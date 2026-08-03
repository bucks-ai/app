"""Validates planner-generated task dicts before they are enqueued.

v2 additions (guarded by the v2 flag):
- Title length bounds: 10..200 chars
- Task-type allowlist — unknown types rejected
- Branch name pattern validation — only safe characters, no '..' sequences

Hard scope guard (separate evaluate_scope_guard function):
- Scans title + description for patterns indicating forbidden operations
  (force-pushes, direct production deploys, bypassing safety gates, etc.)
"""
import re
from tools.log_tools import log_event
from tools.task_tools import load_tasks

_REQUIRED_FIELDS = ("id", "title", "type")
_KNOWN_WORKERS = frozenset({"claude", "codex", "chatgpt"})
_PROTECTED_BRANCHES = frozenset({
    "main", "master", "dev", "develop", "production", "release",
})
# Allowlist of task types the runner knows how to handle.  Unknown types are a
# signal the planner produced an out-of-scope task (v2 check only).
_KNOWN_TASK_TYPES = frozenset({
    "backend", "frontend", "ui", "design", "polish",
    "general", "bugfix", "feature", "refactor", "test",
    "docs", "database", "api", "auth", "infra", "devops",
})

_TITLE_MIN_CHARS = 10   # v2: up from 5
_TITLE_MAX_CHARS = 200

# v2: branch names must use only safe characters and must not contain '..'
# which could indicate a directory-traversal-style branch reference.
# Pattern: starts and ends with alphanumeric; middle may include / _ - .
_BRANCH_SAFE_RE = re.compile(r'^[a-zA-Z0-9]([a-zA-Z0-9/_.\-]*[a-zA-Z0-9])?$')

# ---------------------------------------------------------------------------
# Hard scope guard
# ---------------------------------------------------------------------------
# Each entry: (compiled pattern, human-readable violation label).
# Matched case-insensitively against title + description + prompt fields.
_SCOPE_PATTERNS: list[tuple[re.Pattern, str]] = [
    (re.compile(r'force[\s\-]*push', re.IGNORECASE),
     "force-push operation"),
    (re.compile(r'push\s+.*--force', re.IGNORECASE),
     "force-push flag"),
    (re.compile(r'git\s+reset\s+.*--hard', re.IGNORECASE),
     "hard git reset"),
    (re.compile(r'drop\s+(table|database|schema|db)\b', re.IGNORECASE),
     "destructive database drop"),
    (re.compile(r'truncate\s+table\b', re.IGNORECASE),
     "table truncation"),
    (re.compile(r'delete\s+all\s+records?\b', re.IGNORECASE),
     "bulk record deletion"),
    (re.compile(
        r'\b(bypass|skip|disable|remove)\s+(the\s+(\w+\s+)?)?(check|test|guard|gate|hook|approval|safety)\b',
        re.IGNORECASE),
     "bypassing a safety gate"),
    (re.compile(r'--no-verify\b', re.IGNORECASE),
     "git --no-verify (bypasses commit hooks)"),
    (re.compile(r'commit\.gpgsign\s*=\s*false', re.IGNORECASE),
     "disabling GPG signing"),
    (re.compile(
        r'merge\s+directly\s+(in)?to\s+(main|master|prod(uction)?)\b',
        re.IGNORECASE),
     "direct merge to protected branch"),
    (re.compile(
        r'push\s+directly\s+(to\s+)?(main|master|prod(uction)?)\b',
        re.IGNORECASE),
     "direct push to protected branch"),
    (re.compile(
        r'deploy\s+directly\s+(to\s+)?(main|master|prod(uction)?|staging)\b',
        re.IGNORECASE),
     "direct deploy bypassing workflow"),
    (re.compile(r'\.\./+', re.IGNORECASE),
     "directory traversal sequence"),
]


