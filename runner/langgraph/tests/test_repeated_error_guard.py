"""Unit tests for the repeated-error and repeated-task guards.

Runs standalone (no pytest dependency), mirroring test_failure_guard.py:

    python tests/test_repeated_error_guard.py

Covers the pure helpers in tools/repeated_error_guard.py and the wiring in
graph.update_logs_and_state.  Task-queue mutations and the flight recorder are
stubbed so no real disk state is touched.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.repeated_error_guard import (
    evaluate_error_repetition,
    evaluate_task_repetition,
    REPEATED_ERROR_STOP,
    REPEATED_TASK_STOP,
)
import graph
from state import RunnerState

# Silence the flight recorder and disk persistence during tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None


# ---------------------------------------------------------------------------
# Pure helper: _errors_match (via evaluate_error_repetition)
# ---------------------------------------------------------------------------

def test_identical_errors_match():
    r = evaluate_error_repetition("boom", [{"error": "boom", "task_id": "t1"}], 2, 0)
    assert r["match_count"] == 2

def test_substring_errors_match():
    r = evaluate_error_repetition(
        "connection refused to db", [{"error": "connection refused", "task_id": "t1"}], 2, 0
    )
    assert r["match_count"] == 2

def test_short_strings_require_exact_match():
    r = evaluate_error_repetition("err", [{"error": "error", "task_id": "t1"}], 2, 0)
    assert r["match_count"] == 1  # no match — too short for substring

def test_different_errors_do_not_match():
    r = evaluate_error_repetition("timeout on connect", [{"error": "disk full", "task_id": "t1"}], 2, 0)
    assert r["match_count"] == 1
    assert r["blocked"] is False


# ---------------------------------------------------------------------------
# Pure helper: evaluate_error_repetition
# ---------------------------------------------------------------------------

def test_error_guard_disabled_when_zero():
    r = evaluate_error_repetition("boom", [{"error": "boom", "task_id": "t1"}] * 10, 0, 0)
    assert r["blocked"] is False
    assert r["stop_reason"] is None

def test_error_guard_not_blocked_below_threshold():
    history = [{"error": "boom", "task_id": "t1"}]  # 1 prior + 1 current = 2
    r = evaluate_error_repetition("boom", history, 3, 0)
    assert r["blocked"] is False
    assert r["match_count"] == 2

def test_error_guard_blocked_at_threshold():
    history = [{"error": "boom", "task_id": "t1"}, {"error": "boom", "task_id": "t2"}]  # 2 prior + 1 = 3
    r = evaluate_error_repetition("boom", history, 3, 0)
    assert r["blocked"] is True
    assert r["stop_reason"] == REPEATED_ERROR_STOP
    assert r["match_count"] == 3

def test_error_guard_window_limits_history():
    # 5 old "boom" errors outside the window, then 1 "other" error in-window
    old = [{"error": "boom", "task_id": "x"}] * 5
    recent = [{"error": "other error here", "task_id": "y"}]
    history = old + recent
    r = evaluate_error_repetition("boom", history, 3, window=1)
    # Only 1 entry in window, none matching "boom" → 1 total
    assert r["blocked"] is False
    assert r["match_count"] == 1

def test_error_guard_unbounded_window_when_zero():
    history = [{"error": "boom!", "task_id": "t"}] * 10
    r = evaluate_error_repetition("boom!", history, 3, window=0)
    assert r["blocked"] is True
    assert r["match_count"] == 11


# ---------------------------------------------------------------------------
# Pure helper: evaluate_task_repetition
# ---------------------------------------------------------------------------

def test_task_guard_disabled_when_zero():
    r = evaluate_task_repetition("t1", {"t1": 99}, 0)
    assert r["blocked"] is False
    assert r["stop_reason"] is None

def test_task_guard_first_attempt_not_blocked():
    r = evaluate_task_repetition("t1", {}, 3)
    assert r["blocked"] is False
    assert r["attempt_count"] == 1

def test_task_guard_at_max_not_blocked():
    r = evaluate_task_repetition("t1", {"t1": 2}, 3)
    assert r["blocked"] is False
    assert r["attempt_count"] == 3

def test_task_guard_exceeds_max_is_blocked():
    r = evaluate_task_repetition("t1", {"t1": 3}, 3)
    assert r["blocked"] is True
    assert r["stop_reason"] == REPEATED_TASK_STOP
    assert r["attempt_count"] == 4

def test_task_guard_other_tasks_unaffected():
    r = evaluate_task_repetition("t2", {"t1": 99}, 3)
    assert r["blocked"] is False
    assert r["attempt_count"] == 1


# ---------------------------------------------------------------------------
# Node wiring: update_logs_and_state
# ---------------------------------------------------------------------------

def _with_stubbed_task_io(fn):
    calls = {"requeue": [], "failed": [], "complete": []}
    orig = (graph.requeue_task, graph.mark_task_failed, graph.mark_task_complete)
    graph.requeue_task = lambda task_id, rc: calls["requeue"].append((task_id, rc))
    graph.mark_task_failed = lambda task_id, err: calls["failed"].append((task_id, err))
    graph.mark_task_complete = lambda task_id, summary: calls["complete"].append((task_id, summary))
    try:
        return fn(calls)
    finally:
        graph.requeue_task, graph.mark_task_failed, graph.mark_task_complete = orig


def test_node_accumulates_error_history():
    def body(calls):
        graph.cfg.max_repeated_errors = 3
        graph.cfg.repeated_error_window = 0
        graph.cfg.max_task_attempts = 0
        graph.cfg.failure_guard_enabled = False
        s = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1"},
            worker_result={"success": False, "error": "disk full"},
        )
        out = graph.update_logs_and_state(s)
        assert len(out.error_history) == 1
        assert out.error_history[0]["error"] == "disk full"
        assert out.error_history[0]["task_id"] == "t1"
        assert out.stop_reason is None
    _with_stubbed_task_io(body)


def test_node_trips_on_repeated_error():
    def body(calls):
        graph.cfg.max_repeated_errors = 3
        graph.cfg.repeated_error_window = 0
        graph.cfg.max_task_attempts = 0
        graph.cfg.failure_guard_enabled = False
        history = [
            {"error": "disk full", "task_id": "t0"},
            {"error": "disk full", "task_id": "t0"},
        ]
        s = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1"},
            worker_result={"success": False, "error": "disk full"},
            error_history=history,
        )
        out = graph.update_logs_and_state(s)
        assert out.stop_reason == REPEATED_ERROR_STOP
        assert len(out.error_history) == 3
    _with_stubbed_task_io(body)


def test_node_error_guard_disabled_by_zero():
    def body(calls):
        graph.cfg.max_repeated_errors = 0
        graph.cfg.repeated_error_window = 0
        graph.cfg.max_task_attempts = 0
        graph.cfg.failure_guard_enabled = False
        history = [{"error": "boom", "task_id": "x"}] * 10
        s = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1"},
            worker_result={"success": False, "error": "boom"},
            error_history=history,
        )
        out = graph.update_logs_and_state(s)
        assert out.stop_reason is None
    _with_stubbed_task_io(body)


def test_node_accumulates_task_attempt_counts():
    def body(calls):
        graph.cfg.max_repeated_errors = 0
        graph.cfg.max_task_attempts = 3
        graph.cfg.failure_guard_enabled = False
        s = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1"},
            worker_result={"success": True},
        )
        out = graph.update_logs_and_state(s)
        assert out.task_attempt_counts.get("t1") == 1
        assert out.stop_reason is None
    _with_stubbed_task_io(body)


def test_node_trips_on_repeated_task():
    def body(calls):
        graph.cfg.max_repeated_errors = 0
        graph.cfg.max_task_attempts = 3
        graph.cfg.failure_guard_enabled = False
        s = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1"},
            worker_result={"success": True},
            task_attempt_counts={"t1": 3},
        )
        out = graph.update_logs_and_state(s)
        assert out.stop_reason == REPEATED_TASK_STOP
        assert out.task_attempt_counts["t1"] == 4
    _with_stubbed_task_io(body)


def test_node_task_guard_disabled_by_zero():
    def body(calls):
        graph.cfg.max_repeated_errors = 0
        graph.cfg.max_task_attempts = 0
        graph.cfg.failure_guard_enabled = False
        s = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1"},
            worker_result={"success": True},
            task_attempt_counts={"t1": 99},
        )
        out = graph.update_logs_and_state(s)
        assert out.stop_reason is None
    _with_stubbed_task_io(body)


def test_node_repeated_task_does_not_override_existing_stop_reason():
    def body(calls):
        graph.cfg.max_repeated_errors = 0
        graph.cfg.max_task_attempts = 3
        graph.cfg.failure_guard_enabled = False
        s = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1"},
            worker_result={"success": True},
            task_attempt_counts={"t1": 3},
            stop_reason="deploy_failed",
        )
        out = graph.update_logs_and_state(s)
        assert out.stop_reason == "deploy_failed"
    _with_stubbed_task_io(body)


def test_node_repeated_error_does_not_override_existing_stop_reason():
    def body(calls):
        graph.cfg.max_repeated_errors = 3
        graph.cfg.repeated_error_window = 0
        graph.cfg.max_task_attempts = 0
        graph.cfg.failure_guard_enabled = False
        history = [{"error": "boom", "task_id": "x"}] * 2
        s = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1"},
            worker_result={"success": False, "error": "boom"},
            error_history=history,
            stop_reason="max_runtime",
        )
        out = graph.update_logs_and_state(s)
        assert out.stop_reason == "max_runtime"
    _with_stubbed_task_io(body)


def test_stop_reason_constants_surface_in_decide():
    for reason in (REPEATED_ERROR_STOP, REPEATED_TASK_STOP):
        s = RunnerState(stop_reason=reason)
        out = graph.decide_continue_or_stop(s)
        assert out.status == "stopped", f"expected stopped for {reason}, got {out.status}"


if __name__ == "__main__":
    tests = [
        test_identical_errors_match,
        test_substring_errors_match,
        test_short_strings_require_exact_match,
        test_different_errors_do_not_match,
        test_error_guard_disabled_when_zero,
        test_error_guard_not_blocked_below_threshold,
        test_error_guard_blocked_at_threshold,
        test_error_guard_window_limits_history,
        test_error_guard_unbounded_window_when_zero,
        test_task_guard_disabled_when_zero,
        test_task_guard_first_attempt_not_blocked,
        test_task_guard_at_max_not_blocked,
        test_task_guard_exceeds_max_is_blocked,
        test_task_guard_other_tasks_unaffected,
        test_node_accumulates_error_history,
        test_node_trips_on_repeated_error,
        test_node_error_guard_disabled_by_zero,
        test_node_accumulates_task_attempt_counts,
        test_node_trips_on_repeated_task,
        test_node_task_guard_disabled_by_zero,
        test_node_repeated_task_does_not_override_existing_stop_reason,
        test_node_repeated_error_does_not_override_existing_stop_reason,
        test_stop_reason_constants_surface_in_decide,
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
