"""Validates planner-generated task dicts before they are enqueued."""
from tools.log_tools import log_event
from tools.task_tools import load_tasks

_REQUIRED_FIELDS = ("id", "title", "type")
_KNOWN_WORKERS = frozenset({"claude", "codex", "chatgpt"})
_PROTECTED_BRANCHES = frozenset({
    "main", "master", "dev", "develop", "production", "release",
})


def validate_planner_task(task: dict) -> tuple[bool, list[str]]:
    """Return (ok, issues) for a planner-generated task dict.

    Checks:
    - Required fields (id, title, type) are present and non-empty.
    - Title is at least 5 characters (not trivially short).
    - Branch, if given, is not a protected branch and has no spaces.
    - preferred_worker, if given, is a recognised worker name.
    - Task id does not duplicate an existing task in the queue.
    """
    issues: list[str] = []

    for field in _REQUIRED_FIELDS:
        if not task.get(field):
            issues.append(f"missing required field: '{field}'")

    title = task.get("title", "")
    if title and len(title.strip()) < 5:
        issues.append(f"title too short (< 5 chars): '{title}'")

    branch = task.get("branch", "")
    if branch:
        if branch.lower() in _PROTECTED_BRANCHES:
            issues.append(f"branch '{branch}' is a protected branch")
        if " " in branch:
            issues.append(f"branch '{branch}' contains spaces")

    worker = task.get("preferred_worker", "")
    if worker and worker.lower() not in _KNOWN_WORKERS:
        issues.append(f"unknown preferred_worker: '{worker}'")

    task_id = task.get("id", "")
    if task_id:
        existing_ids = {t["id"] for t in load_tasks()}
        if task_id in existing_ids:
            issues.append(f"duplicate task id: '{task_id}'")

    return len(issues) == 0, issues


def guard_planner_task(task: dict, context: str = "") -> dict | None:
    """Validate a planner task and log the result.

    Returns the task unchanged if valid, or None if it fails validation.
    Logs a 'task_quality_rejected' event on failure.
    """
    ok, issues = validate_planner_task(task)
    if ok:
        log_event("task_quality_passed", {
            "task_id": task.get("id"),
            "context": context,
        })
        return task

    log_event("task_quality_rejected", {
        "task_id": task.get("id"),
        "task_title": task.get("title"),
        "issues": issues,
        "context": context,
    })
    return None
