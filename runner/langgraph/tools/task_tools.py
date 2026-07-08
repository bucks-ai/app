"""Task queue backed by tasks.json."""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

_BACKOFF_SKIPPED_STATUS = "queued"  # only queued tasks participate in backoff

_tasks_path = Path(__file__).parent.parent / ".runtime" / "tasks.local.json"
_tasks_path_legacy = Path(__file__).parent.parent / "tasks.json"

_DEFAULT_TASKS = [
    {
        "id": "operating-team-ui",
        "title": "Build Operating Team UI",
        "type": "ui",
        "preferred_worker": "codex",
        "branch": "feature/operating-team-ui",
        "status": "queued",
    }
]


def _ensure_tasks_file():
    _tasks_path.parent.mkdir(parents=True, exist_ok=True)
    if not _tasks_path.exists():
        # Migrate legacy tasks.json → .runtime/tasks.local.json on first run
        if _tasks_path_legacy.exists():
            import shutil
            shutil.copy2(_tasks_path_legacy, _tasks_path)
        else:
            _tasks_path.write_text(json.dumps(_DEFAULT_TASKS, indent=2))


def _now() -> str:
    return datetime.utcnow().isoformat()


def load_tasks() -> list[dict]:
    _ensure_tasks_file()
    return json.loads(_tasks_path.read_text())


def save_tasks(tasks: list[dict]):
    _tasks_path.write_text(json.dumps(tasks, indent=2))


def find_task_by_id(task_id: str) -> Optional[dict]:
    for task in load_tasks():
        if task.get("id") == task_id:
            return task
    return None


def find_task_by_github_issue(issue_number: int) -> Optional[dict]:
    for task in load_tasks():
        if task.get("source") == "github_issue" and task.get("issue_number") == issue_number:
            return task
    return None


def get_next_queued_task() -> Optional[dict]:
    """Return the first queued task whose retry backoff window has expired.

    Tasks with a ``retry_not_before`` timestamp that is still in the future
    are skipped so the runner waits out the backoff rather than immediately
    hitting the same degraded condition again.
    """
    now_iso = _now()
    tasks = load_tasks()
    for task in tasks:
        if task.get("status") != "queued":
            continue
        retry_not_before = task.get("retry_not_before")
        if retry_not_before and retry_not_before > now_iso:
            continue
        return task
    return None


def mark_task_running(task_id: str):
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = "running"
            task["updated_at"] = _now()
    save_tasks(tasks)


def mark_task_complete(task_id: str, summary: str):
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = "complete"
            task["summary"] = summary
            task["updated_at"] = _now()
    save_tasks(tasks)


def mark_task_failed(task_id: str, error: str):
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = "failed"
            task["error"] = error
            task["updated_at"] = _now()
    save_tasks(tasks)


def requeue_fulfilled_blocked_tasks(inbox_dir) -> list[str]:
    """Requeue blocked tasks whose resource-fulfillment file has landed.

    The resource gate blocks a task and waits for
    ``inbox/{task_id}_resources_provided.txt``. The approvals daemon (or a
    human) creates that file, but nothing flipped the task back to ``queued``
    — so the loop restarted into an empty queue and stalled. This scan closes
    that gap. Only file *existence* is checked; contents are never read.

    Returns the list of requeued task ids.
    """
    inbox_dir = Path(inbox_dir)
    requeued = []
    tasks = load_tasks()
    for task in tasks:
        if task.get("status") != "blocked":
            continue
        task_id = task.get("id")
        if task_id and (inbox_dir / f"{task_id}_resources_provided.txt").exists():
            task["status"] = "queued"
            task["error"] = None
            task["updated_at"] = _now()
            requeued.append(task_id)
    if requeued:
        save_tasks(tasks)
    return requeued


def next_retry_eta() -> Optional[str]:
    """Earliest future ``retry_not_before`` among queued tasks, or None.

    When every queued task is inside its retry-backoff window,
    ``get_next_queued_task`` returns None even though work exists — it's just
    ineligible for a few more seconds. The loop uses this ETA to wait out the
    shortest backoff instead of falling through to the planner and stopping
    with ``chatgpt_no_task``.
    """
    now_iso = _now()
    etas = [
        t["retry_not_before"]
        for t in load_tasks()
        if t.get("status") == "queued"
        and t.get("retry_not_before")
        and t["retry_not_before"] > now_iso
    ]
    return min(etas) if etas else None


def mark_task_blocked(task_id: str, reason: str):
    """Mark a task as blocked on a human action (e.g. awaiting resources).

    Distinct from ``failed`` so the task isn't lost as a failure: a human can
    provision what's needed and flip it back to ``queued`` to retry.
    """
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = "blocked"
            task["error"] = reason
            task["updated_at"] = _now()
    save_tasks(tasks)


def requeue_task(task_id: str, retry_count: int, retry_not_before: Optional[str] = None):
    """Requeue a failed task for another attempt (status → ``queued``).

    Records ``retry_count`` so the failure guard can cap how many times a task is
    retried before it is marked permanently ``failed``.  When ``retry_not_before``
    is supplied (an ISO-8601 UTC timestamp), ``get_next_queued_task`` skips this
    task until that time has passed — implementing backoff for degraded workers.
    """
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = "queued"
            task["retry_count"] = retry_count
            task["updated_at"] = _now()
            if retry_not_before:
                task["retry_not_before"] = retry_not_before
            else:
                task.pop("retry_not_before", None)
    save_tasks(tasks)


def update_task_branch(task_id: str, branch: str):
    """Persist a rewritten branch name back to tasks.json for the given task."""
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["branch"] = branch
            task["updated_at"] = _now()
    save_tasks(tasks)


def add_task(task: dict):
    tasks = load_tasks()
    if "id" not in task:
        task["id"] = str(uuid.uuid4())[:8]
    task.setdefault("status", "queued")
    task.setdefault("created_at", _now())
    tasks.append(task)
    save_tasks(tasks)


def upsert_task(task: dict, *, preserve_status: bool = True) -> dict:
    """Insert or update a task by id, or by linked GitHub issue.

    GitHub issue sync can run repeatedly. This keeps the local queue idempotent
    while still refreshing mutable issue fields such as title, labels, and URL.
    Existing execution state is preserved by default so a completed or running
    task is not requeued just because its issue is still open.
    """
    tasks = load_tasks()
    incoming = dict(task)
    if "id" not in incoming:
        incoming["id"] = str(uuid.uuid4())[:8]

    match_idx = None
    for idx, existing in enumerate(tasks):
        if existing.get("id") == incoming.get("id"):
            match_idx = idx
            break
        if (
            incoming.get("source") == "github_issue"
            and existing.get("source") == "github_issue"
            and incoming.get("issue_number") is not None
            and existing.get("issue_number") == incoming.get("issue_number")
        ):
            match_idx = idx
            break

    now = _now()
    if match_idx is None:
        incoming.setdefault("status", "queued")
        incoming.setdefault("created_at", now)
        incoming["updated_at"] = now
        tasks.append(incoming)
        save_tasks(tasks)
        return incoming

    existing = tasks[match_idx]
    merged = {**existing, **incoming}
    if preserve_status:
        merged["status"] = existing.get("status", incoming.get("status", "queued"))
    merged.setdefault("created_at", existing.get("created_at") or now)
    merged["updated_at"] = now
    tasks[match_idx] = merged
    save_tasks(tasks)
    return merged
