"""Unit tests for M0.4 — excluding Claude subscription cooldown waits from the
MAX_RUNTIME_MINUTES budget and from the stale_run_watchdog gap.

Runs standalone (no pytest dependency), mirroring test_strategic_decision_gate.py:

    python tests/test_cooldown_runtime_budget.py

Covers graph.decide_continue_or_stop:
- a cooldown sleep accumulates into state.cooldown_wait_seconds_total and is
  subtracted from elapsed wall-clock time before it is compared against
  cfg.max_runtime_minutes
- the cooldown wait refreshes state.last_task_completed_at at both the start
  and the end of the sleep, so stale_run_watchdog (which only reads that
  timestamp back in update_logs_and_state) cannot see a stale gap that was
  really just the runner sleeping through a rate-limit reset
- the runtime cap is still enforced normally when no cooldown occurred
"""
import os
import sys
import traceback
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import graph
from state import RunnerState
from tools.stale_run_watchdog import evaluate_stale_run

# Silence the flight recorder and disk persistence during tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None

_sleep_calls = []


def _fake_sleep(seconds):
    _sleep_calls.append(seconds)


# ---------------------------------------------------------------------------
# Runtime cap excludes cooldown wait time
# ---------------------------------------------------------------------------

def test_runtime_cap_not_consumed_by_cooldown_wait():
    """A cooldown sleep long enough to blow past MAX_RUNTIME_MINUTES on raw
    wall-clock elapsed must not stop the loop once its own wait time is
    excluded from the budget."""
    graph.cfg.max_runtime_minutes = 60
    graph.cfg.max_loop_tasks = 1000
    graph.cfg.stale_run_watchdog_enabled = False

    real_sleep = graph.time.sleep
    graph.time.sleep = _fake_sleep
    try:
        # started 90 minutes ago (over the 60-minute cap on raw elapsed)...
        started_at = (datetime.utcnow() - timedelta(minutes=90)).isoformat()
        # ...but 40 of those minutes were a cooldown wait that's about to
        # finish right now (resume_at in the past by a hair so remaining<=0
        # is avoided while keeping the test deterministic: use a resume time
        # slightly in the future instead).
        resume_at = (datetime.utcnow() + timedelta(seconds=5)).isoformat()
        s = RunnerState(
            started_at=started_at,
            loop_count=0,
            cooldown_wait_seconds_total=40 * 60,
            claude_subscription_cooldown_until=resume_at,
        )
        out = graph.decide_continue_or_stop(s)
    finally:
        graph.time.sleep = real_sleep

    # raw elapsed (~90min) minus cooldown budget (40min) = ~50min < 60min cap
    assert out.stop_reason is None, out.stop_reason
    assert out.status == "running", out.status


def test_runtime_cap_still_enforced_without_cooldown():
    """No cooldown occurred: the normal MAX_RUNTIME_MINUTES enforcement must
    still trip exactly as before."""
    graph.cfg.max_runtime_minutes = 60
    graph.cfg.max_loop_tasks = 1000
    graph.cfg.stale_run_watchdog_enabled = False

    started_at = (datetime.utcnow() - timedelta(minutes=90)).isoformat()
    s = RunnerState(
        started_at=started_at,
        loop_count=0,
        cooldown_wait_seconds_total=0.0,
        claude_subscription_cooldown_until=None,
    )
    out = graph.decide_continue_or_stop(s)

    assert out.stop_reason == "max_runtime", out.stop_reason
    assert out.status == "stopped", out.status


# ---------------------------------------------------------------------------
# Cooldown wait accumulation + stale-watchdog suppression
# ---------------------------------------------------------------------------

def test_cooldown_wait_accumulates_seconds_and_refreshes_activity():
    graph.cfg.stale_run_watchdog_enabled = False
    graph.cfg.max_loop_tasks = 1000
    graph.cfg.max_runtime_minutes = 480

    real_sleep = graph.time.sleep
    graph.time.sleep = _fake_sleep
    _sleep_calls.clear()
    try:
        resume_at = (datetime.utcnow() + timedelta(seconds=120)).isoformat()
        s = RunnerState(
            started_at=datetime.utcnow().isoformat(),
            loop_count=0,
            cooldown_wait_seconds_total=0.0,
            claude_subscription_cooldown_until=resume_at,
            last_task_completed_at=(datetime.utcnow() - timedelta(hours=5)).isoformat(),
        )
        before = datetime.utcnow()
        out = graph.decide_continue_or_stop(s)
        after = datetime.utcnow()
    finally:
        graph.time.sleep = real_sleep

    assert len(_sleep_calls) == 1, _sleep_calls
    assert out.cooldown_wait_seconds_total > 0, out.cooldown_wait_seconds_total
    assert 115 <= out.cooldown_wait_seconds_total <= 125, out.cooldown_wait_seconds_total
    assert out.claude_subscription_cooldown_until is None

    # last_task_completed_at was refreshed to "now" (both at wait-start and
    # wait-end), not left at the 5-hours-stale value it started with.
    refreshed = datetime.fromisoformat(out.last_task_completed_at)
    assert before <= refreshed <= after, (before, refreshed, after)


def test_stale_watchdog_suppressed_during_cooldown():
    """End-to-end check on the pure watchdog helper: after a cooldown wait
    refreshes last_task_completed_at, a stale_run_watchdog evaluation run
    immediately afterwards (as update_logs_and_state would run on the next
    loop iteration) must not trip, even though max_stale_task_minutes is far
    smaller than the cooldown wait that just happened."""
    graph.cfg.max_loop_tasks = 1000
    graph.cfg.max_runtime_minutes = 480

    real_sleep = graph.time.sleep
    graph.time.sleep = _fake_sleep
    try:
        # Cooldown wait of 30 simulated minutes; watchdog threshold is only
        # 10 minutes. Without the activity refresh this would trip.
        resume_at = (datetime.utcnow() + timedelta(minutes=30)).isoformat()
        s = RunnerState(
            started_at=datetime.utcnow().isoformat(),
            loop_count=1,
            cooldown_wait_seconds_total=0.0,
            claude_subscription_cooldown_until=resume_at,
            last_task_completed_at=(datetime.utcnow() - timedelta(hours=6)).isoformat(),
        )
        out = graph.decide_continue_or_stop(s)
    finally:
        graph.time.sleep = real_sleep

    result = evaluate_stale_run(
        last_task_completed_at=out.last_task_completed_at,
        loop_count=out.loop_count,
        max_stale_task_minutes=10,
        enabled=True,
    )
    assert result["stale"] is False, result
    assert result["blocked"] is False, result


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_runtime_cap_not_consumed_by_cooldown_wait,
        test_runtime_cap_still_enforced_without_cooldown,
        test_cooldown_wait_accumulates_seconds_and_refreshes_activity,
        test_stale_watchdog_suppressed_during_cooldown,
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
