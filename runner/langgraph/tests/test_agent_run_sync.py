"""Unit tests for the Agent Runs sync module (tools/agent_run_sync.py) and its
wiring into graph.resolve_model_node / graph.update_logs_and_state.

Runs standalone (no pytest dependency):

    python tests/test_agent_run_sync.py

Covers:
  - ``resolve_agent_identity`` pure task-type -> (agent_id, node_id) mapping
  - ``start_agent_run`` / ``complete_agent_run`` / ``fail_agent_run`` against a
    stubbed Supabase client (insert/update payload shape, silent degradation)
  - Graph node integration: start (resolve_model_node), complete and fail
    (update_logs_and_state) transitions for seeded-mission tasks only
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tools.agent_run_sync as ars
from tools.agent_run_sync import (
    resolve_agent_identity,
    start_agent_run,
    complete_agent_run,
    fail_agent_run,
    DEFAULT_AGENT_ID,
)
import graph
from state import RunnerState

# Silence flight recorder and disk persistence during all tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None
ars.log_event = lambda *a, **k: None


# ---------------------------------------------------------------------------
# Pure helper: resolve_agent_identity
# ---------------------------------------------------------------------------

def test_backend_maps_to_engineering_brain():
    agent_id, node_id = resolve_agent_identity("backend")
    assert agent_id == "engineering_brain"
    assert node_id == "orchestration"


def test_infra_and_test_map_to_engineering_brain():
    assert resolve_agent_identity("infra")[0] == "engineering_brain"
    assert resolve_agent_identity("test")[0] == "engineering_brain"


def test_frontend_ui_design_polish_map_to_product_brain():
    for t in ("frontend", "ui", "design", "polish"):
        assert resolve_agent_identity(t)[0] == "product_brain", t


def test_docs_maps_to_ops_brain():
    assert resolve_agent_identity("docs")[0] == "ops_brain"


def test_general_maps_to_default_agent():
    assert resolve_agent_identity("general")[0] == DEFAULT_AGENT_ID


def test_unknown_type_falls_back_to_default():
    assert resolve_agent_identity("something-new")[0] == DEFAULT_AGENT_ID


def test_none_type_falls_back_to_default():
    assert resolve_agent_identity(None)[0] == DEFAULT_AGENT_ID


def test_mapping_is_case_insensitive():
    assert resolve_agent_identity("BACKEND")[0] == "engineering_brain"


# ---------------------------------------------------------------------------
# Fake Supabase client
# ---------------------------------------------------------------------------

class _FakeResult:
    def __init__(self, data):
        self.data = data


class _FakeQuery:
    def __init__(self, calls, insert_return=None, raise_exc=None):
        self._calls = calls
        self._insert_return = insert_return
        self._raise_exc = raise_exc
        self._op = None
        self._payload = None
        self._filters = {}

    def insert(self, payload):
        self._op = "insert"
        self._payload = payload
        return self

    def update(self, payload):
        self._op = "update"
        self._payload = payload
        return self

    def eq(self, col, val):
        self._filters[col] = val
        return self

    def execute(self):
        self._calls.append({"op": self._op, "payload": self._payload, "filters": dict(self._filters)})
        if self._raise_exc:
            raise self._raise_exc
        if self._op == "insert":
            return _FakeResult(self._insert_return if self._insert_return is not None else [])
        return _FakeResult([])


class _FakeClient:
    def __init__(self, calls, insert_return=None, raise_exc=None):
        self._calls = calls
        self._insert_return = insert_return
        self._raise_exc = raise_exc

    def table(self, name):
        return _FakeQuery(self._calls, self._insert_return, self._raise_exc)


def _with_stub(fn, insert_return=None, raise_exc=None, has_supabase=True):
    calls = []
    original_client = ars._get_client
    original_has_supabase = ars._has_supabase
    ars._get_client = lambda: _FakeClient(calls, insert_return=insert_return, raise_exc=raise_exc)
    ars._has_supabase = lambda: has_supabase
    try:
        return fn(calls)
    finally:
        ars._get_client = original_client
        ars._has_supabase = original_has_supabase


_SEEDED_TASK = {
    "id": "task-1",
    "title": "Fix the thing",
    "type": "backend",
    "branch": "feature/x",
    "mission": "Test Mission",
    "seeded_mission_id": "mission-uuid-1",
    "seeded_task_id": "task-uuid-1",
    "business_id": "biz-uuid-1",
    "user_id": "user-uuid-1",
}


# ---------------------------------------------------------------------------
# start_agent_run
# ---------------------------------------------------------------------------

def test_start_no_supabase_returns_none_and_skips_client():
    def body(calls):
        run_id = start_agent_run(_SEEDED_TASK)
        assert run_id is None
        assert calls == []
    _with_stub(body, has_supabase=False)


def test_start_missing_business_id_returns_none():
    def body(calls):
        task = dict(_SEEDED_TASK)
        del task["business_id"]
        run_id = start_agent_run(task)
        assert run_id is None
        assert calls == []
    _with_stub(body)


def test_start_missing_user_id_returns_none():
    def body(calls):
        task = dict(_SEEDED_TASK)
        del task["user_id"]
        run_id = start_agent_run(task)
        assert run_id is None
        assert calls == []
    _with_stub(body)


def test_start_success_returns_id():
    def body(calls):
        run_id = start_agent_run(_SEEDED_TASK)
        assert run_id == "run-uuid-1"
        assert len(calls) == 1
    _with_stub(body, insert_return=[{"id": "run-uuid-1"}])


def test_start_inserts_running_status_and_mapped_agent():
    def body(calls):
        start_agent_run(_SEEDED_TASK)
        payload = calls[0]["payload"]
        assert payload["status"] == "running"
        assert payload["source"] == "workflow"
        assert payload["agent_id"] == "engineering_brain"
        assert payload["node_id"] == "orchestration"
        assert payload["business_id"] == "biz-uuid-1"
        assert payload["user_id"] == "user-uuid-1"
        assert payload["title"] == "Fix the thing"
        assert payload["started_at"] is not None
        assert payload["input"]["seeded_task_id"] == "task-uuid-1"
        assert payload["input"]["seeded_mission_id"] == "mission-uuid-1"
    _with_stub(body, insert_return=[{"id": "run-uuid-1"}])


def test_start_falls_back_to_task_id_when_title_missing():
    def body(calls):
        task = dict(_SEEDED_TASK)
        del task["title"]
        start_agent_run(task)
        assert calls[0]["payload"]["title"] == "task-1"
    _with_stub(body, insert_return=[{"id": "run-uuid-1"}])


def test_start_returns_none_when_insert_empty():
    def body(calls):
        run_id = start_agent_run(_SEEDED_TASK)
        assert run_id is None
    _with_stub(body, insert_return=[])


def test_start_swallows_exception_and_returns_none():
    def body(calls):
        run_id = start_agent_run(_SEEDED_TASK)
        assert run_id is None
    _with_stub(body, raise_exc=RuntimeError("boom"))


# ---------------------------------------------------------------------------
# complete_agent_run / fail_agent_run
# ---------------------------------------------------------------------------

def test_complete_no_run_id_is_noop():
    def body(calls):
        result = complete_agent_run(None, "done")
        assert result == {"success": False}
        assert calls == []
    _with_stub(body)


def test_complete_no_supabase_is_noop():
    def body(calls):
        result = complete_agent_run("run-uuid-1", "done")
        assert result == {"success": False}
        assert calls == []
    _with_stub(body, has_supabase=False)


def test_complete_success_updates_status_and_metrics():
    def body(calls):
        result = complete_agent_run(
            "run-uuid-1",
            "All good",
            output={"files_modified": ["a.py"]},
            cost_usd=0.42,
            duration_seconds=12.5,
        )
        assert result == {"success": True}
        payload = calls[0]["payload"]
        assert payload["status"] == "completed"
        assert payload["summary"] == "All good"
        assert payload["cost_usd"] == 0.42
        assert payload["duration_seconds"] == 12.5
        assert payload["output"] == {"files_modified": ["a.py"]}
        assert calls[0]["filters"] == {"id": "run-uuid-1"}
    _with_stub(body)


def test_complete_without_optional_metrics_omits_them():
    def body(calls):
        complete_agent_run("run-uuid-1", "All good")
        payload = calls[0]["payload"]
        assert "cost_usd" not in payload
        assert "duration_seconds" not in payload
        assert "output" not in payload
    _with_stub(body)


def test_complete_swallows_exception():
    def body(calls):
        result = complete_agent_run("run-uuid-1", "All good")
        assert result["success"] is False
    _with_stub(body, raise_exc=RuntimeError("boom"))


def test_fail_no_run_id_is_noop():
    def body(calls):
        result = fail_agent_run(None, "it broke")
        assert result == {"success": False}
        assert calls == []
    _with_stub(body)


def test_fail_success_sets_status_and_error():
    def body(calls):
        result = fail_agent_run("run-uuid-1", "it broke", cost_usd=1.0, duration_seconds=5.0)
        assert result == {"success": True}
        payload = calls[0]["payload"]
        assert payload["status"] == "failed"
        assert payload["summary"] == "it broke"
        assert payload["error"] == {"code": "worker_failed", "message": "it broke"}
        assert payload["cost_usd"] == 1.0
        assert payload["duration_seconds"] == 5.0
    _with_stub(body)


# ---------------------------------------------------------------------------
# Graph integration: resolve_model_node (start) + update_logs_and_state
# (complete, fail) — only for seeded-mission tasks.
# ---------------------------------------------------------------------------

def _stub_agent_run_sync(started_return="run-uuid-9"):
    calls = {"start": [], "complete": [], "fail": []}
    orig = (graph.start_agent_run, graph.complete_agent_run, graph.fail_agent_run)
    graph.start_agent_run = lambda task: (calls["start"].append(task) or started_return)
    graph.complete_agent_run = lambda run_id, summary, **kw: (
        calls["complete"].append((run_id, summary, kw)) or {"success": True}
    )
    graph.fail_agent_run = lambda run_id, err, **kw: (
        calls["fail"].append((run_id, err, kw)) or {"success": True}
    )
    return calls, orig


def _restore_agent_run_sync(orig):
    graph.start_agent_run, graph.complete_agent_run, graph.fail_agent_run = orig


def _with_stubbed_task_io(fn):
    """Stub out task-queue + seeded-mission Supabase side effects used by
    update_logs_and_state so only agent_run_sync behavior is under test."""
    calls = {"complete_task": [], "failed_task": []}
    orig = (
        graph.mark_task_complete,
        graph.mark_task_failed,
        graph.mark_seeded_task_complete,
        graph.mark_seeded_task_failed,
        graph.check_mission_completion,
        graph.mark_mission_completed,
        graph.mark_mission_failed,
    )
    graph.mark_task_complete = lambda tid, s: calls["complete_task"].append((tid, s))
    graph.mark_task_failed = lambda tid, e: calls["failed_task"].append((tid, e))
    graph.mark_seeded_task_complete = lambda sid, s: None
    graph.mark_seeded_task_failed = lambda sid, e: None
    graph.check_mission_completion = lambda mid: {"status": "in_progress"}
    graph.mark_mission_completed = lambda mid: None
    graph.mark_mission_failed = lambda mid: None
    try:
        return fn(calls)
    finally:
        (
            graph.mark_task_complete,
            graph.mark_task_failed,
            graph.mark_seeded_task_complete,
            graph.mark_seeded_task_failed,
            graph.check_mission_completion,
            graph.mark_mission_completed,
            graph.mark_mission_failed,
        ) = orig


def _disable_other_guards():
    """Turn off every other update_logs_and_state guard so only the seeded
    mission sync block under test can set stop_reason or make extra calls."""
    graph.cfg.failure_guard_enabled = False
    graph.cfg.cost_budget_guard_enabled = False
    graph.cfg.stale_run_watchdog_enabled = False
    graph.cfg.worker_timeout_guard_enabled = False
    graph.cfg.codex_usage_limit_guard_enabled = False
    graph.cfg.claude_subscription_cooldown_enabled = False
    graph.cfg.seeded_mission_queue_enabled = True


def test_resolve_model_starts_run_for_seeded_task():
    calls, orig = _stub_agent_run_sync(started_return="run-uuid-9")
    try:
        state = RunnerState(
            current_task=dict(_SEEDED_TASK),
            current_worker="claude",
        )
        out = graph.resolve_model_node(state)
        assert len(calls["start"]) == 1
        assert calls["start"][0]["id"] == "task-1"
        assert out.current_agent_run_id == "run-uuid-9"
    finally:
        _restore_agent_run_sync(orig)


def test_resolve_model_skips_non_seeded_task():
    calls, orig = _stub_agent_run_sync()
    try:
        state = RunnerState(
            current_task={"id": "adhoc-1", "title": "Ad-hoc task", "type": "backend"},
            current_worker="claude",
        )
        out = graph.resolve_model_node(state)
        assert calls["start"] == []
        assert out.current_agent_run_id is None
    finally:
        _restore_agent_run_sync(orig)


def _seeded_state(success, run_id="run-uuid-9", api_cost=1.23, elapsed=42.0):
    return RunnerState(
        current_task_id="task-1",
        current_task=dict(_SEEDED_TASK),
        worker_result={"success": success, "api_cost": api_cost, "error": None if success else "boom"},
        worker_summary={"files_modified": ["a.py"]} if success else None,
        worker_elapsed_seconds=elapsed,
        current_agent_run_id=run_id,
    )


def test_update_logs_completes_run_on_success():
    calls, orig = _stub_agent_run_sync()
    try:
        type(graph.cfg).has_supabase = property(lambda self: True)

        def body(_task_calls):
            _disable_other_guards()
            state = _seeded_state(success=True)
            out = graph.update_logs_and_state(state)
            assert len(calls["complete"]) == 1
            run_id, summary, kw = calls["complete"][0]
            assert run_id == "run-uuid-9"
            assert kw["cost_usd"] == 1.23
            assert kw["duration_seconds"] == 42.0
            assert kw["output"] == {"files_modified": ["a.py"]}
            assert calls["fail"] == []
            assert out.current_agent_run_id is None
        _with_stubbed_task_io(body)
    finally:
        original_has_supabase = property(
            lambda self: bool(graph.cfg.supabase_url and graph.cfg.supabase_service_role_key)
        )
        type(graph.cfg).has_supabase = original_has_supabase
        _restore_agent_run_sync(orig)


def test_update_logs_fails_run_on_failure():
    calls, orig = _stub_agent_run_sync()
    try:
        type(graph.cfg).has_supabase = property(lambda self: True)

        def body(_task_calls):
            _disable_other_guards()
            state = _seeded_state(success=False)
            out = graph.update_logs_and_state(state)
            assert len(calls["fail"]) == 1
            run_id, err, kw = calls["fail"][0]
            assert run_id == "run-uuid-9"
            assert err == "boom"
            assert kw["cost_usd"] == 1.23
            assert kw["duration_seconds"] == 42.0
            assert calls["complete"] == []
            assert out.current_agent_run_id is None
        _with_stubbed_task_io(body)
    finally:
        original_has_supabase = property(
            lambda self: bool(graph.cfg.supabase_url and graph.cfg.supabase_service_role_key)
        )
        type(graph.cfg).has_supabase = original_has_supabase
        _restore_agent_run_sync(orig)


def test_update_logs_skips_agent_run_sync_for_non_seeded_task():
    calls, orig = _stub_agent_run_sync()
    try:
        type(graph.cfg).has_supabase = property(lambda self: True)

        def body(_task_calls):
            _disable_other_guards()
            state = RunnerState(
                current_task_id="adhoc-1",
                current_task={"id": "adhoc-1", "title": "Ad-hoc"},
                worker_result={"success": True, "api_cost": None},
                current_agent_run_id=None,
            )
            graph.update_logs_and_state(state)
            assert calls["complete"] == []
            assert calls["fail"] == []
        _with_stubbed_task_io(body)
    finally:
        original_has_supabase = property(
            lambda self: bool(graph.cfg.supabase_url and graph.cfg.supabase_service_role_key)
        )
        type(graph.cfg).has_supabase = original_has_supabase
        _restore_agent_run_sync(orig)


def test_update_logs_resets_agent_run_id_even_without_supabase():
    """Scratch-field reset at the end of the node must always clear
    current_agent_run_id, regardless of whether the sync block ran."""
    calls, orig = _stub_agent_run_sync()
    try:
        type(graph.cfg).has_supabase = property(lambda self: False)

        def body(_task_calls):
            _disable_other_guards()
            state = _seeded_state(success=True)
            out = graph.update_logs_and_state(state)
            assert calls["complete"] == []
            assert out.current_agent_run_id is None
        _with_stubbed_task_io(body)
    finally:
        original_has_supabase = property(
            lambda self: bool(graph.cfg.supabase_url and graph.cfg.supabase_service_role_key)
        )
        type(graph.cfg).has_supabase = original_has_supabase
        _restore_agent_run_sync(orig)


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_backend_maps_to_engineering_brain,
        test_infra_and_test_map_to_engineering_brain,
        test_frontend_ui_design_polish_map_to_product_brain,
        test_docs_maps_to_ops_brain,
        test_general_maps_to_default_agent,
        test_unknown_type_falls_back_to_default,
        test_none_type_falls_back_to_default,
        test_mapping_is_case_insensitive,
        test_start_no_supabase_returns_none_and_skips_client,
        test_start_missing_business_id_returns_none,
        test_start_missing_user_id_returns_none,
        test_start_success_returns_id,
        test_start_inserts_running_status_and_mapped_agent,
        test_start_falls_back_to_task_id_when_title_missing,
        test_start_returns_none_when_insert_empty,
        test_start_swallows_exception_and_returns_none,
        test_complete_no_run_id_is_noop,
        test_complete_no_supabase_is_noop,
        test_complete_success_updates_status_and_metrics,
        test_complete_without_optional_metrics_omits_them,
        test_complete_swallows_exception,
        test_fail_no_run_id_is_noop,
        test_fail_success_sets_status_and_error,
        test_resolve_model_starts_run_for_seeded_task,
        test_resolve_model_skips_non_seeded_task,
        test_update_logs_completes_run_on_success,
        test_update_logs_fails_run_on_failure,
        test_update_logs_skips_agent_run_sync_for_non_seeded_task,
        test_update_logs_resets_agent_run_id_even_without_supabase,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
