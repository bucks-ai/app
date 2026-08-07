"""Tests for m4c-03 state self-healing.

Each test is named for the M4b incident it prevents from recurring: a run that
exits ``seeded_queue_exhausted`` while a task is stranded ``running``, a
mission seeded three times into 15 colliding rows, and a network blip that
marked a task terminally ``failed``.
"""
import json
from datetime import datetime, timedelta

import pytest

import graph
import tools.task_tools as task_tools
from state import RunnerState
from tools.state_self_healing import (
    MAX_ORPHAN_REQUEUES,
    PLACEHOLDER_TASK_IDS,
    call_with_transient_retry,
    classify_error,
    decide_failure_disposition,
    is_transient_error,
    plan_mission_seeding,
    plan_startup_heal,
    run_startup_heal,
    summarize_startup_heal,
    unique_task_id,
)


def _iso(minutes_ago: float = 0) -> str:
    return (datetime.utcnow() - timedelta(minutes=minutes_ago)).isoformat()


def _by_id(tasks):
    return {t["id"]: t for t in tasks}


@pytest.fixture
def queue(tmp_path, monkeypatch):
    """Redirect the real queue file and drop any inherited session ownership."""
    path = tmp_path / "tasks.local.json"
    monkeypatch.setattr(task_tools, "_tasks_path", path)
    monkeypatch.setattr(task_tools, "live_task_ids", lambda: set())
    return path


# ---------------------------------------------------------------------------
# 1. Startup self-heal — the stranded 'running' incident (m4b-07/08/09/10)
# ---------------------------------------------------------------------------

def test_a_running_task_whose_owner_is_gone_is_requeued_at_startup():
    """The incident itself: an interrupted run leaves the in-flight task at
    'running' forever, the next loop sees zero queued work, and the run exits
    looking finished 30 seconds after it started."""
    tasks = [{
        "id": "m4b-07", "title": "M4b task", "status": "running",
        "owner_pid": 4242, "owner_host": "laptop", "updated_at": _iso(5),
    }]
    plan = plan_startup_heal(tasks, host="laptop", pid_alive=lambda pid: False)
    healed = _by_id(plan["tasks"])
    assert healed["m4b-07"]["status"] == "queued"
    assert healed["m4b-07"]["orphan_requeue_count"] == 1
    assert "owner_pid" not in healed["m4b-07"]
    assert [o["task_id"] for o in plan["orphans_requeued"]] == ["m4b-07"]
    assert plan["changed"] is True


def test_a_running_task_with_a_live_owner_is_never_stolen():
    tasks = [{
        "id": "live", "title": "Live", "status": "running",
        "owner_pid": 4242, "owner_host": "laptop", "updated_at": _iso(5),
    }]
    plan = plan_startup_heal(tasks, host="laptop", pid_alive=lambda pid: True)
    assert _by_id(plan["tasks"])["live"]["status"] == "running"
    assert plan["orphans_requeued"] == []
    assert plan["changed"] is False


def test_a_running_task_that_cannot_be_verified_is_reported_not_touched():
    tasks = [{
        "id": "elsewhere", "title": "Remote", "status": "running",
        "owner_pid": 99, "owner_host": "other-box", "updated_at": _iso(5),
    }]
    plan = plan_startup_heal(tasks, host="laptop", pid_alive=lambda pid: False)
    assert _by_id(plan["tasks"])["elsewhere"]["status"] == "running"
    assert [u["task_id"] for u in plan["unverifiable_running"]] == ["elsewhere"]


def test_an_endlessly_orphaned_task_is_parked_blocked_not_requeued_forever():
    """Requeueing is right for an interrupted run and wrong for a crash loop:
    a task orphaned on every restart kills the process that claims it."""
    tasks = [{
        "id": "crasher", "title": "Crasher", "status": "running",
        "owner_pid": 1, "owner_host": "laptop", "updated_at": _iso(5),
        "orphan_requeue_count": MAX_ORPHAN_REQUEUES,
    }]
    plan = plan_startup_heal(tasks, host="laptop", pid_alive=lambda pid: False)
    parked = _by_id(plan["tasks"])["crasher"]
    assert parked["status"] == "blocked", "must never be 'failed' — blocked is liftable"
    assert parked["orphan_requeue_count"] == MAX_ORPHAN_REQUEUES + 1
    assert [p["task_id"] for p in plan["parked_orphans"]] == ["crasher"]
    assert plan["orphans_requeued"] == []


