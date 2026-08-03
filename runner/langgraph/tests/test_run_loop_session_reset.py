"""Unit tests for the run-loop fresh-session reset (main.start_fresh_session).

Runs standalone (no pytest dependency), mirroring test_repeated_error_guard.py:

    python tests/test_run_loop_session_reset.py

Covers the incident from 2026-07-09: task_attempt_counts persisted across
run-loop restarts in .runtime/state.local.json, so the repeated-task guard
could insta-block a task on a brand-new session using attempts accumulated
in a previous, unrelated failure cascade. start_fresh_session must reset
task_attempt_counts (along with the other already-reset session fields)
whenever a new loop starts.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from main import start_fresh_session
from state import RunnerState


def test_task_attempt_counts_reset_on_fresh_session():
    saved = RunnerState(task_attempt_counts={"t1": 3, "t2": 1})
    fresh = start_fresh_session(saved)
    assert fresh.task_attempt_counts == {}


def test_other_session_fields_still_reset():
    saved = RunnerState(
        stop_reason="repeated_task",
        loop_count=7,
        consecutive_failures=2,
        status="stopped",
        task_attempt_counts={"t1": 5},
    )
    fresh = start_fresh_session(saved)
    assert fresh.stop_reason is None
    assert fresh.loop_count == 0
    assert fresh.consecutive_failures == 0
    assert fresh.status == "running"
    assert fresh.started_at is not None
    assert fresh.task_attempt_counts == {}


def test_fresh_session_from_saved_state_dict():
    # Mirrors cmd_run_loop's construction: RunnerState(**saved) from a state
    # file written by a prior session with exhausted attempt counts.
    saved_dict = {
        "status": "stopped",
        "stop_reason": "repeated_task",
        "loop_count": 12,
        "task_attempt_counts": {"flaky-task": 4},
    }
    init = RunnerState(**{k: v for k, v in saved_dict.items() if k in RunnerState.model_fields})
    fresh = start_fresh_session(init)
    assert fresh.task_attempt_counts == {}
    assert fresh.stop_reason is None


def test_unrelated_fields_left_untouched():
    saved = RunnerState(current_worker="codex", session_cost=4.5)
    fresh = start_fresh_session(saved)
    assert fresh.current_worker == "codex"
    assert fresh.session_cost == 4.5


if __name__ == "__main__":
    tests = [
        test_task_attempt_counts_reset_on_fresh_session,
        test_other_session_fields_still_reset,
        test_fresh_session_from_saved_state_dict,
        test_unrelated_fields_left_untouched,
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
