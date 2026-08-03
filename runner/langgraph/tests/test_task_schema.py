"""Unit tests for the task-record schema, invariants, and auto-repair.

Every rule in ``tools/task_schema.py`` is pure, so these tests need no
filesystem, no clock, and no live process — liveness and time are injected.

The repair cases are named after the states the founder actually hand-fixed
during M4b: a stranded ``running`` task, triple-seeded colliding ids, and a
finished task still holding a retry window.
"""
from datetime import datetime, timedelta

import pytest

from tools.task_schema import (
    ORPHAN_GRACE_SECONDS,
    STATUSES,
    apply_field_defaults,
    classify_running_task,
    classify_running_tasks,
    find_orphaned_running,
    progress_score,
    repair_tasks,
    validate_task,
    validate_tasks,
    validate_transition,
)

NOW = datetime(2026, 8, 2, 12, 0, 0)


def _iso(minutes_ago: float) -> str:
    return (NOW - timedelta(minutes=minutes_ago)).isoformat()


def _task(**overrides) -> dict:
    task = {"id": "t1", "title": "A task", "status": "queued"}
    task.update(overrides)
    return task


def _never_alive(pid: int) -> bool:
    return False


def _always_alive(pid: int) -> bool:
    return True


def _kinds(items) -> list:
    return [item["kind"] for item in items]


# ---------------------------------------------------------------------------
# Schema validation
# ---------------------------------------------------------------------------

def test_valid_task_has_no_violations():
    assert validate_task(_task()) == []


@pytest.mark.parametrize("field", ["id", "title", "status"])
def test_missing_required_field_is_a_violation(field):
    task = _task()
    del task[field]
    violations = validate_task(task)
    assert "missing_required_field" in _kinds(violations)
    assert any(v["field"] == field for v in violations)


def test_blank_required_field_is_a_violation():
    assert "missing_required_field" in _kinds(validate_task(_task(title="   ")))


def test_unknown_status_is_a_violation():
    violation = validate_task(_task(status="in_progress"))[0]
    assert violation["kind"] == "unknown_status"
    assert "in_progress" in violation["detail"]


@pytest.mark.parametrize("status", sorted(STATUSES))
def test_every_allowed_status_validates(status):
    assert validate_task(_task(status=status)) == []


def test_wrong_field_type_is_a_violation():
    violation = validate_task(_task(retry_count="3"))[0]
    assert violation["kind"] == "wrong_field_type"
    assert violation["field"] == "retry_count"


def test_boolean_is_not_accepted_as_an_int_field():
    assert "wrong_field_type" in _kinds(validate_task(_task(retry_count=True)))


def test_negative_retry_count_is_a_violation():
    assert "invalid_field_value" in _kinds(validate_task(_task(retry_count=-1)))


def test_unknown_extra_fields_are_allowed():
    assert validate_task(_task(completion_evidence={"sha": "abc"}, dry_run=True)) == []


def test_unparseable_retry_not_before_is_a_violation():
    assert "invalid_field_value" in _kinds(validate_task(_task(retry_not_before="soonish")))


def test_terminal_task_holding_a_retry_window_is_a_violation():
    violations = validate_task(_task(status="complete", retry_not_before=_iso(-30)))
    assert "retry_window_on_terminal_task" in _kinds(violations)


def test_blocked_task_may_hold_a_retry_window():
    # blocked is a parked task awaiting a human, not a terminal state.
    assert validate_task(_task(status="blocked", retry_not_before=_iso(-30))) == []


def test_non_object_entry_is_reported_not_raised():
    assert validate_task("not-a-task", 3)[0]["kind"] == "not_an_object"


def test_queue_must_be_a_list():
    assert validate_tasks({"id": "t1"})[0]["kind"] == "queue_not_a_list"


def test_duplicate_ids_are_reported():
    violations = validate_tasks([_task(id="dup"), _task(id="dup")])
    assert "duplicate_id" in _kinds(violations)


def test_duplicate_seeded_task_ids_are_reported():
    violations = validate_tasks([
        _task(id="a", seeded_task_id="uuid-1"),
        _task(id="b", seeded_task_id="uuid-1"),
    ])
    assert "duplicate_seeded_task_id" in _kinds(violations)


def test_clean_queue_has_no_violations():
    assert validate_tasks([_task(id="a"), _task(id="b", seeded_task_id="uuid-1")]) == []


# ---------------------------------------------------------------------------
# Transitions
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("old,new", [
    ("queued", "running"),
    ("queued", "blocked"),
    ("running", "complete"),
    ("running", "failed"),
    ("running", "queued"),
    ("blocked", "queued"),
    ("failed", "queued"),
    ("complete", "queued"),
    ("complete", "complete"),
])
def test_allowed_transitions(old, new):
    assert validate_transition(old, new) is True