def test_placeholder_fixture_rows_are_pruned():
    tasks = [
        {"id": "rls-fixture-task", "title": "RLS fixture mission task", "status": "complete"},
        {"id": "real", "title": "Real", "status": "queued"},
    ]
    plan = plan_startup_heal(tasks)
    assert [t["id"] for t in plan["tasks"]] == ["real"]
    assert [p["task_id"] for p in plan["pruned"]] == ["rls-fixture-task"]


def test_a_placeholder_that_actually_ran_is_kept():
    """Pruning must never discard a record of work that happened."""
    placeholder_id = sorted(PLACEHOLDER_TASK_IDS)[0]
    tasks = [{
        "id": placeholder_id, "title": "Fixture", "status": "complete",
        "summary": "Files: created docs/x.md",
    }]
    plan = plan_startup_heal(tasks)
    assert [t["id"] for t in plan["tasks"]] == [placeholder_id]
    assert plan["pruned"] == []


def test_a_healthy_queue_is_left_completely_alone():
    tasks = [
        {"id": "a", "title": "A", "status": "queued"},
        {"id": "b", "title": "B", "status": "complete", "summary": "done"},
    ]
    plan = plan_startup_heal(tasks)
    assert plan["tasks"] == tasks
    assert plan["changed"] is False


def test_summary_names_every_class_of_damage():
    tasks = [
        {"id": "orphan", "title": "O", "status": "running",
         "owner_pid": 1, "owner_host": "laptop", "updated_at": _iso(5)},
        {"id": "rls-fixture-task", "title": "F", "status": "complete"},
    ]
    plan = plan_startup_heal(tasks, host="laptop", pid_alive=lambda pid: False)
    summary = summarize_startup_heal(plan, task_count_before=len(tasks))
    assert summary["task_count_before"] == 2
    assert summary["task_count_after"] == 1
    assert summary["orphans_requeued"] == ["orphan"]
    assert summary["pruned"] == ["rls-fixture-task"]
    assert summary["repairs_by_kind"]["orphaned_running_requeued"] == 1
    assert summary["healed"] is True


def test_run_startup_heal_persists_and_logs(queue, monkeypatch):
    queue.write_text(json.dumps([
        {"id": "stranded", "title": "S", "status": "running",
         "owner_pid": 1, "owner_host": "nowhere", "updated_at": _iso(5)},
        {"id": "rls-fixture-task", "title": "F", "status": "complete"},
    ]))
    monkeypatch.setattr(task_tools, "_pid_alive", lambda pid: False)
    monkeypatch.setattr("socket.gethostname", lambda: "nowhere")
    events = []
    monkeypatch.setattr("tools.log_tools.log_event",
                        lambda et, payload, task_id=None: events.append((et, payload)))

    summary = run_startup_heal()

    persisted = _by_id(json.loads(queue.read_text()))
    assert persisted["stranded"]["status"] == "queued"
    assert "rls-fixture-task" not in persisted
    assert summary["orphans_requeued"] == ["stranded"]
    kinds = [et for et, _ in events]
    assert "orphaned_task_requeued" in kinds
    assert "placeholder_task_pruned" in kinds
    assert "startup_self_heal" in kinds


def test_startup_heal_is_idempotent(queue, monkeypatch):
    queue.write_text(json.dumps([
        {"id": "stranded", "title": "S", "status": "running",
         "owner_pid": 1, "owner_host": "nowhere", "updated_at": _iso(5)},
    ]))
    monkeypatch.setattr(task_tools, "_pid_alive", lambda pid: False)
    monkeypatch.setattr("socket.gethostname", lambda: "nowhere")
    run_startup_heal()
    second = run_startup_heal()
    assert second["healed"] is False
    assert json.loads(queue.read_text())[0]["orphan_requeue_count"] == 1


# ---------------------------------------------------------------------------
# 2. Idempotent seeding — the triple-seeded "Execute: AI Infra" mission
# ---------------------------------------------------------------------------

