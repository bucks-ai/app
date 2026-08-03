"""Unit tests for `python main.py doctor` — the queue health report.

``build_report``, ``diff_against_mission_tasks`` and the formatters are pure,
so the Supabase side is supplied as plain rows. ``run_doctor`` is covered
against a temp queue file with the Supabase check switched off.
"""
import json
from datetime import datetime, timedelta

import pytest

import tools.task_tools as task_tools
from tools.queue_doctor import (
    build_report,
    diff_against_mission_tasks,
    format_report,
    format_repairs,
    run_doctor,
)

NOW = datetime(2026, 8, 2, 12, 0, 0)


def _iso(minutes_ago: float) -> str:
    return (NOW - timedelta(minutes=minutes_ago)).isoformat()


def _task(**overrides) -> dict:
    task = {"id": "t1", "title": "A task", "status": "queued"}
    task.update(overrides)
    return task


def _dead(pid: int) -> bool:
    return False


def _report(tasks, **kwargs):
    kwargs.setdefault("now", NOW)
    kwargs.setdefault("host", "box")
    kwargs.setdefault("pid_alive", _dead)
    return build_report(tasks, **kwargs)


# ---------------------------------------------------------------------------
# Report contents
# ---------------------------------------------------------------------------

def test_counts_tasks_by_status():
    report = _report([
        _task(id="a", status="queued"),
        _task(id="b", status="queued"),
        _task(id="c", status="complete"),
    ])
    assert report["task_count"] == 3
    assert report["counts_by_status"] == {"complete": 1, "queued": 2}


def test_status_free_records_are_counted_separately():
    report = _report([{"id": "a", "title": "No status"}])
    assert report["counts_by_status"] == {"<none>": 1}


def test_reports_orphans_with_a_reason():
    report = _report([
        _task(id="stranded", status="running", owner_pid=999, owner_host="box", updated_at=_iso(5)),
    ])
    assert report["orphans"] == [
        {"task_id": "stranded", "reason": "owner_process_gone", "updated_at": _iso(5)}
    ]
    assert report["healthy"] is False


def test_separates_unverifiable_running_tasks_from_orphans():
    report = _report([
        _task(id="foreign", status="running", owner_pid=1, owner_host="elsewhere"),
    ])
    assert report["orphans"] == []
    assert [r["task_id"] for r in report["unverifiable_running"]] == ["foreign"]


def test_reports_duplicates_separately_from_other_violations():
    report = _report([
        _task(id="dup", seeded_task_id="uuid-1"),
        _task(id="dup", seeded_task_id="uuid-2"),
        _task(id="bad", status="in_progress"),
    ])
    assert [d["kind"] for d in report["duplicates"]] == ["duplicate_id"]
    assert "unknown_status" in [v["kind"] for v in report["violations"]]


def test_healthy_queue_reports_healthy():
    report = _report([_task(id="a"), _task(id="b", status="complete")])
    assert report["healthy"] is True
    assert report["orphans"] == report["violations"] == []


def test_supabase_divergence_makes_the_queue_unhealthy():
    report = _report(
        [_task()],
        supabase={"checked": True, "reason": None, "missions": ["m1"], "divergences": [
            {"kind": "status_mismatch", "task_id": "t1", "detail": "x"},
        ]},
    )
    assert report["healthy"] is False


# ---------------------------------------------------------------------------
# Supabase divergence
# ---------------------------------------------------------------------------

def test_status_mismatch_is_reported():
    tasks = [_task(id="t1", status="complete", seeded_mission_id="m1", seeded_task_id="uuid-1")]
    rows = [{"id": "uuid-1", "mission_id": "m1", "status": "queued"}]
    divergence = diff_against_mission_tasks(tasks, rows)[0]
    assert divergence["kind"] == "status_mismatch"
    assert divergence["local_status"] == "complete"
    assert divergence["remote_status"] == "queued"
    assert "sync-back to Supabase did not land" in divergence["detail"]


def test_matching_statuses_produce_no_divergence():
    tasks = [_task(seeded_mission_id="m1", seeded_task_id="uuid-1")]
    rows = [{"id": "uuid-1", "mission_id": "m1", "status": "queued"}]
    assert diff_against_mission_tasks(tasks, rows) == []


def test_local_row_pointing_at_a_missing_supabase_row():
    tasks = [_task(seeded_mission_id="m1", seeded_task_id="uuid-gone")]
    divergence = diff_against_mission_tasks(tasks, [])[0]
    assert divergence["kind"] == "missing_in_supabase"


