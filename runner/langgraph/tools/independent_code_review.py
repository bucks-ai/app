"""Independent Code Review Gate.

Provides an autonomous second look at worker changes before they are committed.
Runs after check.sh passes, cross-referencing the actual git diff against the
task's acceptance criteria to catch scope creep, secret leaks, and forbidden-file
modifications — independent of the worker's own summary.

Gate behaviour (controlled from config.py):
- INDEPENDENT_CODE_REVIEW_ENABLED=true (default): runs after check.sh passes
- INDEPENDENT_CODE_REVIEW_STRICT_MODE=false (default): failures logged as
  warnings and commits proceed; set to true to block the commit on failure.
"""
import re
import subprocess
from pathlib import Path
from typing import Optional
from tools.log_tools import log_event

# Patterns that suggest secret material in a diff addition line.
# Anchored to match assignment/definition lines only (not comments or docs).
_SECRET_PATTERNS: list[re.Pattern] = [
    re.compile(r'(?i)\b(api[_-]?key|apikey|secret[_-]?key|access[_-]?key|auth[_-]?key)\s*[=:]\s*["\']?[A-Za-z0-9+/]{16,}'),
    re.compile(r'(?i)\b(password|passwd|pwd)\s*[=:]\s*["\']?\S{8,}'),
    re.compile(r'(?i)\b(token|bearer)\s*[=:]\s*["\']?[A-Za-z0-9._\-]{16,}'),
    re.compile(r'(?i)(sk-|pk-|rk-)[A-Za-z0-9]{20,}'),
    re.compile(r'AKIA[0-9A-Z]{16}'),
]

_EMPTY_VALUES = frozenset({"", "none", "n/a", "na", "(none)", "not applicable", "skipped"})


def _is_meaningful(val: str) -> bool:
    return val.strip().lower() not in _EMPTY_VALUES


def get_diff_text(repo_path: str) -> str:
    """Return the diff of uncommitted changes (or the most recent commit if tree is clean)."""
    try:
        result = subprocess.run(
            ["git", "diff", "HEAD"],
            cwd=repo_path, capture_output=True, text=True, timeout=30,
        )
        diff = result.stdout or ""
        if diff.strip():
            return diff
        # Tree is clean — worker self-committed; inspect HEAD's patch instead.
        result2 = subprocess.run(
            ["git", "show", "--patch", "HEAD"],
            cwd=repo_path, capture_output=True, text=True, timeout=30,
        )
        return result2.stdout or ""
    except Exception:
        return ""


def _extract_changed_files(diff_text: str) -> list[str]:
    """Extract file paths from diff/show output (both +++ and --- sides)."""
    files: set[str] = set()
    for line in diff_text.splitlines():
        m = re.match(r'^(?:\+\+\+|---)\s+(?:a/|b/)?(.+)', line)
        if m:
            f = m.group(1).strip()
            if f and f != "/dev/null":
                files.add(f)
    return sorted(files)


def _check_env_files(all_files: list[str]) -> tuple[bool, str]:
    """Fail when any .env* file was modified."""
    violations = [
        f for f in all_files
        if re.match(r'(?i)^\.env(\.|$)', Path(f).name)
    ]
    if violations:
        return False, f"modified .env file(s): {', '.join(violations[:5])}"
    return True, ""


def _check_forbidden_scope(all_files: list[str], task: dict) -> tuple[bool, str]:
    """Fail when any changed file appears in the task's forbidden_scope."""
    ac = task.get("acceptance_criteria")
    if not isinstance(ac, dict):
        return True, ""

    forbidden_raw = ac.get("forbidden_scope", "")
    if not forbidden_raw or not str(forbidden_raw).strip():
        return True, ""

    forbidden_text = str(forbidden_raw).lower()
    violations = []
    for f in all_files:
        f_stripped = f.strip()
        if not _is_meaningful(f_stripped):
            continue
        f_lower = f_stripped.lower()
        name = Path(f_lower).name
        parts = list(Path(f_lower).parts) + [name]
        for part in parts:
            if part and len(part) > 2 and part in forbidden_text:
                violations.append(f_stripped)
                break

    if violations:
        return False, f"files touch forbidden scope: {', '.join(violations[:5])}"
    return True, ""