def _candidates(mission_id="m-1", count=3, prefix="ai-infra"):
    return [
        {
            "id": f"{prefix}-{i}", "title": f"Task {i}", "status": "queued",
            "seeded_mission_id": mission_id, "seeded_task_id": f"uuid-{i}",
        }
        for i in range(1, count + 1)
    ]


def _remote(count=3):
    return [{"id": f"uuid-{i}", "position": i} for i in range(1, count + 1)]


def test_first_seeding_adds_every_task():
    plan = plan_mission_seeding("m-1", _candidates(), [], remote_rows=_remote())
    assert [t["id"] for t in plan["to_add"]] == ["ai-infra-1", "ai-infra-2", "ai-infra-3"]
    assert plan["skipped"] == []
    assert plan["already_seeded"] is False


def test_re_seeding_the_same_mission_adds_nothing():
    """The incident: nothing checked whether the mission was already local, so
    "Execute: AI Infra" produced 15 rows with ids ai-infra-1..5 three times
    over, and a completion could mark the wrong row."""
    existing = _candidates()
    plan = plan_mission_seeding("m-1", _candidates(), existing, remote_rows=_remote())
    assert plan["to_add"] == []
    assert [s["seeded_task_id"] for s in plan["skipped"]] == ["uuid-1", "uuid-2", "uuid-3"]
    assert plan["already_seeded"] is True


def test_seeding_three_times_never_exceeds_the_missions_task_count():
    queue_tasks: list = []
    for _ in range(3):
        plan = plan_mission_seeding("m-1", _candidates(), queue_tasks, remote_rows=_remote())
        queue_tasks = queue_tasks + plan["to_add"]
    assert len(queue_tasks) == 3
    assert len({t["id"] for t in queue_tasks}) == 3


def test_only_the_genuinely_new_mission_task_is_added():
    existing = _candidates(count=2)
    plan = plan_mission_seeding("m-1", _candidates(count=3), existing, remote_rows=_remote())
    assert [t["seeded_task_id"] for t in plan["to_add"]] == ["uuid-3"]
    assert len(plan["skipped"]) == 2


def test_a_colliding_local_id_is_reassigned_before_it_is_written():
    """Two different missions can derive the same local id. M4c.0 repairs that
    after the fact; seeding must not create it in the first place."""
    existing = [{"id": "ai-infra-1", "title": "Other mission", "status": "queued",
                 "seeded_mission_id": "m-other", "seeded_task_id": "other-uuid"}]
    plan = plan_mission_seeding("m-1", _candidates(count=1), existing, remote_rows=_remote(1))
    assert plan["to_add"][0]["id"] == "ai-infra-1-2"
    assert plan["reassignments"] == [{
        "seeded_task_id": "uuid-1",
        "requested_id": "ai-infra-1",
        "assigned_id": "ai-infra-1-2",
    }]


def test_ids_stay_unique_within_one_seeding_batch():
    existing = [{"id": "dup", "title": "Existing", "status": "queued"}]
    candidates = [
        {"id": "dup", "title": "A", "status": "queued",
         "seeded_mission_id": "m-1", "seeded_task_id": "uuid-a"},
        {"id": "dup", "title": "B", "status": "queued",
         "seeded_mission_id": "m-1", "seeded_task_id": "uuid-b"},
    ]
    plan = plan_mission_seeding("m-1", candidates, existing, remote_rows=[{"id": "uuid-a"}, {"id": "uuid-b"}])
    assert [t["id"] for t in plan["to_add"]] == ["dup-2", "dup-3"]


def test_supabase_is_the_source_of_truth_for_what_the_mission_contains():
    existing = _candidates(count=3)
    existing[2]["status"] = "queued"
    plan = plan_mission_seeding("m-1", _candidates(count=2), existing, remote_rows=_remote(2))
    stale = plan["stale_local"]
    assert [s["seeded_task_id"] for s in stale] == ["uuid-3"]
    assert stale[0]["prunable"] is True


def test_a_finished_local_row_is_never_pruned_as_stale():
    existing = _candidates(count=3)
    existing[2]["status"] = "complete"
    plan = plan_mission_seeding("m-1", _candidates(count=2), existing, remote_rows=_remote(2))
    assert plan["stale_local"][0]["prunable"] is False


def test_unique_task_id_walks_past_every_taken_suffix():
    assert unique_task_id("t", set()) == "t"
    assert unique_task_id("t", {"t"}) == "t-2"
    assert unique_task_id("t", {"t", "t-2", "t-3"}) == "t-4"