@pytest.mark.parametrize("old,new", [
    ("complete", "running"),
    ("complete", "failed"),
    ("complete", "blocked"),
    ("failed", "running"),
    ("failed", "complete"),
])
def test_terminal_states_only_leave_via_requeue(old, new):
    assert validate_transition(old, new) is False


def test_unknown_target_status_is_rejected():
    assert validate_transition("queued", "in_progress") is False


def test_unknown_source_status_is_permissive():
    # The record is already broken; repair handles it, rejection would strand it.
    assert validate_transition("in_progress", "queued") is True
    assert validate_transition(None, "running") is True


# ---------------------------------------------------------------------------
# Orphan classification
# ---------------------------------------------------------------------------

def test_task_claimed_by_current_session_is_live():
    task = _task(status="running", updated_at=_iso(600))
    verdict = classify_running_task(task, live_task_ids={"t1"}, now=NOW, pid_alive=_never_alive)
    assert verdict == {"live": True, "reason": "claimed_by_current_session"}


def test_running_task_with_live_owner_process_is_live():
    task = _task(status="running", owner_pid=4242, owner_host="box", updated_at=_iso(600))
    verdict = classify_running_task(task, now=NOW, host="box", pid_alive=_always_alive)
    assert verdict == {"live": True, "reason": "owner_process_alive"}


def test_running_task_with_dead_owner_process_is_orphaned():
    task = _task(status="running", owner_pid=4242, owner_host="box", updated_at=_iso(1))
    verdict = classify_running_task(task, now=NOW, host="box", pid_alive=_never_alive)
    assert verdict == {"live": False, "reason": "owner_process_gone"}


def test_owner_on_another_host_is_never_stolen():
    task = _task(status="running", owner_pid=4242, owner_host="other-box", updated_at=_iso(9000))
    verdict = classify_running_task(task, now=NOW, host="box", pid_alive=_never_alive)
    assert verdict == {"live": True, "reason": "owner_on_other_host"}


def test_ownerless_running_task_within_grace_is_live():
    task = _task(status="running", updated_at=_iso(5))
    verdict = classify_running_task(task, now=NOW, pid_alive=_never_alive)
    assert verdict["live"] is True
    assert verdict["reason"] == "no_owner_record_within_grace"


def test_ownerless_running_task_past_grace_is_orphaned():
    task = _task(status="running", updated_at=_iso(ORPHAN_GRACE_SECONDS / 60 + 1))
    verdict = classify_running_task(task, now=NOW, pid_alive=_never_alive)
    assert verdict == {"live": False, "reason": "no_owner_record_stale"}


def test_ownerless_running_task_without_timestamp_is_left_alone():
    # Nothing to measure staleness against, so it must not be requeued blind.
    verdict = classify_running_task(_task(status="running"), now=NOW, pid_alive=_never_alive)
    assert verdict == {"live": True, "reason": "no_owner_record_unverifiable"}


def test_created_at_is_used_when_updated_at_is_missing():
    task = _task(status="running", created_at=_iso(ORPHAN_GRACE_SECONDS / 60 + 1))
    assert classify_running_task(task, now=NOW, pid_alive=_never_alive)["live"] is False


def test_classify_running_tasks_buckets_each_row():
    tasks = [
        _task(id="live", status="running", owner_pid=1, owner_host="box"),
        _task(id="dead", status="running", owner_pid=2, owner_host="box", updated_at=_iso(1)),
        _task(id="foreign", status="running", owner_pid=3, owner_host="elsewhere"),
        _task(id="queued-one", status="queued"),
    ]
    buckets = classify_running_tasks(
        tasks, now=NOW, host="box", pid_alive=lambda pid: pid == 1
    )
    assert [r["task_id"] for r in buckets["live"]] == ["live"]
    assert [r["task_id"] for r in buckets["orphaned"]] == ["dead"]
    assert [r["task_id"] for r in buckets["unverifiable"]] == ["foreign"]


def test_find_orphaned_running_ignores_non_running_rows():
    tasks = [_task(id="c", status="complete", updated_at=_iso(9000))]
    assert find_orphaned_running(tasks, now=NOW, pid_alive=_never_alive) == []


# ---------------------------------------------------------------------------
# Repair: orphaned running
# ---------------------------------------------------------------------------

