"""Unit tests for failure_retry_backoff.

Covers the pure helpers in tools/failure_retry_backoff.py and the task_tools
backoff-skip logic, plus graph-level integration (retry event carries
degraded+retry_not_before fields).

Run standalone:
    python tests/test_failure_retry_backoff.py
Or via pytest:
    python -m pytest tests/test_failure_retry_backoff.py -x -q
"""
import os
import sys
import traceback
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.failure_retry_backoff import (
    is_degraded_failure,
    compute_backoff,
    compute_retry_not_before,
)
import graph
from state import RunnerState

# Silence the flight recorder and disk persistence during tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None


# ---------------------------------------------------------------------------
# is_degraded_failure
# ---------------------------------------------------------------------------

def test_degraded_on_timeout_marker_in_error():
    assert is_degraded_failure("timed out after 570s", None, 570, 0) is True


def test_degraded_on_health_probe_marker():
    assert is_degraded_failure("cli binary not found on PATH", None, 570, 0) is True


def test_degraded_on_elapsed_exceeds_threshold():
    assert is_degraded_failure(None, 600.0, 570, 0) is True


def test_not_degraded_when_elapsed_below_threshold():
    assert is_degraded_failure(None, 100.0, 570, 0) is False


def test_degraded_on_consecutive_failures_above_one():
    assert is_degraded_failure("some error", None, 570, 2) is True


def test_not_degraded_on_single_consecutive_failure():
    assert is_degraded_failure("some error", None, 570, 1) is False


def test_not_degraded_clean_first_failure():
    assert is_degraded_failure("boom", None, 570, 0) is False


def test_degraded_threshold_zero_disables_elapsed_check():
    assert is_degraded_failure(None, 9999.0, 0, 0) is False


# ---------------------------------------------------------------------------
# compute_backoff
# ---------------------------------------------------------------------------

def test_backoff_first_attempt():
    assert compute_backoff(1, 30.0, 2.0, 300.0) == 30.0


def test_backoff_second_attempt():
    assert compute_backoff(2, 30.0, 2.0, 300.0) == 60.0


def test_backoff_third_attempt():
    assert compute_backoff(3, 30.0, 2.0, 300.0) == 120.0


def test_backoff_capped_at_max():
    assert compute_backoff(10, 30.0, 2.0, 300.0) == 300.0


def test_backoff_disabled_when_base_zero():
    assert compute_backoff(1, 0.0, 2.0, 300.0) == 0.0


def test_backoff_disabled_when_max_zero():
    assert compute_backoff(1, 30.0, 2.0, 0.0) == 0.0


def test_backoff_invalid_attempt_returns_zero():
    assert compute_backoff(0, 30.0, 2.0, 300.0) == 0.0
    assert compute_backoff(-1, 30.0, 2.0, 300.0) == 0.0


# ---------------------------------------------------------------------------
# compute_retry_not_before
# ---------------------------------------------------------------------------

def test_retry_not_before_returns_future_iso():
    _now = datetime(2026, 6, 23, 12, 0, 0)
    ts = compute_retry_not_before(1, 30.0, 2.0, 300.0, _now=_now)
    expected = datetime(2026, 6, 23, 12, 0, 30).isoformat()
    assert ts == expected, ts


def test_retry_not_before_returns_none_when_disabled():
    assert compute_retry_not_before(1, 0.0, 2.0, 300.0) is None


def test_retry_not_before_second_attempt_doubles():
    _now = datetime(2026, 6, 23, 12, 0, 0)
    ts1 = compute_retry_not_before(1, 30.0, 2.0, 300.0, _now=_now)
    ts2 = compute_retry_not_before(2, 30.0, 2.0, 300.0, _now=_now)
    dt1 = datetime.fromisoformat(ts1)
    dt2 = datetime.fromisoformat(ts2)
    assert (dt2 - dt1).total_seconds() == 30.0, f"{ts1} vs {ts2}"


# ---------------------------------------------------------------------------
# task_tools backoff-skip integration
# ---------------------------------------------------------------------------

def _make_task(task_id, retry_not_before=None):
    t = {"id": task_id, "title": "Test", "status": "queued"}
    if retry_not_before:
        t["retry_not_before"] = retry_not_before
    return t