# ---------------------------------------------------------------------------
# 3. Transient vs genuine — the "business not found" incident
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("error,signal", [
    ("Temporary failure in name resolution", "dns"),
    ("could not resolve host: api.supabase.co", "dns"),
    ("[Errno 104] Connection reset by peer", "connection"),
    ("Max retries exceeded with url: /rest/v1/businesses", "connection"),
    ("HTTPSConnectionPool: Read timeout", "timeout"),
    ("context deadline exceeded", "timeout"),
    ("429 Too Many Requests", "rate_limit"),
    ("rate limit exceeded, retry later", "rate_limit"),
    ("502 Bad Gateway", "server_error"),
    ("service unavailable", "server_error"),
])
def test_infrastructure_failures_are_transient(error, signal):
    verdict = classify_error(error)
    assert verdict["class"] == "transient"
    assert verdict["signal"] == signal


@pytest.mark.parametrize("error", [
    "check.sh failed: 3 tests failing",
    "acceptance criteria missing",
    "worker returned no output",
    "SyntaxError: invalid syntax",
    "business b-1 not found for sandboxed mission",
    "",
    None,
])
def test_everything_else_is_genuine(error):
    """The default must be conservative: wrongly calling a real failure
    transient retries broken work forever."""
    assert classify_error(error)["class"] == "genuine"


def test_a_worker_cli_timeout_is_not_reclassified_as_transient():
    """A worker that runs past its own timeout is a local degradation with its
    own guard and its own backoff. Calling it transient would make a worker
    that never finishes un-failable."""
    assert not is_transient_error("claude CLI timed out after 2700s")
    assert not is_transient_error("worker timed out")


def test_a_status_code_needs_status_context_to_count():
    assert is_transient_error("http 503 from supabase")
    assert is_transient_error("status code: 500")
    assert not is_transient_error("commit 503abc touched 500 lines")


def test_transport_exceptions_are_transient_whatever_they_say():
    import subprocess

    assert is_transient_error(ConnectionResetError("boom"))
    assert is_transient_error(TimeoutError("nothing useful here")), (
        "socket.timeout is TimeoutError from 3.10 on"
    )
    assert not is_transient_error(subprocess.TimeoutExpired("claude", 2700)), (
        "a worker CLI overrunning its own timeout is a local degradation, not a transport failure"
    )


def test_a_transient_cause_wrapped_in_a_generic_error_is_still_transient():
    try:
        try:
            raise ConnectionRefusedError("connection refused")
        except ConnectionRefusedError as inner:
            raise RuntimeError("supabase query failed") from inner
    except RuntimeError as exc:
        assert is_transient_error(exc)


def test_a_transient_failure_retries_without_spending_the_terminal_budget():
    task = {"id": "t1", "retry_count": 1, "transient_retry_count": 0}
    disposition = decide_failure_disposition("connection reset", task, max_transient_retries=3)
    assert disposition["action"] == "retry"
    assert disposition["terminal_allowed"] is False
    assert disposition["transient_retry_count"] == 1


def test_a_transient_failure_parks_blocked_once_its_retries_are_spent():
    """Never 'failed'. failed is terminal, and a terminal task on a degraded
    network is exactly what forced the hand-edits: every relaunch exhausted the
    queue in 30 seconds."""
    task = {"id": "t1", "transient_retry_count": 3}
    disposition = decide_failure_disposition("connection reset", task, max_transient_retries=3)
    assert disposition["action"] == "park"
    assert disposition["terminal_allowed"] is False


def test_a_genuine_failure_is_left_to_the_failure_guard():
    disposition = decide_failure_disposition("check.sh failed", {"id": "t1"})
    assert disposition["action"] == "defer"
    assert disposition["terminal_allowed"] is True


def test_call_with_transient_retry_retries_then_succeeds():
    attempts = []

    def flaky():
        attempts.append(1)
        if len(attempts) < 3:
            raise OSError("Connection refused")
        return {"ok": "row"}

    out = call_with_transient_retry(flaky, op="test", attempts=3, _sleep=lambda s: None)
    assert out["ok"] is True
    assert out["value"] == {"ok": "row"}
    assert out["attempts"] == 3