def validate_planner_task(task: dict, *, v2: bool = True) -> tuple[bool, list[str]]:
    """Return (ok, issues) for a planner-generated task dict.

    v1 checks (always active):
    - Required fields (id, title, type) present and non-empty
    - Title >= 5 chars
    - Branch not a protected name and contains no spaces
    - preferred_worker, if given, is a recognised worker name
    - Task id does not duplicate an existing queued task

    v2 checks (when v2=True, the default):
    - Title between _TITLE_MIN_CHARS and _TITLE_MAX_CHARS chars
    - type must be in _KNOWN_TASK_TYPES
    - Branch name matches safe-character pattern; no '..' sequences
    """
    issues: list[str] = []

    for field in _REQUIRED_FIELDS:
        if not task.get(field):
            issues.append(f"missing required field: '{field}'")

    title = task.get("title", "")
    if title:
        title_stripped = title.strip()
        if v2:
            if len(title_stripped) < _TITLE_MIN_CHARS:
                issues.append(
                    f"title too short (< {_TITLE_MIN_CHARS} chars): '{title}'"
                )
            if len(title_stripped) > _TITLE_MAX_CHARS:
                issues.append(f"title too long (> {_TITLE_MAX_CHARS} chars)")
        else:
            if len(title_stripped) < 5:
                issues.append(f"title too short (< 5 chars): '{title}'")

    task_type = task.get("type", "")
    if task_type and v2 and task_type.lower() not in _KNOWN_TASK_TYPES:
        issues.append(
            f"unknown task type: '{task_type}' "
            f"(allowed: {sorted(_KNOWN_TASK_TYPES)})"
        )

    branch = task.get("branch", "")
    if branch:
        if branch.lower() in _PROTECTED_BRANCHES:
            issues.append(f"branch '{branch}' is a protected branch")
        if " " in branch:
            issues.append(f"branch '{branch}' contains spaces")
        if v2:
            if ".." in branch:
                issues.append(f"branch '{branch}' contains '..' sequence")
            if not _BRANCH_SAFE_RE.match(branch):
                issues.append(f"branch '{branch}' contains unsafe characters")

    worker = task.get("preferred_worker", "")
    if worker and worker.lower() not in _KNOWN_WORKERS:
        issues.append(f"unknown preferred_worker: '{worker}'")

    task_id = task.get("id", "")
    if task_id:
        existing_ids = {t["id"] for t in load_tasks()}
        if task_id in existing_ids:
            issues.append(f"duplicate task id: '{task_id}'")

    return len(issues) == 0, issues


def evaluate_scope_guard(task: dict) -> tuple[bool, list[str]]:
    """Check whether a task requests an operation outside the runner's scope.

    Scans the combined text of ``title``, ``description``, and ``prompt``
    fields (case-insensitive) against _SCOPE_PATTERNS.  A single match is
    enough to reject the task.

    Returns (clean, violations) where ``clean`` is True when no patterns fire.
    """
    text = " ".join(filter(None, [
        task.get("title", ""),
        task.get("description", ""),
        task.get("prompt", ""),
    ]))
    violations: list[str] = []
    for pattern, label in _SCOPE_PATTERNS:
        if pattern.search(text):
            violations.append(label)
    return len(violations) == 0, violations


def guard_planner_task(
    task: dict,
    context: str = "",
    *,
    v2: bool = True,
    scope_guard: bool = True,
) -> dict | None:
    """Validate a planner task and log the result.

    Runs the quality gate (v2 by default) and the hard scope guard (enabled
    by default).  Returns the task unchanged when all checks pass, or None
    when any check fails.  Logs a structured rejection event on failure.
    """
    all_issues: list[str] = []

    ok, issues = validate_planner_task(task, v2=v2)
    if not ok:
        all_issues.extend(issues)

    if scope_guard:
        clean, violations = evaluate_scope_guard(task)
        if not clean:
            all_issues.extend(f"scope_guard: {v}" for v in violations)

    if not all_issues:
        log_event("task_quality_passed", {
            "task_id": task.get("id"),
            "context": context,
            "v2": v2,
            "scope_guard": scope_guard,
        })
        return task

    log_event("task_quality_rejected", {
        "task_id": task.get("id"),
        "task_title": task.get("title"),
        "issues": all_issues,
        "context": context,
        "v2": v2,
        "scope_guard": scope_guard,
    })
    return None