def test_repair_requeues_orphaned_running_task():
    tasks = [_task(status="running", owner_pid=99, owner_host="box", updated_at=_iso(3))]
    repaired, repairs = repair_tasks(tasks, now=NOW, host="box", pid_alive=_never_alive)
    assert repaired[0]["status"] == "queued"
    assert _kinds(repairs) == ["orphaned_running_requeued"]
    assert repairs[0]["reason"] == "owner_process_gone"


def test_repair_clears_the_owner_record_when_requeueing():
    tasks = [_task(status="running", owner_pid=99, owner_host="box", updated_at=_iso(3))]
    repaired, _ = repair_tasks(tasks, now=NOW, host="box", pid_alive=_never_alive)
    assert "owner_pid" not in repaired[0]
    assert "owner_host" not in repaired[0]


def test_repair_leaves_a_live_running_task_alone():
    tasks = [_task(status="running", owner_pid=99, owner_host="box", updated_at=_iso(3))]
    repaired, repairs = repair_tasks(tasks, now=NOW, host="box", pid_alive=_always_alive)
    assert repaired[0]["status"] == "running"
    assert repairs == []


def test_repair_does_not_mutate_the_input():
    original = _task(status="running", updated_at=_iso(9000))
    tasks = [original]
    repair_tasks(tasks, now=NOW, pid_alive=_never_alive)
    assert original["status"] == "running"


# ---------------------------------------------------------------------------
# Repair: duplicates
# ---------------------------------------------------------------------------

def test_two_rows_for_one_supabase_row_collapse_to_the_one_with_progress():
    tasks = [
        _task(id="a", status="queued", seeded_task_id="uuid-1"),
        _task(id="a", status="complete", seeded_task_id="uuid-1", summary="shipped"),
    ]
    repaired, repairs = repair_tasks(tasks, now=NOW, pid_alive=_never_alive)
    assert len(repaired) == 1
    assert repaired[0]["status"] == "complete"
    assert _kinds(repairs) == ["duplicate_seeded_task_merged"]


def test_triple_seeded_colliding_ids_are_reassigned_not_dropped():
    # The "Execute: AI Infra" case: three seedings, one id, three distinct
    # Supabase rows. Dropping two would silently discard real work.
    tasks = [
        _task(id="ai-infra-1", status="queued", seeded_task_id=f"uuid-{n}", title=f"Set {n}")
        for n in (1, 2, 3)
    ]
    repaired, repairs = repair_tasks(tasks, now=NOW, pid_alive=_never_alive)
    assert len(repaired) == 3
    assert sorted(t["id"] for t in repaired) == ["ai-infra-1", "ai-infra-1-2", "ai-infra-1-3"]
    assert _kinds(repairs) == ["duplicate_id_reassigned"] * 2


def test_reassignment_keeps_the_row_with_progress_on_the_original_id():
    tasks = [
        _task(id="dup", status="queued", seeded_task_id="uuid-1"),
        _task(id="dup", status="complete", seeded_task_id="uuid-2"),
    ]
    repaired, _ = repair_tasks(tasks, now=NOW, pid_alive=_never_alive)
    by_id = {t["id"]: t for t in repaired}
    assert by_id["dup"]["status"] == "complete"
    assert by_id["dup-2"]["status"] == "queued"


def test_reassignment_does_not_collide_with_an_existing_id():
    tasks = [
        _task(id="dup", status="queued", seeded_task_id="uuid-1"),
        _task(id="dup", status="queued", seeded_task_id="uuid-2"),
        _task(id="dup-2", status="queued", seeded_task_id="uuid-3"),
    ]
    repaired, _ = repair_tasks(tasks, now=NOW, pid_alive=_never_alive)
    ids = [t["id"] for t in repaired]
    assert len(ids) == len(set(ids)) == 3


def test_indistinguishable_duplicate_ids_are_merged():
    tasks = [
        _task(id="dup", status="queued"),
        _task(id="dup", status="running", updated_at=_iso(1)),
    ]
    repaired, repairs = repair_tasks(tasks, now=NOW, pid_alive=_never_alive)
    assert len(repaired) == 1
    assert _kinds(repairs)[0] == "duplicate_id_merged"


def test_progress_score_prefers_complete_over_running():
    assert progress_score(_task(status="complete")) > progress_score(_task(status="running"))
    assert progress_score(_task(status="running")) > progress_score(_task(status="queued"))


def test_progress_score_breaks_ties_on_evidence_then_recency():
    with_summary = _task(status="failed", summary="did work", updated_at=_iso(90))
    bare = _task(status="failed", updated_at=_iso(1))
    assert progress_score(with_summary) > progress_score(bare)


# ---------------------------------------------------------------------------
# Repair: stale retry window, unknown status, junk entries
# ---------------------------------------------------------------------------