def test_call_with_transient_retry_does_not_retry_genuine_errors():
    attempts = []

    def broken():
        attempts.append(1)
        raise ValueError("column does not exist")

    out = call_with_transient_retry(broken, op="test", attempts=3, _sleep=lambda s: None)
    assert out["ok"] is False
    assert out["transient"] is False
    assert len(attempts) == 1


def test_call_with_transient_retry_reports_an_unreachable_service():
    def down():
        raise OSError("Temporary failure in name resolution")

    out = call_with_transient_retry(down, op="test", attempts=2, _sleep=lambda s: None)
    assert out == {
        "ok": False, "value": None, "error": "Temporary failure in name resolution",
        "transient": True, "signal": "dns", "attempts": 2,
    }


# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

def test_self_healing_is_on_by_default_and_reported(monkeypatch):
    from config import RunnerConfig

    monkeypatch.delenv("STATE_SELF_HEALING", raising=False)
    monkeypatch.delenv("MAX_TRANSIENT_RETRIES", raising=False)
    cfg = RunnerConfig()
    assert cfg.state_self_healing_enabled is True
    assert cfg.max_transient_retries == 5
    report = cfg.report()
    assert report["state_self_healing_enabled"] is True
    assert report["max_transient_retries"] == 5


def test_self_healing_can_be_switched_off_and_tuned(monkeypatch):
    from config import RunnerConfig

    monkeypatch.setenv("STATE_SELF_HEALING", "false")
    monkeypatch.setenv("MAX_TRANSIENT_RETRIES", "2")
    cfg = RunnerConfig()
    assert cfg.state_self_healing_enabled is False
    assert cfg.max_transient_retries == 2


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------

def test_the_startup_heal_runs_before_the_first_task_is_claimed():
    edges = [(e.source, e.target) for e in graph.graph.get_graph().edges]
    assert "self_heal_task_state" in graph.graph.nodes
    assert ("check_pending_migrations_if_needed", "self_heal_task_state") in edges
    assert ("self_heal_task_state", "load_next_task") in edges


def test_the_startup_heal_node_records_its_summary_on_state(monkeypatch):
    monkeypatch.setattr(graph, "run_startup_heal", lambda: {"healed": True, "orphans_requeued": ["x"]})
    out = graph.self_heal_task_state(RunnerState())
    assert out.startup_self_heal["orphans_requeued"] == ["x"]


def test_the_startup_heal_node_is_skipped_when_self_healing_is_off(monkeypatch):
    called = []
    monkeypatch.setattr(graph, "run_startup_heal", lambda: called.append(1))
    monkeypatch.setattr(graph.cfg, "state_self_healing_enabled", False)
    out = graph.self_heal_task_state(RunnerState())
    assert called == []
    assert out.startup_self_heal is None


def test_an_unreachable_database_requeues_the_task_instead_of_failing_it(monkeypatch):
    """The incident verbatim: a degraded network broke the Supabase lookup and
    the task was marked failed with "business not found"."""
    failed, blocked, requeued = [], [], []
    monkeypatch.setattr(graph, "lookup_business", lambda bid: {
        "status": "unreachable", "business": None,
        "error": "Temporary failure in name resolution", "signal": "dns",
    })
    monkeypatch.setattr(graph, "mark_task_failed", lambda tid, err: failed.append(tid))
    monkeypatch.setattr(graph, "mark_task_blocked", lambda tid, err: blocked.append(tid))
    monkeypatch.setattr(graph, "requeue_task", lambda tid, rc, rnb=None, fields=None: requeued.append(
        (tid, rc, rnb, fields)
    ))

    task = {"id": "t1", "business_id": "b-1", "runner_target": "business"}
    out = graph.resolve_business_repo_if_needed(
        RunnerState(current_task_id="t1", current_task=task)
    )

    assert failed == [], "an unreachable database must never mark a task terminally failed"
    assert out.stop_reason is None
    assert requeued and requeued[0][0] == "t1"
    assert requeued[0][3] == {"transient_retry_count": 1}
    assert out.retry_pending is True


def test_a_task_requeued_for_a_transient_failure_is_not_dispatched(monkeypatch):
    state = RunnerState(current_task_id="t1", retry_pending=True)
    assert graph._route_after_business_repo(state) == "decide_continue_or_stop"