def test_supabase_row_never_seeded_locally():
    tasks = [_task(id="t1", seeded_mission_id="m1", seeded_task_id="uuid-1")]
    rows = [
        {"id": "uuid-1", "mission_id": "m1", "status": "queued"},
        {"id": "uuid-2", "mission_id": "m1", "status": "queued", "task_id": "m1-2"},
    ]
    divergence = diff_against_mission_tasks(tasks, rows)[0]
    assert divergence["kind"] == "missing_locally"
    assert divergence["task_id"] == "m1-2"


def test_rows_from_other_missions_are_ignored():
    tasks = [_task(seeded_mission_id="m1", seeded_task_id="uuid-1")]
    rows = [
        {"id": "uuid-1", "mission_id": "m1", "status": "queued"},
        {"id": "uuid-9", "mission_id": "m2", "status": "queued"},
    ]
    assert diff_against_mission_tasks(tasks, rows) == []


def test_unseeded_local_tasks_are_ignored():
    assert diff_against_mission_tasks([_task()], [{"id": "uuid-1", "mission_id": "m1"}]) == []


# ---------------------------------------------------------------------------
# Formatting
# ---------------------------------------------------------------------------

def test_format_report_names_each_orphan_and_the_fix_command():
    text = format_report(_report([
        _task(id="stranded", status="running", owner_pid=999, owner_host="box", updated_at=_iso(5)),
    ]))
    assert "stranded" in text
    assert "owner_process_gone" in text
    assert "doctor --fix" in text


def test_format_report_on_a_healthy_queue():
    text = format_report(_report([_task()]))
    assert "Queue is healthy." in text
    assert "No orphaned 'running' tasks" in text


def test_format_report_states_when_supabase_was_not_checked():
    text = format_report(_report([_task()], supabase={
        "checked": False, "reason": "supabase_not_configured", "missions": [], "divergences": [],
    }))
    assert "supabase_not_configured" in text


def test_format_repairs_groups_by_kind():
    text = format_repairs([
        {"kind": "orphaned_running_requeued", "task_id": "a", "detail": "requeued a"},
        {"kind": "orphaned_running_requeued", "task_id": "b", "detail": "requeued b"},
        {"kind": "stale_retry_window_cleared", "task_id": "c", "detail": "cleared c"},
    ])
    assert "orphaned_running_requeued (2)" in text
    assert "stale_retry_window_cleared (1)" in text


def test_format_repairs_with_nothing_to_do():
    assert "Nothing to repair" in format_repairs([])


# ---------------------------------------------------------------------------
# run_doctor against a real queue file
# ---------------------------------------------------------------------------

@pytest.fixture
def queue(tmp_path, monkeypatch):
    path = tmp_path / "tasks.local.json"
    monkeypatch.setattr(task_tools, "_tasks_path", path)
    monkeypatch.setattr(task_tools, "live_task_ids", lambda: set())
    monkeypatch.setattr(task_tools, "_pid_alive", lambda pid: False)
    return path


def _write(path, tasks):
    path.write_text(json.dumps(tasks, indent=2))


def _read(path):
    return json.loads(path.read_text())


def test_run_doctor_reports_without_changing_the_file(queue):
    _write(queue, [_task(id="stranded", status="running", updated_at=_iso(9000))])
    before = queue.read_text()
    result = run_doctor(check_supabase=False)
    assert [o["task_id"] for o in result["report"]["orphans"]] == ["stranded"]
    assert result["repairs"] == []
    assert queue.read_text() == before


def test_run_doctor_fix_requeues_an_orphan(queue):
    _write(queue, [_task(id="stranded", status="running", updated_at=_iso(9000))])
    result = run_doctor(fix=True, check_supabase=False)
    assert _read(queue)[0]["status"] == "queued"
    assert [r["kind"] for r in result["repairs"]] == ["orphaned_running_requeued"]
    assert result["report"]["healthy"] is True


def test_run_doctor_fix_also_fills_missing_required_fields(queue):
    _write(queue, [{"id": "t1", "status": "queued"}])
    result = run_doctor(fix=True, check_supabase=False)
    assert _read(queue)[0]["title"] == "t1"
    assert "missing_title_defaulted" in [r["kind"] for r in result["repairs"]]


def test_run_doctor_fix_is_a_no_op_on_a_healthy_queue(queue):
    _write(queue, [_task()])
    before = queue.read_text()
    result = run_doctor(fix=True, check_supabase=False)
    assert result["repairs"] == []
    assert queue.read_text() == before


def test_run_doctor_text_includes_the_applied_repairs(queue):
    _write(queue, [_task(id="stranded", status="running", updated_at=_iso(9000))])
    text = run_doctor(fix=True, check_supabase=False)["text"]
    assert "Applied 1 repair(s):" in text
    assert "orphaned_running_requeued" in text
