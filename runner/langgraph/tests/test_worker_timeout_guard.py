"""Unit tests for the worker timeout guard.

Runs standalone (no pytest dependency), mirroring test_failure_guard.py:

    python tests/test_worker_timeout_guard.py

Covers the pure decision helpers in tools/worker_timeout_guard.py and the
graph.update_logs_and_state node integration. Task-queue mutations and the
flight recorder are stubbed, so no real disk state under the runner is touched.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.worker_timeout_guard import (
    _is_timeout_error,
    evaluate_worker_timeout,
    WORKER_TIMEOUT_STOP,
)
import graph
from state import RunnerState

# Silence the flight recorder and disk persistence during tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None


# ---------------------------------------------------------------------------
# Pure helper: _is_timeout_error
# ---------------------------------------------------------------------------

def test_is_timeout_error_matches_run_command_message():
    assert _is_timeout_error("Command timed out after 600s") is True


def test_is_timeout_error_matches_case_insensitive():
    assert _is_timeout_error("TIMED OUT AFTER 300s") is True


def test_is_timeout_error_matches_timeout_expired():
    assert _is_timeout_error("timeout expired") is True


def test_is_timeout_error_false_for_unrelated_error():
    assert _is_timeout_error("ModuleNotFoundError: no module named foo") is False


def test_is_timeout_error_false_for_none():
    assert _is_timeout_error(None) is False


def test_is_timeout_error_false_for_empty_string():
    assert _is_timeout_error("") is False


# ---------------------------------------------------------------------------
# Pure helper: evaluate_worker_timeout
# ---------------------------------------------------------------------------

def test_guard_disabled_when_max_zero():
    r = evaluate_worker_timeout(
        elapsed_seconds=700,
        error="Command timed out after 600s",
        timeout_count=10,
        max_worker_timeouts=0,
        worker_timeout_threshold=570,
    )
    assert r["timed_out"] is False
    assert r["blocked"] is False
    assert r["stop_reason"] is None
    assert r["timeout_count"] == 10  # unchanged


def test_elapsed_triggers_timeout():
    r = evaluate_worker_timeout(
        elapsed_seconds=580,
        error=None,
        timeout_count=0,
        max_worker_timeouts=3,
        worker_timeout_threshold=570,
    )
    assert r["timed_out"] is True
    assert r["timeout_count"] == 1
    assert r["blocked"] is False


def test_elapsed_below_threshold_not_timeout():
    r = evaluate_worker_timeout(
        elapsed_seconds=400,
        error=None,
        timeout_count=0,
        max_worker_timeouts=3,
        worker_timeout_threshold=570,
    )
    assert r["timed_out"] is False
    assert r["timeout_count"] == 0


def test_error_text_triggers_timeout():
    r = evaluate_worker_timeout(
        elapsed_seconds=10,
        error="Command timed out after 600s",
        timeout_count=0,
        max_worker_timeouts=3,
        worker_timeout_threshold=570,
    )
    assert r["timed_out"] is True
    assert r["timeout_count"] == 1


def test_neither_signal_no_timeout():
    r = evaluate_worker_timeout(
        elapsed_seconds=30,
        error="SomeOtherError",
        timeout_count=2,
        max_worker_timeouts=3,
        worker_timeout_threshold=570,
    )
    assert r["timed_out"] is False
    assert r["timeout_count"] == 2


def test_elapsed_none_does_not_count_as_timeout():
    r = evaluate_worker_timeout(
        elapsed_seconds=None,
        error=None,
        timeout_count=0,
        max_worker_timeouts=3,
        worker_timeout_threshold=570,
    )
    assert r["timed_out"] is False


def test_threshold_zero_disables_elapsed_check():
    r = evaluate_worker_timeout(
        elapsed_seconds=9999,
        error=None,
        timeout_count=0,
        max_worker_timeouts=3,
        worker_timeout_threshold=0,
    )
    assert r["timed_out"] is False


def test_blocked_at_max():
    r = evaluate_worker_timeout(
        elapsed_seconds=600,
        error=None,
        timeout_count=2,
        max_worker_timeouts=3,
        worker_timeout_threshold=570,
    )
    assert r["timed_out"] is True
    assert r["timeout_count"] == 3
    assert r["blocked"] is True
    assert r["stop_reason"] == WORKER_TIMEOUT_STOP


def test_not_blocked_below_max():
    r = evaluate_worker_timeout(
        elapsed_seconds=600,
        error=None,
        timeout_count=1,
        max_worker_timeouts=3,
        worker_timeout_threshold=570,
    )
    assert r["blocked"] is False
    assert r["stop_reason"] is None


def test_blocked_exactly_at_max_equals_one():
    r = evaluate_worker_timeout(
        elapsed_seconds=600,
        error=None,
        timeout_count=0,
        max_worker_timeouts=1,
        worker_timeout_threshold=570,
    )
    assert r["blocked"] is True
    assert r["stop_reason"] == WORKER_TIMEOUT_STOP


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


def _timeout_state(task_id="t1", timeout_count=0, elapsed=600.0, max_retries=0):
    return RunnerState(
        current_task_id=task_id,
        current_task={"id": task_id},
        worker_result={"success": False, "error": "Command timed out after 600s"},
        worker_elapsed_seconds=elapsed,
        worker_timeout_count=timeout_count,
    )


def test_node_first_timeout_increments_count():
    def body(calls):
        graph.cfg.worker_timeout_guard_enabled = True
        graph.cfg.max_worker_timeouts = 3
        graph.cfg.worker_timeout_threshold = 570
        graph.cfg.failure_guard_enabled = False
        out = graph.update_logs_and_state(_timeout_state(timeout_count=0))
        assert out.worker_timeout_count == 1, out.worker_timeout_count
        assert out.stop_reason is None, out.stop_reason
    _with_stubbed_task_io(body)


def test_node_timeout_at_max_sets_stop_reason():
    def body(calls):
        graph.cfg.worker_timeout_guard_enabled = True
        graph.cfg.max_worker_timeouts = 3
        graph.cfg.worker_timeout_threshold = 570
        graph.cfg.failure_guard_enabled = False
        out = graph.update_logs_and_state(_timeout_state(timeout_count=2))
        assert out.worker_timeout_count == 3, out.worker_timeout_count
        assert out.stop_reason == WORKER_TIMEOUT_STOP, out.stop_reason
    _with_stubbed_task_io(body)


def test_node_non_timeout_failure_does_not_increment():
    def body(calls):
        graph.cfg.worker_timeout_guard_enabled = True
        graph.cfg.max_worker_timeouts = 3
        graph.cfg.worker_timeout_threshold = 570
        graph.cfg.failure_guard_enabled = False
        s = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1"},
            worker_result={"success": False, "error": "SyntaxError: unexpected token"},
            worker_elapsed_seconds=10.0,
            worker_timeout_count=1,
        )
        out = graph.update_logs_and_state(s)
        assert out.worker_timeout_count == 1, out.worker_timeout_count
        assert out.stop_reason is None, out.stop_reason
    _with_stubbed_task_io(body)


def test_node_guard_disabled_no_effect():
    def body(calls):
        graph.cfg.worker_timeout_guard_enabled = False
        graph.cfg.failure_guard_enabled = False
        out = graph.update_logs_and_state(_timeout_state(timeout_count=99))
        assert out.worker_timeout_count == 99, out.worker_timeout_count
        assert out.stop_reason is None, out.stop_reason
    _with_stubbed_task_io(body)


def test_node_elapsed_seconds_cleared_after_loop():
    def body(calls):
        graph.cfg.worker_timeout_guard_enabled = True
        graph.cfg.max_worker_timeouts = 3
        graph.cfg.worker_timeout_threshold = 570
        graph.cfg.failure_guard_enabled = False
        out = graph.update_logs_and_state(_timeout_state())
        assert out.worker_elapsed_seconds is None, out.worker_elapsed_seconds
    _with_stubbed_task_io(body)


def test_stop_reason_constant_surfaces_in_decide():
    s = RunnerState(stop_reason=WORKER_TIMEOUT_STOP)
    out = graph.decide_continue_or_stop(s)
    assert out.status == "stopped", out.status


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_is_timeout_error_matches_run_command_message,
        test_is_timeout_error_matches_case_insensitive,
        test_is_timeout_error_matches_timeout_expired,
        test_is_timeout_error_false_for_unrelated_error,
        test_is_timeout_error_false_for_none,
        test_is_timeout_error_false_for_empty_string,
        test_guard_disabled_when_max_zero,
        test_elapsed_triggers_timeout,
        test_elapsed_below_threshold_not_timeout,
        test_error_text_triggers_timeout,
        test_neither_signal_no_timeout,
        test_elapsed_none_does_not_count_as_timeout,
        test_threshold_zero_disables_elapsed_check,
        test_blocked_at_max,
        test_not_blocked_below_max,
        test_blocked_exactly_at_max_equals_one,
        test_node_first_timeout_increments_count,
        test_node_timeout_at_max_sets_stop_reason,
        test_node_non_timeout_failure_does_not_increment,
        test_node_guard_disabled_no_effect,
        test_node_elapsed_seconds_cleared_after_loop,
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
