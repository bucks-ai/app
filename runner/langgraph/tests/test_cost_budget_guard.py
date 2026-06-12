"""Unit tests for the cost and budget tracking guard.

Runs standalone (no pytest dependency), mirroring test_worker_timeout_guard.py:

    python tests/test_cost_budget_guard.py

Covers the pure decision helper in tools/cost_budget_guard.py and the
graph.update_logs_and_state node integration. Task-queue mutations and the
flight recorder are stubbed, so no real disk state under the runner is touched.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.cost_budget_guard import evaluate_cost_budget, COST_BUDGET_STOP
import graph
from state import RunnerState

# Silence the flight recorder and disk persistence during tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None


# ---------------------------------------------------------------------------
# Pure helper: evaluate_cost_budget
# ---------------------------------------------------------------------------

def test_both_limits_zero_never_blocked():
    r = evaluate_cost_budget(
        task_cost=999.0,
        session_cost=999.0,
        max_session_cost=0.0,
        max_task_cost=0.0,
    )
    assert r["blocked"] is False
    assert r["stop_reason"] is None
    assert r["task_exceeded"] is False
    assert r["session_exceeded"] is False


def test_session_cost_accumulates():
    r = evaluate_cost_budget(
        task_cost=3.0,
        session_cost=5.0,
        max_session_cost=0.0,
        max_task_cost=0.0,
    )
    assert r["session_cost"] == 8.0


def test_task_cost_zero_no_block():
    r = evaluate_cost_budget(
        task_cost=0.0,
        session_cost=0.0,
        max_session_cost=10.0,
        max_task_cost=5.0,
    )
    assert r["blocked"] is False
    assert r["session_cost"] == 0.0


def test_task_exceeded_blocks():
    r = evaluate_cost_budget(
        task_cost=6.0,
        session_cost=0.0,
        max_session_cost=0.0,
        max_task_cost=5.0,
    )
    assert r["task_exceeded"] is True
    assert r["blocked"] is True
    assert r["stop_reason"] == COST_BUDGET_STOP


def test_task_exactly_at_limit_not_blocked():
    r = evaluate_cost_budget(
        task_cost=5.0,
        session_cost=0.0,
        max_session_cost=0.0,
        max_task_cost=5.0,
    )
    assert r["task_exceeded"] is False
    assert r["blocked"] is False


def test_session_exceeded_blocks():
    r = evaluate_cost_budget(
        task_cost=2.0,
        session_cost=9.0,
        max_session_cost=10.0,
        max_task_cost=0.0,
    )
    assert r["session_exceeded"] is True
    assert r["blocked"] is True
    assert r["stop_reason"] == COST_BUDGET_STOP
    assert r["session_cost"] == 11.0


def test_session_exactly_at_limit_blocked():
    r = evaluate_cost_budget(
        task_cost=1.0,
        session_cost=9.0,
        max_session_cost=10.0,
        max_task_cost=0.0,
    )
    assert r["session_exceeded"] is True
    assert r["blocked"] is True


def test_session_below_limit_not_blocked():
    r = evaluate_cost_budget(
        task_cost=1.0,
        session_cost=8.0,
        max_session_cost=10.0,
        max_task_cost=0.0,
    )
    assert r["session_exceeded"] is False
    assert r["blocked"] is False
    assert r["session_cost"] == 9.0


def test_both_exceeded_blocked_once():
    r = evaluate_cost_budget(
        task_cost=10.0,
        session_cost=5.0,
        max_session_cost=10.0,
        max_task_cost=5.0,
    )
    assert r["task_exceeded"] is True
    assert r["session_exceeded"] is True
    assert r["blocked"] is True
    assert r["stop_reason"] == COST_BUDGET_STOP


def test_session_cost_zero_no_session_block():
    r = evaluate_cost_budget(
        task_cost=0.0,
        session_cost=0.0,
        max_session_cost=50.0,
        max_task_cost=10.0,
    )
    assert r["blocked"] is False
    assert r["session_cost"] == 0.0


# ---------------------------------------------------------------------------
# Node behavior — graph.update_logs_and_state
# ---------------------------------------------------------------------------

def _with_stubbed_task_io(fn):
    calls = {"requeue": [], "failed": [], "complete": []}
    orig = (graph.requeue_task, graph.mark_task_failed, graph.mark_task_complete)
    graph.requeue_task = lambda task_id, rc: calls["requeue"].append((task_id, rc))
    graph.mark_task_failed = lambda task_id, err: calls["failed"].append((task_id, err))
    graph.mark_task_complete = lambda task_id, s: calls["complete"].append((task_id, s))
    try:
        return fn(calls)
    finally:
        graph.requeue_task, graph.mark_task_failed, graph.mark_task_complete = orig


def _cost_state(task_id="t1", session_cost=0.0, api_cost=None, success=True):
    return RunnerState(
        current_task_id=task_id,
        current_task={"id": task_id},
        worker_result={"success": success, "api_cost": api_cost},
        session_cost=session_cost,
    )


def test_node_accumulates_estimated_cost():
    def body(calls):
        graph.cfg.cost_budget_guard_enabled = True
        graph.cfg.max_session_cost_dollars = 0.0
        graph.cfg.max_task_cost_dollars = 0.0
        graph.cfg.estimated_cost_per_task_dollars = 2.0
        graph.cfg.failure_guard_enabled = False
        s = _cost_state(session_cost=5.0, api_cost=None)
        out = graph.update_logs_and_state(s)
        assert out.session_cost == 7.0, out.session_cost
        assert out.stop_reason is None, out.stop_reason
    _with_stubbed_task_io(body)


def test_node_uses_api_cost_over_estimate():
    def body(calls):
        graph.cfg.cost_budget_guard_enabled = True
        graph.cfg.max_session_cost_dollars = 0.0
        graph.cfg.max_task_cost_dollars = 0.0
        graph.cfg.estimated_cost_per_task_dollars = 2.0
        graph.cfg.failure_guard_enabled = False
        s = _cost_state(session_cost=0.0, api_cost=3.5)
        out = graph.update_logs_and_state(s)
        assert out.session_cost == 3.5, out.session_cost
    _with_stubbed_task_io(body)


def test_node_session_budget_exceeded_sets_stop_reason():
    def body(calls):
        graph.cfg.cost_budget_guard_enabled = True
        graph.cfg.max_session_cost_dollars = 10.0
        graph.cfg.max_task_cost_dollars = 0.0
        graph.cfg.estimated_cost_per_task_dollars = 3.0
        graph.cfg.failure_guard_enabled = False
        s = _cost_state(session_cost=9.0, api_cost=None)
        out = graph.update_logs_and_state(s)
        assert out.session_cost == 12.0, out.session_cost
        assert out.stop_reason == COST_BUDGET_STOP, out.stop_reason
    _with_stubbed_task_io(body)


def test_node_task_budget_exceeded_sets_stop_reason():
    def body(calls):
        graph.cfg.cost_budget_guard_enabled = True
        graph.cfg.max_session_cost_dollars = 0.0
        graph.cfg.max_task_cost_dollars = 5.0
        graph.cfg.estimated_cost_per_task_dollars = 0.0
        graph.cfg.failure_guard_enabled = False
        s = _cost_state(session_cost=0.0, api_cost=6.0)
        out = graph.update_logs_and_state(s)
        assert out.stop_reason == COST_BUDGET_STOP, out.stop_reason
    _with_stubbed_task_io(body)


def test_node_guard_disabled_no_accumulation():
    def body(calls):
        graph.cfg.cost_budget_guard_enabled = False
        graph.cfg.failure_guard_enabled = False
        s = _cost_state(session_cost=5.0, api_cost=10.0)
        out = graph.update_logs_and_state(s)
        assert out.session_cost == 5.0, out.session_cost
        assert out.stop_reason is None, out.stop_reason
    _with_stubbed_task_io(body)


def test_node_cost_accumulates_on_failure():
    def body(calls):
        graph.cfg.cost_budget_guard_enabled = True
        graph.cfg.max_session_cost_dollars = 0.0
        graph.cfg.max_task_cost_dollars = 0.0
        graph.cfg.estimated_cost_per_task_dollars = 1.5
        graph.cfg.failure_guard_enabled = False
        s = _cost_state(session_cost=2.0, api_cost=None, success=False)
        out = graph.update_logs_and_state(s)
        assert out.session_cost == 3.5, out.session_cost
    _with_stubbed_task_io(body)


def test_node_zero_cost_no_accumulation():
    def body(calls):
        graph.cfg.cost_budget_guard_enabled = True
        graph.cfg.max_session_cost_dollars = 10.0
        graph.cfg.max_task_cost_dollars = 5.0
        graph.cfg.estimated_cost_per_task_dollars = 0.0
        graph.cfg.failure_guard_enabled = False
        s = _cost_state(session_cost=9.0, api_cost=None)
        out = graph.update_logs_and_state(s)
        assert out.session_cost == 9.0, out.session_cost
        assert out.stop_reason is None, out.stop_reason
    _with_stubbed_task_io(body)


def test_stop_reason_constant_surfaces_in_decide():
    s = RunnerState(stop_reason=COST_BUDGET_STOP)
    out = graph.decide_continue_or_stop(s)
    assert out.status == "stopped", out.status


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_both_limits_zero_never_blocked,
        test_session_cost_accumulates,
        test_task_cost_zero_no_block,
        test_task_exceeded_blocks,
        test_task_exactly_at_limit_not_blocked,
        test_session_exceeded_blocks,
        test_session_exactly_at_limit_blocked,
        test_session_below_limit_not_blocked,
        test_both_exceeded_blocked_once,
        test_session_cost_zero_no_session_block,
        test_node_accumulates_estimated_cost,
        test_node_uses_api_cost_over_estimate,
        test_node_session_budget_exceeded_sets_stop_reason,
        test_node_task_budget_exceeded_sets_stop_reason,
        test_node_guard_disabled_no_accumulation,
        test_node_cost_accumulates_on_failure,
        test_node_zero_cost_no_accumulation,
        test_stop_reason_constant_surfaces_in_decide,
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