def _with_task_queue(tasks, fn):
    """Run fn() with load_tasks() returning tasks, save_tasks() a no-op."""
    orig_load = graph.load_tasks
    orig_save = __import__("tools.task_tools", fromlist=["save_tasks"]).save_tasks
    import tools.task_tools as tt
    tt.load_tasks = lambda: [dict(t) for t in tasks]
    tt.save_tasks = lambda t: None
    try:
        return fn()
    finally:
        tt.load_tasks = orig_load
        tt.save_tasks = orig_save


def test_task_tools_skips_task_in_backoff_window():
    import tools.task_tools as tt
    future = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
    tasks = [_make_task("t1", retry_not_before=future)]

    def run():
        return tt.get_next_queued_task()

    orig_load = tt.load_tasks
    tt.load_tasks = lambda: [dict(t) for t in tasks]
    try:
        result = tt.get_next_queued_task()
        assert result is None, f"expected None, got {result}"
    finally:
        tt.load_tasks = orig_load


def test_task_tools_returns_task_after_backoff_expires():
    import tools.task_tools as tt
    past = (datetime.utcnow() - timedelta(minutes=1)).isoformat()
    tasks = [_make_task("t1", retry_not_before=past)]

    orig_load = tt.load_tasks
    tt.load_tasks = lambda: [dict(t) for t in tasks]
    try:
        result = tt.get_next_queued_task()
        assert result is not None, "expected task after backoff expired"
        assert result["id"] == "t1"
    finally:
        tt.load_tasks = orig_load


def test_task_tools_returns_task_with_no_backoff():
    import tools.task_tools as tt
    tasks = [_make_task("t1")]

    orig_load = tt.load_tasks
    tt.load_tasks = lambda: [dict(t) for t in tasks]
    try:
        result = tt.get_next_queued_task()
        assert result is not None
        assert result["id"] == "t1"
    finally:
        tt.load_tasks = orig_load


def test_task_tools_skips_backoff_task_returns_next():
    import tools.task_tools as tt
    future = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
    tasks = [
        _make_task("t1", retry_not_before=future),
        _make_task("t2"),
    ]

    orig_load = tt.load_tasks
    tt.load_tasks = lambda: [dict(t) for t in tasks]
    try:
        result = tt.get_next_queued_task()
        assert result is not None
        assert result["id"] == "t2", f"expected t2, got {result}"
    finally:
        tt.load_tasks = orig_load


# ---------------------------------------------------------------------------
# Graph integration: degraded retry logs retry_not_before
# ---------------------------------------------------------------------------

def _with_stubbed_task_io(fn):
    calls = {"requeue": [], "failed": [], "complete": []}
    orig = (graph.requeue_task, graph.mark_task_failed, graph.mark_task_complete)
    graph.requeue_task = lambda task_id, rc, retry_not_before=None: calls["requeue"].append((task_id, rc, retry_not_before))
    graph.mark_task_failed = lambda task_id, err: calls["failed"].append((task_id, err))
    graph.mark_task_complete = lambda task_id, summary: calls["complete"].append((task_id, summary))
    try:
        return fn(calls)
    finally:
        graph.requeue_task, graph.mark_task_failed, graph.mark_task_complete = orig


def test_graph_applies_backoff_on_timeout_failure():
    def body(calls):
        graph.cfg.failure_guard_enabled = True
        graph.cfg.max_task_retries = 2
        graph.cfg.max_consecutive_failures = 5
        graph.cfg.failure_retry_backoff_enabled = True
        graph.cfg.failure_retry_backoff_base_s = 30.0
        graph.cfg.failure_retry_backoff_multiplier = 2.0
        graph.cfg.failure_retry_backoff_max_s = 300.0
        graph.cfg.worker_timeout_threshold = 570
        s = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1"},
            worker_result={"success": False, "error": "timed out after 570s"},
            consecutive_failures=0,
            worker_elapsed_seconds=600.0,
        )
        graph.update_logs_and_state(s)
        assert len(calls["requeue"]) == 1, calls
        _tid, _rc, rnb = calls["requeue"][0]
        assert rnb is not None, "expected a retry_not_before timestamp for a degraded failure"
    _with_stubbed_task_io(body)


