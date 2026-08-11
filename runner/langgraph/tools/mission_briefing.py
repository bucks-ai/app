"""Mission briefing and task precheck — pure functions for worker prompt enrichment.

build_mission_briefing:   Returns a briefing block for the worker prompt when the
                          current task belongs to a named mission.  Empty string
                          for tasks with no mission — the prompt is byte-identical.

extract_file_paths:       Parses concrete file paths from a task description.
check_artifacts_present:  Tests whether every named artifact exists in the repo.
should_precheck_task:     Returns False when a task has force_dispatch set.

All functions are pure (no disk writes, no log_event calls, no API calls).
"""
from __future__ import annotations

import re
from pathlib import Path
from typing import Optional

_ALREADY_DONE_CAP = 5

# Recognisable file extensions — deliberately narrow so prose words never
# look like paths.  Extend as real artifact types arise; do not add ".*".
_EXTENSION_ALLOWLIST = frozenset({
    "py", "ts", "tsx", "js", "jsx", "json", "yaml", "yml",
    "sh", "sql", "md", "txt", "toml", "cfg", "lock",
    "html", "css", "go", "rs", "rb", "java", "kt",
    "graphql", "prisma", "proto", "env",
})

# Matches path-like strings with at least one directory separator.
# Negative lookbehind keeps URL components out (skips "://foo/bar.js").
_PATH_RE = re.compile(
    r'(?<![:/\w])'                          # not preceded by URL-like chars
    r'((?:\.\.?/)?(?:\w[\w.-]*/){1,10}'    # optional leading ../ or ./; 1-10 dir segments
    r'\w[\w.-]*\.(?:\w+))'                  # filename.ext
)


# ---------------------------------------------------------------------------
# Mission briefing
# ---------------------------------------------------------------------------

def _is_mission_task(task: dict) -> bool:
    """True when the task belongs to any named mission."""
    return bool(task.get("mission"))


def _mission_key(task: dict) -> str:
    return task.get("mission") or ""


def _same_mission(task_a: dict, task_b: dict) -> bool:
    key_a = _mission_key(task_a)
    key_b = _mission_key(task_b)
    return bool(key_a) and key_a == key_b


def _files_from_summary(raw_summary: str) -> list[str]:
    """Extract reported file paths from a raw worker summary string."""
    if not raw_summary:
        return []
    try:
        from tools.summary_tools import parse_worker_summary
        parsed = parse_worker_summary(raw_summary)
        files: list[str] = (
            list(parsed.get("files_created") or [])
            + list(parsed.get("files_modified") or [])
        )
        return [
            f for f in files
            if f and f.strip().lower() not in ("none", "n/a", "")
        ]
    except Exception:
        return []


