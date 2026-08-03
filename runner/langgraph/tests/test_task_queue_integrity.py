"""Integration tests for the durability guarantees of the task queue file.

Covers the parts of ``tools/task_tools.py`` that cannot be pure: atomic saves,
auto-repair on load, session-ownership stamping, and transition enforcement.

These are the failure modes the founder hand-fixed during M4b — each test is
named for the incident it prevents from recurring.
"""
import json
import os
from datetime import datetime, timedelta

import pytest

import tools.task_tools as task_tools


@pytest.fixture
def queue(tmp_path, monkeypatch):
    path = tmp_path / "tasks.local.json"
    monkeypatch.setattr(task_tools, "_tasks_path", path)
    # No inherited session ownership unless a test opts in.
    monkeypatch.setattr(task_tools, "live_task_ids", lambda: set())
    return path


def _iso(minutes_ago: float) -> str:
    return (datetime.utcnow() - timedelta(minutes=minutes_ago)).isoformat()


def _write(path, tasks):
    path.write_text(json.dumps(tasks, indent=2))


def _read(path):
    return json.loads(path.read_text())


def _by_id(tasks):
    return {t["id"]: t for t in tasks}


# ---------------------------------------------------------------------------
# Atomic writes
# ---------------------------------------------------------------------------

def test_save_writes_valid_json(queue):
    task_tools.save_tasks([{"id": "a", "title": "A", "status": "queued"}])
    assert _read(queue)[0]["id"] == "a"


def test_save_leaves_no_temp_file_behind(queue):
    task_tools.save_tasks([{"id": "a", "title": "A", "status": "queued"}])
    assert [p.name for p in queue.parent.iterdir()] == ["tasks.local.json"]


def test_interrupted_save_leaves_the_previous_queue_intact(queue, monkeypatch):
    """The whole point of the temp-file-plus-rename: a crash mid-save must not
    truncate the queue. Before M4c.0 this was a bare ``write_text``, which
    opens the real file for truncation before writing a single byte."""
    original = [{"id": "a", "title": "A", "status": "queued"}]
    task_tools.save_tasks(original)

    def _boom(src, dst):
        raise KeyboardInterrupt("killed mid-save")

    monkeypatch.setattr(task_tools.os, "replace", _boom)
    with pytest.raises(KeyboardInterrupt):
        task_tools.save_tasks([{"id": "b", "title": "B", "status": "queued"}])

    assert _read(queue) == original
    assert [p.name for p in queue.parent.iterdir()] == ["tasks.local.json"]


def test_the_test_suite_can_never_write_the_real_queue(tmp_path, monkeypatch):
    """A test that forgets to redirect ``_tasks_path`` must not rewrite the
    founder's live queue — which is exactly what happened the first time
    load-time repair was switched on. Both paths are pointed at a temp file
    here so the guard is exercised without going near real runtime state."""
    stand_in = tmp_path / "tasks.local.json"
    _write(stand_in, [{"id": "a", "title": "A", "status": "queued"}])
    monkeypatch.setattr(task_tools, "_tasks_path", stand_in)
    monkeypatch.setattr(task_tools, "_REAL_TASKS_PATH", stand_in)

    assert task_tools._persist_queue([]) is False
    assert _read(stand_in) == [{"id": "a", "title": "A", "status": "queued"}]


def test_corrupt_queue_is_salvaged_not_silently_dropped(queue):
    queue.write_text('[{"id": "a", "status": "que')
    assert task_tools.load_tasks() == []
    salvaged = [p for p in queue.parent.iterdir() if ".corrupt." in p.name]
    assert len(salvaged) == 1
    assert salvaged[0].read_text() == '[{"id": "a", "status": "que'


# ---------------------------------------------------------------------------
# Auto-repair on load
# ---------------------------------------------------------------------------

