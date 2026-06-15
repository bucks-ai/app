"""Unit tests for the Codex usage-limit guard.

Runs standalone (no pytest dependency), mirroring test_worker_timeout_guard.py:

    python tests/test_codex_usage_limit_guard.py

Covers the pure decision helpers in tools/codex_usage_limit_guard.py and the
graph.update_logs_and_state node integration.  Task-queue mutations and the
flight recorder are stubbed, so no real disk state under the runner is touched.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.codex_usage_limit_guard import (
    _is_usage_limit_error,
    evaluate_codex_usage_limit,
    CODEX_USAGE_LIMIT_STOP,
)
import graph
from state import RunnerState

# Silence the flight recorder and disk persistence during tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None


# ---------------------------------------------------------------------------
# Pure helper: _is_usage_limit_error
# ---------------------------------------------------------------------------

def test_is_usage_limit_error_429():
    assert _is_usage_limit_error("Error: 429 Too Many Requests") is True


def test_is_usage_limit_error_rate_limit_space():
    assert _is_usage_limit_error("rate limit exceeded") is True


def test_is_usage_limit_error_rate_limit_underscore():
    assert _is_usage_limit_error("error: rate_limit_exceeded") is True


def test_is_usage_limit_error_quota():
    assert _is_usage_limit_error("OpenAI: quota_exceeded") is True


def test_is_usage_limit_error_insufficient_quota():
    assert _is_usage_limit_error("insufficient_quota for this model") is True


def test_is_usage_limit_error_monthly_limit():
    assert _is_usage_limit_error("You have exceeded your monthly limit") is True


def test_is_usage_limit_error_usage_limit():
    assert _is_usage_limit_error("usage limit reached") is True


def test_is_usage_limit_error_too_many_requests():
    assert _is_usage_limit_error("Too Many Requests") is True


def test_is_usage_limit_error_billing_hard_limit():
    assert _is_usage_limit_error("billing hard limit reached") is True


def test_is_usage_limit_error_case_insensitive():
    assert _is_usage_limit_error("QUOTA EXCEEDED") is True


def test_is_usage_limit_error_false_for_unrelated():
    assert _is_usage_limit_error("ModuleNotFoundError: no module named foo") is False


def test_is_usage_limit_error_false_for_timeout():
    assert _is_usage_limit_error("Command timed out after 600s") is False


def test_is_usage_limit_error_false_for_none():
    assert _is_usage_limit_error(None) is False


def test_is_usage_limit_error_false_for_empty_string():
    assert _is_usage_limit_error("") is False


# ---------------------------------------------------------------------------
# Pure helper: evaluate_codex_usage_limit
# ---------------------------------------------------------------------------

def test_guard_disabled_when_max_zero():
    r = evaluate_codex_usage_limit(
        error="Error: 429 Too Many Requests",
        worker="codex",
        usage_limit_count=5,
        max_codex_usage_limit_errors=0,
    )
    assert r["usage_limit_detected"] is False
    assert r["blocked"] is False
    assert r["stop_reason"] is None
    assert r["usage_limit_count"] == 5  # unchanged


def test_guard_no_effect_for_non_codex_worker():
    r = evaluate_codex_usage_limit(
        error="Error: 429 Too Many Requests",
        worker="claude",
        usage_limit_count=0,
        max_codex_usage_limit_errors=2,
    )
    assert r["usage_limit_detected"] is False
    assert r["blocked"] is False
    assert r["usage_limit_count"] == 0


def test_guard_no_effect_for_none_worker():
    r = evaluate_codex_usage_limit(
        error="Error: 429 Too Many Requests",
        worker=None,
        usage_limit_count=0,
        max_codex_usage_limit_errors=2,
    )
    assert r["usage_limit_detected"] is False
    assert r["blocked"] is False


def test_usage_limit_detected_increments_count():
    r = evaluate_codex_usage_limit(
        error="rate limit exceeded",
        worker="codex",
        usage_limit_count=0,
        max_codex_usage_limit_errors=2,
    )
    assert r["usage_limit_detected"] is True
    assert r["usage_limit_count"] == 1
    assert r["blocked"] is False


def test_no_usage_limit_error_no_increment():
    r = evaluate_codex_usage_limit(
        error="SyntaxError: unexpected token",
        worker="codex",
        usage_limit_count=1,
        max_codex_usage_limit_errors=2,
    )
    assert r["usage_limit_detected"] is False
    assert r["usage_limit_count"] == 1
    assert r["blocked"] is False


def test_blocked_at_max():
    r = evaluate_codex_usage_limit(
        error="quota exceeded",
        worker="codex",
        usage_limit_count=1,
        max_codex_usage_limit_errors=2,
    )
    assert r["usage_limit_detected"] is True
    assert r["usage_limit_count"] == 2
    assert r["blocked"] is True
    assert r["stop_reason"] == CODEX_USAGE_LIMIT_STOP


def test_blocked_exactly_at_max_equals_one():
    r = evaluate_codex_usage_limit(
        error="429 Too Many Requests",
        worker="codex",
        usage_limit_count=0,
        max_codex_usage_limit_errors=1,
    )
    assert r["blocked"] is True
    assert r["stop_reason"] == CODEX_USAGE_LIMIT_STOP


def test_not_blocked_below_max():
    r = evaluate_codex_usage_limit(
        error="rate_limit_exceeded",
        worker="codex",
        usage_limit_count=0,
        max_codex_usage_limit_errors=3,
    )
    assert r["blocked"] is False
    assert r["stop_reason"] is None


def test_none_error_not_detected():
    r = evaluate_codex_usage_limit(
        error=None,
        worker="codex",
        usage_limit_count=0,
        max_codex_usage_limit_errors=2,
    )
    assert r["usage_limit_detected"] is False
    assert r["usage_limit_count"] == 0


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


def _codex_limit_state(task_id="t1", usage_limit_count=0, error="Error: 429 Too Many Requests"):
    return RunnerState(
        current_task_id=task_id,
        current_task={"id": task_id},
        worker_result={"worker": "codex", "success": False, "error": error},
        codex_usage_limit_count=usage_limit_count,
    )


def test_node_first_limit_error_increments_count():
    def body(calls):
        graph.cfg.codex_usage_limit_guard_enabled = True
        graph.cfg.max_codex_usage_limit_errors = 3
        graph.cfg.worker_timeout_guard_enabled = False
        graph.cfg.failure_guard_enabled = False
        out = graph.update_logs_and_state(_codex_limit_state(usage_limit_count=0))
        assert out.codex_usage_limit_count == 1, out.codex_usage_limit_count
        assert out.stop_reason is None, out.stop_reason
    _with_stubbed_task_io(body)


def test_node_limit_at_max_sets_stop_reason():
    def body(calls):
        graph.cfg.codex_usage_limit_guard_enabled = True
        graph.cfg.max_codex_usage_limit_errors = 2
        graph.cfg.worker_timeout_guard_enabled = False
        graph.cfg.failure_guard_enabled = False
        out = graph.update_logs_and_state(_codex_limit_state(usage_limit_count=1))
        assert out.codex_usage_limit_count == 2, out.codex_usage_limit_count
        assert out.stop_reason == CODEX_USAGE_LIMIT_STOP, out.stop_reason
    _with_stubbed_task_io(body)


def test_node_non_limit_error_does_not_increment():
    def body(calls):
        graph.cfg.codex_usage_limit_guard_enabled = True
        graph.cfg.max_codex_usage_limit_errors = 2
        graph.cfg.worker_timeout_guard_enabled = False
        graph.cfg.failure_guard_enabled = False
        s = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1"},
            worker_result={"worker": "codex", "success": False, "error": "SyntaxError: bad token"},
            codex_usage_limit_count=1,
        )
        out = graph.update_logs_and_state(s)
        assert out.codex_usage_limit_count == 1, out.codex_usage_limit_count
        assert out.stop_reason is None, out.stop_reason
    _with_stubbed_task_io(body)


def test_node_guard_disabled_no_effect():
    def body(calls):
        graph.cfg.codex_usage_limit_guard_enabled = False
        graph.cfg.worker_timeout_guard_enabled = False
        graph.cfg.failure_guard_enabled = False
        out = graph.update_logs_and_state(_codex_limit_state(usage_limit_count=99))
        assert out.codex_usage_limit_count == 99, out.codex_usage_limit_count
        assert out.stop_reason is None, out.stop_reason
    _with_stubbed_task_io(body)


def test_node_non_codex_worker_no_effect():
    def body(calls):
        graph.cfg.codex_usage_limit_guard_enabled = True
        graph.cfg.max_codex_usage_limit_errors = 2
        graph.cfg.worker_timeout_guard_enabled = False
        graph.cfg.failure_guard_enabled = False
        s = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1"},
            worker_result={"worker": "claude", "success": False, "error": "Error: 429 Too Many Requests"},
            codex_usage_limit_count=0,
        )
        out = graph.update_logs_and_state(s)
        assert out.codex_usage_limit_count == 0, out.codex_usage_limit_count
        assert out.stop_reason is None, out.stop_reason
    _with_stubbed_task_io(body)


def test_stop_reason_constant_surfaces_in_decide():
    s = RunnerState(stop_reason=CODEX_USAGE_LIMIT_STOP)
    out = graph.decide_continue_or_stop(s)
    assert out.status == "stopped", out.status


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_is_usage_limit_error_429,
        test_is_usage_limit_error_rate_limit_space,
        test_is_usage_limit_error_rate_limit_underscore,
        test_is_usage_limit_error_quota,
        test_is_usage_limit_error_insufficient_quota,
        test_is_usage_limit_error_monthly_limit,
        test_is_usage_limit_error_usage_limit,
        test_is_usage_limit_error_too_many_requests,
        test_is_usage_limit_error_billing_hard_limit,
        test_is_usage_limit_error_case_insensitive,
        test_is_usage_limit_error_false_for_unrelated,
        test_is_usage_limit_error_false_for_timeout,
        test_is_usage_limit_error_false_for_none,
        test_is_usage_limit_error_false_for_empty_string,
        test_guard_disabled_when_max_zero,
        test_guard_no_effect_for_non_codex_worker,
        test_guard_no_effect_for_none_worker,
        test_usage_limit_detected_increments_count,
        test_no_usage_limit_error_no_increment,
        test_blocked_at_max,
        test_blocked_exactly_at_max_equals_one,
        test_not_blocked_below_max,
        test_none_error_not_detected,
        test_node_first_limit_error_increments_count,
        test_node_limit_at_max_sets_stop_reason,
        test_node_non_limit_error_does_not_increment,
        test_node_guard_disabled_no_effect,
        test_node_non_codex_worker_no_effect,
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