def test_an_unreachable_database_parks_the_task_once_retries_are_spent(monkeypatch):
    blocked, failed = [], []
    monkeypatch.setattr(graph, "lookup_business", lambda bid: {
        "status": "unreachable", "business": None, "error": "connection refused", "signal": "connection",
    })
    monkeypatch.setattr(graph, "mark_task_blocked", lambda tid, err: blocked.append((tid, err)))
    monkeypatch.setattr(graph, "mark_task_failed", lambda tid, err: failed.append(tid))

    task = {
        "id": "t1", "business_id": "b-1", "runner_target": "business",
        "transient_retry_count": graph.cfg.max_transient_retries,
    }
    out = graph.resolve_business_repo_if_needed(
        RunnerState(current_task_id="t1", current_task=task)
    )

    assert failed == []
    assert blocked and blocked[0][0] == "t1"
    assert out.stop_reason is None
    assert graph._route_after_business_repo(out) == "decide_continue_or_stop"


def _stub_task_io(monkeypatch):
    calls = {"requeue": [], "failed": [], "blocked": [], "complete": []}
    monkeypatch.setattr(graph, "requeue_task",
                        lambda tid, rc, rnb=None, fields=None: calls["requeue"].append((tid, rc, fields)))
    monkeypatch.setattr(graph, "mark_task_failed", lambda tid, err: calls["failed"].append((tid, err)))
    monkeypatch.setattr(graph, "mark_task_blocked", lambda tid, err: calls["blocked"].append((tid, err)))
    monkeypatch.setattr(graph, "mark_task_complete", lambda tid, s: calls["complete"].append((tid, s)))
    return calls


def test_a_network_failure_never_marks_a_task_terminally_failed(monkeypatch):
    """Retries are exhausted, so the failure guard would give up and mark this
    task failed — terminal. A DNS error takes the network-pause path, which
    requeues the task without touching any counter (even better than transient)."""
    calls = _stub_task_io(monkeypatch)
    monkeypatch.setattr(graph.cfg, "max_task_retries", 1)
    monkeypatch.setattr(graph.cfg, "failure_guard_enabled", True)
    monkeypatch.setattr(graph.cfg, "state_self_healing_enabled", True)
    state = RunnerState(
        current_task_id="t1",
        current_task={"id": "t1", "title": "T", "retry_count": 5},
        worker_result={"success": False, "error": "Temporary failure in name resolution"},
    )
    out = graph.update_logs_and_state(state)
    assert calls["failed"] == []
    # Network-pause path: requeued with None extra (not transient metadata) and
    # retry_count is unchanged — the genuine-retry budget must not be spent.
    assert calls["requeue"] and calls["requeue"][0][1] == 5
    assert calls["requeue"][0][2] is None, "network-pause requeue must not touch transient metadata"
    assert out.retry_pending is True


def test_a_genuine_failure_with_no_retries_left_is_still_marked_failed(monkeypatch):
    calls = _stub_task_io(monkeypatch)
    monkeypatch.setattr(graph.cfg, "max_task_retries", 1)
    monkeypatch.setattr(graph.cfg, "failure_guard_enabled", True)
    monkeypatch.setattr(graph.cfg, "state_self_healing_enabled", True)
    state = RunnerState(
        current_task_id="t1",
        current_task={"id": "t1", "title": "T", "retry_count": 5},
        worker_result={"success": False, "error": "check.sh failed: 3 tests failing"},
    )
    graph.update_logs_and_state(state)
    assert [c[0] for c in calls["failed"]] == ["t1"]
    assert calls["requeue"] == []


def test_a_genuinely_missing_business_still_fails_the_task(monkeypatch):
    """Self-healing must not blunt a real error: a query that succeeded and
    found nothing is still a hard failure."""
    failed = []
    monkeypatch.setattr(graph, "lookup_business", lambda bid: {"status": "not_found", "business": None})
    monkeypatch.setattr(graph, "mark_task_failed", lambda tid, err: failed.append(tid))

    out = graph.resolve_business_repo_if_needed(RunnerState(
        current_task_id="t1",
        current_task={"id": "t1", "business_id": "b-1", "runner_target": "business"},
    ))
    assert out.stop_reason == "business_not_found"
    assert failed == ["t1"]