def test_load_requeues_a_running_task_whose_owner_process_is_gone(queue, monkeypatch):
    monkeypatch.setattr(task_tools, "_pid_alive", lambda pid: False)
    _write(queue, [{
        "id": "stranded", "title": "Stranded", "status": "running",
        "owner_pid": 424242, "owner_host": task_tools.socket.gethostname(),
        "updated_at": _iso(5),
    }])
    assert task_tools.load_tasks()[0]["status"] == "queued"
    # …and the repair is persisted, so the next process sees it too.
    assert _read(queue)[0]["status"] == "queued"


def test_load_leaves_a_running_task_with_a_live_owner_alone(queue):
    _write(queue, [{
        "id": "mine", "title": "Mine", "status": "running",
        "owner_pid": os.getpid(), "owner_host": task_tools.socket.gethostname(),
        "updated_at": _iso(120),
    }])
    assert task_tools.load_tasks()[0]["status"] == "running"


def test_load_leaves_the_current_sessions_task_alone(queue, monkeypatch):
    """A pre-M4c.0 row has no owner pid. The running session still names it in
    state.local.json, so it must not be requeued out from under itself."""
    monkeypatch.setattr(task_tools, "live_task_ids", lambda: {"in-flight"})
    _write(queue, [{
        "id": "in-flight", "title": "In flight", "status": "running",
        "updated_at": _iso(9000),
    }])
    assert task_tools.load_tasks()[0]["status"] == "running"


def test_load_requeues_a_long_stale_ownerless_running_task(queue):
    _write(queue, [{
        "id": "m4b-07", "title": "Stranded since last week", "status": "running",
        "updated_at": _iso(60 * 24 * 7),
    }])
    assert task_tools.load_tasks()[0]["status"] == "queued"


def test_load_clears_a_stale_retry_window_on_a_finished_task(queue):
    _write(queue, [{
        "id": "done", "title": "Done", "status": "complete",
        "retry_not_before": _iso(-120),
    }])
    assert "retry_not_before" not in task_tools.load_tasks()[0]


def test_load_requeues_an_unknown_status(queue):
    _write(queue, [{"id": "weird", "title": "Weird", "status": "in_progress"}])
    assert task_tools.load_tasks()[0]["status"] == "queued"


def test_load_deduplicates_colliding_ids(queue):
    _write(queue, [
        {"id": "dup", "title": "Dup", "status": "queued"},
        {"id": "dup", "title": "Dup", "status": "complete", "summary": "shipped"},
    ])
    tasks = task_tools.load_tasks()
    assert len(tasks) == 1
    assert tasks[0]["status"] == "complete"


def test_load_repair_is_logged_per_repair_kind(queue, monkeypatch):
    events = []
    monkeypatch.setattr(task_tools, "_log", lambda et, payload, task_id=None: events.append((et, payload)))
    _write(queue, [
        {"id": "weird", "title": "Weird", "status": "in_progress"},
        {"id": "old", "title": "Old", "status": "running", "updated_at": _iso(9000)},
    ])
    task_tools.load_tasks()
    kinds = {p.get("kind") for et, p in events if et == "task_queue_repaired"}
    assert kinds == {"unknown_status_requeued", "orphaned_running_requeued"}
    assert any(et == "task_queue_repair_summary" for et, _ in events)


def test_load_does_not_rewrite_a_healthy_queue(queue):
    _write(queue, [{"id": "a", "title": "A", "status": "queued"}])
    before = queue.stat().st_mtime_ns
    task_tools.load_tasks()
    assert queue.stat().st_mtime_ns == before


def test_load_with_repair_disabled_returns_the_file_verbatim(queue):
    raw = [{"id": "old", "title": "Old", "status": "running", "updated_at": _iso(9000)}]
    _write(queue, raw)
    assert task_tools.load_tasks(repair=False) == raw


def test_load_does_not_invent_a_missing_title(queue):
    """Load-time repair fixes impossible states, not cosmetic ones — filling
    fields on every load would rewrite records nobody asked us to touch."""
    _write(queue, [{"id": "a", "status": "queued"}])
    assert "title" not in task_tools.load_tasks()[0]


# ---------------------------------------------------------------------------
# Ownership stamping
# ---------------------------------------------------------------------------

