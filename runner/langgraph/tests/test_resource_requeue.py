"""Tests for tools.task_tools.requeue_fulfilled_blocked_tasks.

Covers the gap where the approvals daemon wrote the inbox fulfillment file
but the blocked task was never flipped back to ``queued``, stalling the loop.
"""
import json

import pytest

import tools.task_tools as task_tools


@pytest.fixture
def queue(tmp_path, monkeypatch):
    """Point the task queue at a temp file and return (tasks_path, inbox_dir)."""
    tasks_path = tmp_path / "tasks.local.json"
    inbox = tmp_path / "inbox"
    inbox.mkdir()
    monkeypatch.setattr(task_tools, "_tasks_path", tasks_path)
    return tasks_path, inbox


def _write_tasks(tasks_path, tasks):
    tasks_path.write_text(json.dumps(tasks, indent=2))


def _statuses(tasks_path):
    return {t["id"]: t["status"] for t in json.loads(tasks_path.read_text())}


def test_requeues_blocked_task_with_fulfillment_file(queue):
    tasks_path, inbox = queue
    _write_tasks(tasks_path, [
        {"id": "t1", "status": "blocked", "error": "awaiting resources/credentials"},
    ])
    (inbox / "t1_resources_provided.txt").touch()

    assert task_tools.requeue_fulfilled_blocked_tasks(inbox) == ["t1"]
    assert _statuses(tasks_path)["t1"] == "queued"


def test_blocked_task_without_file_stays_blocked(queue):
    tasks_path, inbox = queue
    _write_tasks(tasks_path, [
        {"id": "t1", "status": "blocked", "error": "awaiting resources/credentials"},
    ])

    assert task_tools.requeue_fulfilled_blocked_tasks(inbox) == []
    assert _statuses(tasks_path)["t1"] == "blocked"


def test_non_blocked_tasks_untouched(queue):
    tasks_path, inbox = queue
    _write_tasks(tasks_path, [
        {"id": "t1", "status": "queued"},
        {"id": "t2", "status": "complete"},
        {"id": "t3", "status": "failed", "error": "boom"},
    ])
    # Fulfillment files for non-blocked tasks must not change anything.
    for tid in ("t1", "t2", "t3"):
        (inbox / f"{tid}_resources_provided.txt").touch()

    assert task_tools.requeue_fulfilled_blocked_tasks(inbox) == []
    assert _statuses(tasks_path) == {"t1": "queued", "t2": "complete", "t3": "failed"}


def test_mixed_queue_only_fulfilled_requeued(queue):
    tasks_path, inbox = queue
    _write_tasks(tasks_path, [
        {"id": "a", "status": "blocked", "error": "awaiting resources/credentials"},
        {"id": "b", "status": "blocked", "error": "awaiting resources/credentials"},
        {"id": "c", "status": "queued"},
    ])
    (inbox / "a_resources_provided.txt").touch()

    assert task_tools.requeue_fulfilled_blocked_tasks(inbox) == ["a"]
    statuses = _statuses(tasks_path)
    assert statuses == {"a": "queued", "b": "blocked", "c": "queued"}
    # Requeue clears the stale blocked-reason.
    task_a = [t for t in json.loads(tasks_path.read_text()) if t["id"] == "a"][0]
    assert task_a["error"] is None