def test_terminal_task_loses_its_stale_retry_window():
    tasks = [_task(status="failed", retry_not_before=_iso(-120))]
    repaired, repairs = repair_tasks(tasks, now=NOW, pid_alive=_never_alive)
    assert "retry_not_before" not in repaired[0]
    assert _kinds(repairs) == ["stale_retry_window_cleared"]


def test_queued_task_keeps_its_retry_window():
    tasks = [_task(status="queued", retry_not_before=_iso(-120))]
    repaired, repairs = repair_tasks(tasks, now=NOW, pid_alive=_never_alive)
    assert repaired[0]["retry_not_before"] == _iso(-120)
    assert repairs == []


def test_unknown_status_is_requeued_loudly():
    tasks = [_task(status="in_progress")]
    repaired, repairs = repair_tasks(tasks, now=NOW, pid_alive=_never_alive)
    assert repaired[0]["status"] == "queued"
    assert repairs[0]["kind"] == "unknown_status_requeued"
    assert repairs[0]["previous_status"] == "in_progress"


def test_missing_status_is_requeued():
    task = _task()
    del task["status"]
    repaired, repairs = repair_tasks([task], now=NOW, pid_alive=_never_alive)
    assert repaired[0]["status"] == "queued"
    assert _kinds(repairs) == ["unknown_status_requeued"]


def test_non_object_entries_are_dropped():
    repaired, repairs = repair_tasks(["junk", _task()], now=NOW, pid_alive=_never_alive)
    assert len(repaired) == 1
    assert "dropped_non_object" in _kinds(repairs)


def test_non_list_queue_repairs_to_empty():
    repaired, repairs = repair_tasks({"id": "t1"}, now=NOW)
    assert repaired == []
    assert _kinds(repairs) == ["queue_not_a_list"]


def test_owner_record_is_stripped_from_non_running_tasks():
    tasks = [_task(status="complete", owner_pid=7, owner_host="box")]
    repaired, _ = repair_tasks(tasks, now=NOW, host="box", pid_alive=_always_alive)
    assert "owner_pid" not in repaired[0]


def test_healthy_queue_needs_no_repair():
    tasks = [
        _task(id="a", status="queued"),
        _task(id="b", status="complete"),
        _task(id="c", status="running", owner_pid=1, owner_host="box"),
    ]
    repaired, repairs = repair_tasks(tasks, now=NOW, host="box", pid_alive=_always_alive)
    assert repairs == []
    assert repaired == tasks


def test_repair_output_is_schema_valid():
    tasks = [
        _task(id="dup", status="in_progress", seeded_task_id="uuid-1"),
        _task(id="dup", status="complete", seeded_task_id="uuid-1", retry_not_before=_iso(-5)),
        _task(id="orphan", status="running", updated_at=_iso(9000)),
    ]
    repaired, _ = repair_tasks(tasks, now=NOW, pid_alive=_never_alive)
    assert validate_tasks(repaired) == []


def test_repair_is_idempotent():
    tasks = [
        _task(id="dup", status="in_progress", seeded_task_id="uuid-1"),
        _task(id="dup", status="complete", seeded_task_id="uuid-2", retry_not_before=_iso(-5)),
        _task(id="orphan", status="running", updated_at=_iso(9000)),
    ]
    once, _ = repair_tasks(tasks, now=NOW, pid_alive=_never_alive)
    twice, repairs = repair_tasks(once, now=NOW, pid_alive=_never_alive)
    assert repairs == []
    assert twice == once


# ---------------------------------------------------------------------------
# Field defaults (doctor --fix only)
# ---------------------------------------------------------------------------

def test_field_defaults_fill_a_missing_title():
    task = _task()
    del task["title"]
    repaired, fixes = apply_field_defaults([task], now_iso=NOW.isoformat())
    assert repaired[0]["title"] == "t1"
    assert _kinds(fixes) == ["missing_title_defaulted"]


def test_field_defaults_generate_a_missing_id():
    repaired, fixes = apply_field_defaults(
        [{"title": "No id", "status": "queued"}], now_iso=NOW.isoformat()
    )
    assert repaired[0]["id"] == "recovered-task-1"
    assert _kinds(fixes) == ["missing_id_generated"]


def test_field_defaults_reset_a_negative_retry_count():
    repaired, fixes = apply_field_defaults([_task(retry_count=-2)], now_iso=NOW.isoformat())
    assert repaired[0]["retry_count"] == 0
    assert _kinds(fixes) == ["negative_retry_count_reset"]


def test_field_defaults_leave_a_healthy_record_alone():
    repaired, fixes = apply_field_defaults([_task()], now_iso=NOW.isoformat())
    assert fixes == []
    assert repaired == [_task()]