def test_marking_running_stamps_the_owning_process(queue):
    _write(queue, [{"id": "a", "title": "A", "status": "queued"}])
    task_tools.mark_task_running("a")
    task = _read(queue)[0]
    assert task["owner_pid"] == os.getpid()
    assert task["owner_host"] == task_tools.socket.gethostname()


def test_completing_a_task_releases_ownership(queue):
    _write(queue, [{"id": "a", "title": "A", "status": "queued"}])
    task_tools.mark_task_running("a")
    task_tools.mark_task_complete("a", "done")
    task = _read(queue)[0]
    assert task["status"] == "complete"
    assert "owner_pid" not in task and "owner_host" not in task


def test_requeueing_a_task_releases_ownership(queue):
    _write(queue, [{"id": "a", "title": "A", "status": "queued"}])
    task_tools.mark_task_running("a")
    task_tools.requeue_task("a", 1)
    task = _read(queue)[0]
    assert task["status"] == "queued"
    assert "owner_pid" not in task


def test_a_stamped_running_task_survives_reload_in_the_same_process(queue):
    _write(queue, [{"id": "a", "title": "A", "status": "queued"}])
    task_tools.mark_task_running("a")
    assert task_tools.load_tasks()[0]["status"] == "running"


# ---------------------------------------------------------------------------
# Transition enforcement
# ---------------------------------------------------------------------------

def test_a_completed_task_cannot_be_reopened_as_running(queue, monkeypatch):
    events = []
    monkeypatch.setattr(task_tools, "_log", lambda et, p, task_id=None: events.append((et, p)))
    _write(queue, [{"id": "a", "title": "A", "status": "complete"}])
    task_tools.mark_task_running("a")
    assert _read(queue)[0]["status"] == "complete"
    assert [et for et, _ in events] == ["task_transition_rejected"]


def test_a_completed_task_cannot_be_marked_failed(queue):
    _write(queue, [{"id": "a", "title": "A", "status": "complete"}])
    task_tools.mark_task_failed("a", "late error")
    assert _read(queue)[0]["status"] == "complete"


def test_a_completed_task_can_still_be_requeued(queue):
    _write(queue, [{"id": "a", "title": "A", "status": "complete"}])
    task_tools.requeue_task("a", 0)
    assert _read(queue)[0]["status"] == "queued"


def test_a_failed_task_can_be_requeued_then_run_again(queue):
    _write(queue, [{"id": "a", "title": "A", "status": "failed"}])
    task_tools.requeue_task("a", 1)
    task_tools.mark_task_running("a")
    assert _read(queue)[0]["status"] == "running"


def test_the_normal_lifecycle_is_never_blocked(queue):
    _write(queue, [{"id": "a", "title": "A", "status": "queued"}])
    task_tools.mark_task_running("a")
    task_tools.mark_task_blocked("a", "awaiting resources")
    assert _read(queue)[0]["status"] == "blocked"
    task_tools.requeue_task("a", 0)
    task_tools.mark_task_running("a")
    task_tools.mark_task_complete("a", "shipped")
    assert _read(queue)[0]["status"] == "complete"


def test_status_writes_only_touch_the_named_task(queue):
    _write(queue, [
        {"id": "a", "title": "A", "status": "queued"},
        {"id": "b", "title": "B", "status": "queued"},
    ])
    task_tools.mark_task_complete("a", "done")
    tasks = _by_id(_read(queue))
    assert tasks["a"]["status"] == "complete"
    assert tasks["b"]["status"] == "queued"


def test_save_logs_a_schema_violation_without_refusing_the_write(queue, monkeypatch):
    events = []
    monkeypatch.setattr(task_tools, "_log", lambda et, p, task_id=None: events.append((et, p)))
    task_tools.save_tasks([{"id": "dup", "status": "queued"}, {"id": "dup", "status": "queued"}])
    assert len(_read(queue)) == 2
    kinds = {k for et, p in events if et == "task_schema_violation" for k in p["kinds"]}
    assert "duplicate_id" in kinds
