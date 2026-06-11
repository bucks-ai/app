"""Unit tests for the failure & retry guard.

Runs standalone (no pytest dependency), mirroring test_resource_gate.py:

    python tests/test_failure_guard.py

Covers the pure decision helpers in tools/failure_guard.py and the
graph.update_logs_and_state node, plus the ask_chatgpt_next_task retry skip.
Task-queue mutations (requeue / mark_failed / mark_complete) and the flight
recorder are stubbed, so no real disk state under the runner is touched.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.failure_guard import (
    task_retry_count,
    evaluate_failure,
    CONSECUTIVE_FAILURES_STOP,
)
import graph
from state import RunnerState

# Silence the flight recorder and disk persistence during tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None


# ---------------------------------------------------------------------------
# Pure helper: task_retry_count
# ---------------------------------------------------------------------------

def test_retry_count_default_zero():
    assert task_retry_count(None) == 0
    assert task_retry_count({}) == 0


def test_retry_count_reads_value():
    assert task_retry_count({"retry_count": 2}) == 2


def test_retry_count_tolerates_garbage():
    assert task_retry_count({"retry_count": "x"}) == 0
    assert task_retry_count({"retry_count": None}) == 0
    assert task_retry_count({"retry_count": -3}) == 0


# ---------------------------------------------------------------------------
# Pure helper: evaluate_failure
# ---------------------------------------------------------------------------

def test_first_failure_retries():
    d = evaluate_failure({}, consecutive_failures=0, max_task_retries=1, max_consecutive_failures=3)
    assert d["action"] == "retry", d
    assert d["retry_count"] == 1, d
    assert d["consecutive_failures"] == 1, d
    assert d["circuit_open"] is False, d
    assert d["stop_reason"] is None, d


def test_gives_up_when_retries_exhausted():
    d = evaluate_failure({"retry_count": 1}, consecutive_failures=1, max_task_retries=1, max_consecutive_failures=5)
    assert d["action"] == "give_up", d
    assert d["retry_count"] == 1, d  # unchanged when giving up


def test_retries_disabled_gives_up_immediately():
    d = evaluate_failure({}, consecutive_failures=0, max_task_retries=0, max_consecutive_failures=3)
    assert d["action"] == "give_up", d


def test_circuit_opens_at_threshold():
    d = evaluate_failure({}, consecutive_failures=2, max_task_retries=5, max_consecutive_failures=3)
    assert d["consecutive_failures"] == 3, d
    assert d["circuit_open"] is True, d
    assert d["stop_reason"] == CONSECUTIVE_FAILURES_STOP, d


def test_circuit_disabled_when_threshold_non_positive():
    d = evaluate_failure({}, consecutive_failures=99, max_task_retries=1, max_consecutive_failures=0)
    assert d["circuit_open"] is False, d
    assert d["stop_reason"] is None, d


def test_retry_and_circuit_are_independent():
    # A task with retries remaining can still trip the breaker on the same failure.
    d = evaluate_failure({}, consecutive_failures=2, max_task_retries=2, max_consecutive_failures=3)
    assert d["action"] == "retry", d
    assert d["circuit_open"] is True, d


# ---------------------------------------------------------------------------
# Node behavior — graph.update_logs_and_state
# ---------------------------------------------------------------------------

def _with_stubbed_task_io(fn):
    """Run fn(calls) with task-queue mutations captured instead of hitting disk."""
    calls = {"requeue": [], "failed": [], "complete": []}
    orig = (graph.requeue_task, graph.mark_task_failed, graph.mark_task_complete)
    graph.requeue_task = lambda task_id, rc: calls["requeue"].append((task_id, rc))
    graph.mark_task_failed = lambda task_id, err: calls["failed"].append((task_id, err))
    graph.mark_task_complete = lambda task_id, summary: calls["complete"].append((task_id, summary))
    try:
        return fn(calls)
    finally:
        graph.requeue_task, graph.mark_task_failed, graph.mark_task_complete = orig


def _failed_state(task, consecutive=0):
    return RunnerState(
        current_task_id=task["id"],
        current_task=task,
        worker_result={"success": False, "error": "boom"},
        consecutive_failures=consecutive,
    )


def test_node_requeues_on_first_failure():
    def body(calls):
        graph.cfg.failure_guard_enabled = True
        graph.cfg.max_task_retries = 1
        graph.cfg.max_consecutive_failures = 3
        out = graph.update_logs_and_state(_failed_state({"id": "t1"}))
        assert calls["requeue"] == [("t1", 1)], calls
        assert calls["failed"] == [], calls
        assert out.retry_pending is True, out.retry_pending
        assert out.consecutive_failures == 1, out.consecutive_failures
        assert out.stop_reason is None, out.stop_reason
    _with_stubbed_task_io(body)


def test_node_marks_failed_when_retries_exhausted():
    def body(calls):
        graph.cfg.failure_guard_enabled = True
        graph.cfg.max_task_retries = 1
        graph.cfg.max_consecutive_failures = 3
        out = graph.update_logs_and_state(_failed_state({"id": "t1", "retry_count": 1}))
        assert calls["requeue"] == [], calls
        assert calls["failed"] == [("t1", "boom")], calls
        assert out.retry_pending is False, out.retry_pending
    _with_stubbed_task_io(body)


def test_node_circuit_breaker_sets_stop_reason():
    def body(calls):
        graph.cfg.failure_guard_enabled = True
        graph.cfg.max_task_retries = 5
        graph.cfg.max_consecutive_failures = 3
        out = graph.update_logs_and_state(_failed_state({"id": "t1"}, consecutive=2))
        assert out.consecutive_failures == 3, out.consecutive_failures
        assert out.stop_reason == CONSECUTIVE_FAILURES_STOP, out.stop_reason
        # Still requeued for the next run even though this run halts.
        assert calls["requeue"] == [("t1", 1)], calls
    _with_stubbed_task_io(body)


def test_node_success_resets_consecutive_failures():
    def body(calls):
        graph.cfg.failure_guard_enabled = True
        s = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1"},
            worker_result={"success": True},
            consecutive_failures=2,
        )
        out = graph.update_logs_and_state(s)
        assert out.consecutive_failures == 0, out.consecutive_failures
        assert out.retry_pending is False, out.retry_pending
        assert calls["complete"] and calls["complete"][0][0] == "t1", calls
    _with_stubbed_task_io(body)


def test_node_disabled_guard_falls_back_to_mark_failed():
    def body(calls):
        graph.cfg.failure_guard_enabled = False
        try:
            out = graph.update_logs_and_state(_failed_state({"id": "t1"}, consecutive=5))
            assert calls["failed"] == [("t1", "boom")], calls
            assert calls["requeue"] == [], calls
            assert out.stop_reason is None, out.stop_reason
            # Counter untouched when the guard is off.
            assert out.consecutive_failures == 5, out.consecutive_failures
        finally:
            graph.cfg.failure_guard_enabled = True
    _with_stubbed_task_io(body)


# ---------------------------------------------------------------------------
# ask_chatgpt_next_task skips when a retry is pending
# ---------------------------------------------------------------------------

def test_ask_next_task_skips_when_retry_pending():
    asked = []
    orig = graph.ChatGPTWorker

    class _Planner:
        def ask_for_next_task(self, summary):
            asked.append(summary)
            return {"id": "new", "title": "should not be asked"}

    graph.ChatGPTWorker = _Planner
    try:
        out = graph.ask_chatgpt_next_task(RunnerState(retry_pending=True))
        assert asked == [], "planner must not be asked while a retry is pending"
        assert out.stop_reason is None, out.stop_reason
    finally:
        graph.ChatGPTWorker = orig


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

def test_stop_reason_constant_surfaces_in_stop():
    s = RunnerState(stop_reason=CONSECUTIVE_FAILURES_STOP)
    out = graph.decide_continue_or_stop(s)
    assert out.status == "stopped", out.status


if __name__ == "__main__":
    tests = [
        test_retry_count_default_zero,
        test_retry_count_reads_value,
        test_retry_count_tolerates_garbage,
        test_first_failure_retries,
        test_gives_up_when_retries_exhausted,
        test_retries_disabled_gives_up_immediately,
        test_circuit_opens_at_threshold,
        test_circuit_disabled_when_threshold_non_positive,
        test_retry_and_circuit_are_independent,
        test_node_requeues_on_first_failure,
        test_node_marks_failed_when_retries_exhausted,
        test_node_circuit_breaker_sets_stop_reason,
        test_node_success_resets_consecutive_failures,
        test_node_disabled_guard_falls_back_to_mark_failed,
        test_ask_next_task_skips_when_retry_pending,
        test_stop_reason_constant_surfaces_in_stop,
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