def build_mission_briefing(current_task: dict, all_tasks: list[dict]) -> str:
    """Return a mission briefing block to prepend to the worker prompt.

    Returns "" for tasks with no mission, leaving the prompt byte-identical to
    what it was before this feature was added.

    current_task — the task about to be dispatched.
    all_tasks    — the full task queue (as returned by task_tools.load_tasks).
    """
    if not _is_mission_task(current_task):
        return ""

    current_id = current_task.get("id", "")
    mission_name = _mission_key(current_task)

    mission_tasks = [t for t in all_tasks if _same_mission(current_task, t)]
    if not mission_tasks:
        return ""

    current_idx = next(
        (i for i, t in enumerate(mission_tasks) if t.get("id") == current_id), -1
    )

    completed = [t for t in mission_tasks if t.get("status") == "complete"]
    still_to_come = [
        t for i, t in enumerate(mission_tasks)
        if t.get("status") in ("queued", "blocked")
        and t.get("id") != current_id
        and i > current_idx
    ]

    total = len(mission_tasks)
    # 1-based position; fall back to last position when current task not found
    position = (current_idx + 1) if current_idx >= 0 else total

    lines = [
        "## MISSION CONTEXT (read before starting — do not skip)",
        "",
        f"Mission: {mission_name}",
        f"Position: You are task {position} of {total} in this mission.",
        (
            "The mission plan was approved by the founder. "
            "This work is pre-authorised — execute, do not ask whether to proceed."
        ),
        "",
    ]

    # ── ALREADY DONE ─────────────────────────────────────────────────────────
    lines.append(
        "### ALREADY DONE (already merged to main — do NOT rebuild any of this)"
    )
    if not completed:
        lines.append("(none — you are the first task in this mission)")
    else:
        lines.append(
            "NOTE: The summaries below are REPORTED BY THE WORKER, "
            "not independently verified."
        )
        shown = completed[-_ALREADY_DONE_CAP:]
        rest_count = len(completed) - len(shown)
        if rest_count > 0:
            lines.append(
                f"(showing {len(shown)} most recent; "
                f"{rest_count} earlier task(s) also complete)"
            )
        for t in shown:
            task_id_label = t.get("id", "?")
            title = t.get("title", "?")
            lines.append(f"- [{task_id_label}] {title}")
            files = _files_from_summary(t.get("summary", ""))
            if files:
                shown_files = files[:8]
                suffix = f" (+{len(files) - 8} more)" if len(files) > 8 else ""
                lines.append(f"  Files: {', '.join(shown_files)}{suffix}")

    lines.append("")

    # ── STILL TO COME ────────────────────────────────────────────────────────
    lines.append(
        "### STILL TO COME (NOT your job — do NOT implement any of these)"
    )
    if not still_to_come:
        lines.append("(none — you are the last task in this mission)")
    else:
        for t in still_to_come:
            lines.append(f"- {t.get('title', '?')}")

    lines.append("")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Already-satisfied precheck
# ---------------------------------------------------------------------------

def extract_file_paths(description: str) -> list[str]:
    """Extract concrete file paths from a task description.

    Conservative: only returns strings that contain at least one path separator,
    have a recognised file extension, and do not look like URL fragments.

    Returns [] when no concrete artifacts are named — the caller must always
    dispatch when the list is empty.
    """
    if not description:
        return []

    found: list[str] = []
    for m in _PATH_RE.finditer(description):
        path = m.group(1)
        # Extension must be in the allowlist.
        ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
        if ext not in _EXTENSION_ALLOWLIST:
            continue
        # Skip URL fragments (the lookbehind catches most, but check context).
        start = m.start()
        prefix = description[max(0, start - 12):start]
        if "://" in prefix:
            continue
        if path not in found:
            found.append(path)

    return found


def check_artifacts_present(
    file_paths: list[str],
    repo_path: str,
    *,
    extra_search_dirs: Optional[list[str]] = None,
) -> dict:
    """Check whether all named file paths exist in the working tree.

    Returns:
        present      — paths that exist under at least one search root.
        missing      — paths not found under any search root.
        all_present  — True only when file_paths is non-empty AND every path
                       exists (the "already satisfied" condition).

    The caller is responsible for ensuring file_paths is non-empty before
    treating all_present=True as a skip signal.
    """
    if not file_paths:
        return {"present": [], "missing": [], "all_present": False}

    search_roots = [Path(repo_path)]
    for d in extra_search_dirs or []:
        p = Path(d)
        if p != Path(repo_path):
            search_roots.append(p)

    present: list[str] = []
    missing: list[str] = []
    for path_str in file_paths:
        found = any((root / path_str).exists() for root in search_roots)
        (present if found else missing).append(path_str)

    return {
        "present": present,
        "missing": missing,
        "all_present": len(missing) == 0,
    }


def should_precheck_task(task: dict) -> bool:
    """Return False when the task's force_dispatch flag is set.

    A task with force_dispatch=True always dispatches a worker, even when
    all named artifacts already exist.
    """
    return not bool(task.get("force_dispatch"))