def _check_secret_patterns(diff_text: str) -> tuple[bool, str]:
    """Fail when any added diff line matches a known secret pattern."""
    hit_count = 0
    for line in diff_text.splitlines():
        if not line.startswith("+") or line.startswith("+++"):
            continue
        for pattern in _SECRET_PATTERNS:
            if pattern.search(line):
                hit_count += 1
                break

    if hit_count:
        return False, f"diff contains {hit_count} line(s) matching secret patterns"
    return True, ""


def _check_allowed_scope(all_files: list[str], task: dict) -> tuple[bool, str]:
    """Warn when changed files fall outside the task's allowed_scope.

    Returns False only when allowed_scope is explicitly specified AND at least
    one changed file clearly falls outside it. Skipped when no allowed_scope is
    defined, keeping the gate quiet for tasks without strict scope bounds.
    """
    ac = task.get("acceptance_criteria")
    if not isinstance(ac, dict):
        return True, ""

    allowed_raw = ac.get("allowed_scope", "")
    if not allowed_raw:
        return True, ""

    if isinstance(allowed_raw, list):
        allowed_parts = [str(p).strip().lower() for p in allowed_raw if str(p).strip()]
    else:
        allowed_parts = [p.strip().lower() for p in str(allowed_raw).split(",") if p.strip()]

    if not any(allowed_parts):
        return True, ""

    out_of_scope = []
    for f in all_files:
        f_lower = f.lower().strip()
        if not _is_meaningful(f_lower):
            continue
        in_scope = any(
            f_lower.startswith(scope) or scope in f_lower
            for scope in allowed_parts
        )
        if not in_scope:
            out_of_scope.append(f)

    if out_of_scope:
        return False, (
            f"changed files outside allowed_scope "
            f"({', '.join(out_of_scope[:5])})"
        )
    return True, ""


def validate_code_review(
    diff_text: str,
    summary: dict,
    task: dict,
) -> tuple[bool, list[str]]:
    """Run all code review checks. Returns (ok, issues).

    Collects files from both the actual diff and the worker's summary to guard
    against a worker that under-reports what it changed.
    """
    diff_files = _extract_changed_files(diff_text)
    summary_files = [
        str(f).strip()
        for f in (summary.get("files_created") or []) + (summary.get("files_modified") or [])
        if str(f).strip() and _is_meaningful(str(f).strip())
    ]
    all_files: list[str] = sorted({*diff_files, *summary_files})

    checks = [
        _check_env_files(all_files),
        _check_forbidden_scope(all_files, task),
        _check_secret_patterns(diff_text),
        _check_allowed_scope(all_files, task),
    ]
    issues = [msg for ok, msg in checks if not ok]
    return len(issues) == 0, issues


def guard_code_review(
    diff_text: str,
    summary: dict,
    task: dict,
    context: str = "",
    *,
    strict_mode: bool = False,
) -> dict:
    """Run the independent code review gate and log the result.

    Returns a dict with:
    - ``passed`` (bool): True when all checks pass.
    - ``issues`` (list[str]): reasons for failure; empty when passed.
    - ``strict_mode`` (bool): mirrors the input flag.

    Logs ``task_code_review_passed`` on success, or ``task_code_review_rejected``
    (strict mode) / ``task_code_review_warned`` (non-strict) on failure.
    """
    ok, issues = validate_code_review(diff_text, summary, task)
    task_id = task.get("id")

    if ok:
        log_event("task_code_review_passed", {
            "task_id": task_id,
            "context": context,
        }, task_id=task_id)
        return {"passed": True, "issues": [], "strict_mode": strict_mode}

    if strict_mode:
        log_event("task_code_review_rejected", {
            "task_id": task_id,
            "task_title": task.get("title"),
            "issues": issues,
            "context": context,
            "strict_mode": True,
        }, task_id=task_id)
    else:
        log_event("task_code_review_warned", {
            "task_id": task_id,
            "task_title": task.get("title"),
            "issues": issues,
            "context": context,
            "strict_mode": False,
        }, task_id=task_id)

    return {"passed": False, "issues": issues, "strict_mode": strict_mode}
