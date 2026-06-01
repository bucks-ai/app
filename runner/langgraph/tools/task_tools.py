"""Task queue backed by tasks.json."""
import json
import uuid
from datetime import datetime
from pathlib import Path
from typing import Optional

_tasks_path = Path(__file__).parent.parent / "tasks.json"

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
    if not _tasks_path.exists():
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


def add_task(task: dict):
    tasks = load_tasks()
    if "id" not in task:
        task["id"] = str(uuid.uuid4())[:8]
    task.setdefault("status", "queued")
    task.setdefault("created_at", datetime.utcnow().isoformat())
    tasks.append(task)
    save_tasks(tasks)
