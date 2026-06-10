"""Task queue backed by tasks.json."""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

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


def load_tasks() -> list[dict]:
    _ensure_tasks_file()
    return json.loads(_tasks_path.read_text())


def save_tasks(tasks: list[dict]):
    _tasks_path.write_text(json.dumps(tasks, indent=2))


def get_next_queued_task() -> Optional[dict]:
    tasks = load_tasks()
    for task in tasks:
        if task.get("status") == "queued":
            return task
    return None


def mark_task_running(task_id: str):
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = "running"
            task["updated_at"] = datetime.utcnow().isoformat()
    save_tasks(tasks)


def mark_task_complete(task_id: str, summary: str):
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = "complete"
            task["summary"] = summary
            task["updated_at"] = datetime.utcnow().isoformat()
    save_tasks(tasks)


def mark_task_failed(task_id: str, error: str):
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["status"] = "failed"
            task["error"] = error
            task["updated_at"] = datetime.utcnow().isoformat()
    save_tasks(tasks)


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
            task["updated_at"] = datetime.utcnow().isoformat()
    save_tasks(tasks)


def update_task_branch(task_id: str, branch: str):
    """Persist a rewritten branch name back to tasks.json for the given task."""
    tasks = load_tasks()
    for task in tasks:
        if task["id"] == task_id:
            task["branch"] = branch
            task["updated_at"] = datetime.utcnow().isoformat()
    save_tasks(tasks)


def add_task(task: dict):
    tasks = load_tasks()
    if "id" not in task:
        task["id"] = str(uuid.uuid4())[:8]
    task.setdefault("status", "queued")
    task.setdefault("created_at", datetime.utcnow().isoformat())
    tasks.append(task)
    save_tasks(tasks)