def test_graph_no_backoff_on_clean_first_failure():
    def body(calls):
        graph.cfg.failure_guard_enabled = True
        graph.cfg.max_task_retries = 2
        graph.cfg.max_consecutive_failures = 5
        graph.cfg.failure_retry_backoff_enabled = True
        graph.cfg.failure_retry_backoff_base_s = 30.0
        graph.cfg.failure_retry_backoff_multiplier = 2.0
        graph.cfg.failure_retry_backoff_max_s = 300.0
        graph.cfg.worker_timeout_threshold = 570
        s = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1"},
            worker_result={"success": False, "error": "bad output"},
            consecutive_failures=0,
            worker_elapsed_seconds=10.0,
        )
        graph.update_logs_and_state(s)
        assert len(calls["requeue"]) == 1, calls
        _tid, _rc, rnb = calls["requeue"][0]
        assert rnb is None, "clean first failure should not apply backoff"
    _with_stubbed_task_io(body)


def test_graph_backoff_disabled_by_config():
    def body(calls):
        graph.cfg.failure_guard_enabled = True
        graph.cfg.max_task_retries = 2
        graph.cfg.max_consecutive_failures = 5
        graph.cfg.failure_retry_backoff_enabled = False
        graph.cfg.worker_timeout_threshold = 570
        s = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1"},
            worker_result={"success": False, "error": "timed out after 570s"},
            consecutive_failures=0,
            worker_elapsed_seconds=600.0,
        )
        graph.update_logs_and_state(s)
        assert len(calls["requeue"]) == 1, calls
        _tid, _rc, rnb = calls["requeue"][0]
        assert rnb is None, "backoff disabled — retry_not_before must be None"
    _with_stubbed_task_io(body)


def test_graph_backoff_on_sustained_consecutive_failures():
    def body(calls):
        graph.cfg.failure_guard_enabled = True
        graph.cfg.max_task_retries = 5
        graph.cfg.max_consecutive_failures = 10
        graph.cfg.failure_retry_backoff_enabled = True
        graph.cfg.failure_retry_backoff_base_s = 30.0
        graph.cfg.failure_retry_backoff_multiplier = 2.0
        graph.cfg.failure_retry_backoff_max_s = 300.0
        graph.cfg.worker_timeout_threshold = 570
        s = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1"},
            worker_result={"success": False, "error": "check failed"},
            consecutive_failures=2,
            worker_elapsed_seconds=10.0,
        )
        graph.update_logs_and_state(s)
        assert len(calls["requeue"]) == 1, calls
        _tid, _rc, rnb = calls["requeue"][0]
        assert rnb is not None, "sustained consecutive failures should trigger backoff"
    _with_stubbed_task_io(body)


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_degraded_on_timeout_marker_in_error,
        test_degraded_on_health_probe_marker,
        test_degraded_on_elapsed_exceeds_threshold,
        test_not_degraded_when_elapsed_below_threshold,
        test_degraded_on_consecutive_failures_above_one,
        test_not_degraded_on_single_consecutive_failure,
        test_not_degraded_clean_first_failure,
        test_degraded_threshold_zero_disables_elapsed_check,
        test_backoff_first_attempt,
        test_backoff_second_attempt,
        test_backoff_third_attempt,
        test_backoff_capped_at_max,
        test_backoff_disabled_when_base_zero,
        test_backoff_disabled_when_max_zero,
        test_backoff_invalid_attempt_returns_zero,
        test_retry_not_before_returns_future_iso,
        test_retry_not_before_returns_none_when_disabled,
        test_retry_not_before_second_attempt_doubles,
        test_task_tools_skips_task_in_backoff_window,
        test_task_tools_returns_task_after_backoff_expires,
        test_task_tools_returns_task_with_no_backoff,
        test_task_tools_skips_backoff_task_returns_next,
        test_graph_applies_backoff_on_timeout_failure,
        test_graph_no_backoff_on_clean_first_failure,
        test_graph_backoff_disabled_by_config,
        test_graph_backoff_on_sustained_consecutive_failures,
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
