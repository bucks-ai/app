"""Logging and state persistence tools."""
import json
import os
from datetime import datetime
from pathlib import Path

_runner_dir = Path(__file__).parent.parent
_logs_path = _runner_dir / "logs" / "runs.jsonl"
_state_path = _runner_dir / ".runtime" / "state.local.json"
_state_path_legacy = _runner_dir / "state.json"


def _ensure_dirs():
    _logs_path.parent.mkdir(parents=True, exist_ok=True)
    _state_path.parent.mkdir(parents=True, exist_ok=True)
    # Migrate legacy state.json → .runtime/state.local.json on first run
    if not _state_path.exists() and _state_path_legacy.exists():
        import shutil
        shutil.copy2(_state_path_legacy, _state_path)


def new_event(event_type: str, payload: dict, task_id: str = None) -> dict:
    return {
        "event_type": event_type,
        "timestamp": datetime.utcnow().isoformat(),
        "task_id": task_id,
        "payload": payload,
    }


def append_jsonl_event(event: dict):
    _ensure_dirs()
    with open(_logs_path, "a") as f:
        f.write(json.dumps(event) + "\n")


def update_state(state: dict):
    _ensure_dirs()
    state["updated_at"] = datetime.utcnow().isoformat()
    with open(_state_path, "w") as f:
        json.dump(state, f, indent=2)


def read_state() -> dict:
    if not _state_path.exists():
        return {}
    with open(_state_path) as f:
        return json.load(f)


def read_logs(tail: int = 50) -> list[dict]:
    if not _logs_path.exists():
        return []
    lines = _logs_path.read_text().strip().splitlines()
    recent = lines[-tail:] if tail else lines
    events = []
    for line in recent:
        try:
            events.append(json.loads(line))
        except json.JSONDecodeError:
            pass
    return events


def log_event(event_type: str, payload: dict, task_id: str = None):
    event = new_event(event_type, payload, task_id)
    append_jsonl_event(event)
    return event
