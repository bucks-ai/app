"""Unit tests for the loop watchdog restart decision logic.

Runs standalone:
    python tests/test_loop_watchdog.py

Covers ``evaluate_restart_decision()`` in ``tools/loop_watchdog.py``.
All tests are pure-function; no subprocess, no file I/O, no sleep.
"""
import os
import sys
import traceback
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.loop_watchdog import (
    evaluate_restart_decision,
    HARD_GATE_REASONS,
)

_BASE_UTC = datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# No stop_reason (unexpected exit / crash)
# ---------------------------------------------------------------------------

def test_no_stop_reason_restarts():
    r = evaluate_restart_decision(None)
    assert r["should_restart"] is True


def test_no_stop_reason_empty_string_restarts():
    r = evaluate_restart_decision("")
    assert r["should_restart"] is True


def test_no_stop_reason_uses_default_delay():
    r = evaluate_restart_decision(None, default_delay_s=45)
    assert r["should_restart"] is True
    assert r["wait_seconds"] == 45.0


# ---------------------------------------------------------------------------
# Hard gate reasons — should NOT restart
# ---------------------------------------------------------------------------

def test_awaiting_resources_no_restart():
    r = evaluate_restart_decision("awaiting_resources")
    assert r["should_restart"] is False


def test_merge_approval_no_restart():
    r = evaluate_restart_decision("merge_approval_required")
    assert r["should_restart"] is False


def test_sql_approval_pending_no_restart():
    r = evaluate_restart_decision("sql_approval_pending")
    assert r["should_restart"] is False


def test_sql_approval_required_no_restart():
    r = evaluate_restart_decision("sql_approval_required")
    assert r["should_restart"] is False


def test_strategic_gate_no_restart():
    r = evaluate_restart_decision("strategic_gate_blocked")
    assert r["should_restart"] is False


def test_git_conflict_no_restart():
    r = evaluate_restart_decision("git_conflict_escalated")
    assert r["should_restart"] is False


def test_preflight_unsafe_no_restart():
    r = evaluate_restart_decision("preflight_unsafe")
    assert r["should_restart"] is False


def test_repo_unhealthy_no_restart():
    r = evaluate_restart_decision("repo_unhealthy")
    assert r["should_restart"] is False


def test_cost_budget_no_restart():
    r = evaluate_restart_decision("loop_blocked_on_cost_budget")
    assert r["should_restart"] is False


def test_cost_budget_exceeded_no_restart():
    r = evaluate_restart_decision("cost_budget_exceeded")
    assert r["should_restart"] is False


def test_hard_gate_reason_field_present():
    r = evaluate_restart_decision("preflight_unsafe")
    assert "hard human gate" in r["reason"]


def test_all_hard_gate_reasons_covered():
    for reason in HARD_GATE_REASONS:
        r = evaluate_restart_decision(reason)
        assert r["should_restart"] is False, f"Expected no restart for {reason!r}"


# ---------------------------------------------------------------------------
# Max restarts ceiling
# ---------------------------------------------------------------------------

def test_max_restarts_zero_unlimited():
    r = evaluate_restart_decision("max_loop_tasks", max_restarts=0, restart_count=999)
    assert r["should_restart"] is True


def test_max_restarts_ceiling_reached():
    r = evaluate_restart_decision("max_loop_tasks", max_restarts=5, restart_count=5)
    assert r["should_restart"] is False
    assert "max_restarts" in r["reason"]


def test_max_restarts_below_ceiling():
    r = evaluate_restart_decision("max_loop_tasks", max_restarts=5, restart_count=4)
    assert r["should_restart"] is True


# ---------------------------------------------------------------------------
# Claude subscription cooldown — with cooldown_until in state
# ---------------------------------------------------------------------------

def test_cooldown_with_future_timestamp_uses_remaining():
    future = _BASE_UTC + timedelta(hours=2)
    state = {"claude_subscription_cooldown_until": future.isoformat()}
    r = evaluate_restart_decision(
        "claude_subscription_cooldown",
        state,
        _now=_BASE_UTC,
    )
    assert r["should_restart"] is True
    # 2 hours + 120s buffer
    assert r["wait_seconds"] >= 7200
    assert r["wait_seconds"] <= 7320 + 1  # small float tolerance


def test_cooldown_with_past_timestamp_uses_buffer_only():
    past = _BASE_UTC - timedelta(minutes=5)
    state = {"claude_subscription_cooldown_until": past.isoformat()}
    r = evaluate_restart_decision(
        "claude_subscription_cooldown",
        state,
        _now=_BASE_UTC,
    )
    assert r["should_restart"] is True
    # remaining = 0 (past), so wait is just the buffer
    assert r["wait_seconds"] == 120.0


def test_cooldown_without_timestamp_falls_back_to_1h():
    r = evaluate_restart_decision("claude_subscription_cooldown", {})
    assert r["should_restart"] is True
    assert r["wait_seconds"] == 3600.0


def test_cooldown_no_state_falls_back_to_1h():
    r = evaluate_restart_decision("claude_subscription_cooldown")
    assert r["should_restart"] is True
    assert r["wait_seconds"] == 3600.0


def test_cooldown_malformed_timestamp_falls_back():
    state = {"claude_subscription_cooldown_until": "not-a-datetime"}
    r = evaluate_restart_decision("claude_subscription_cooldown", state)
    assert r["should_restart"] is True
    assert r["wait_seconds"] == 3600.0


# ---------------------------------------------------------------------------
# Codex usage limit
# ---------------------------------------------------------------------------

def test_codex_usage_limit_restarts_after_1h():
    r = evaluate_restart_decision("loop_blocked_on_codex_usage_limit")
    assert r["should_restart"] is True
    assert r["wait_seconds"] == 3600.0


def test_codex_usage_limit_alt_name():
    r = evaluate_restart_decision("codex_usage_limit")
    assert r["should_restart"] is True
    assert r["wait_seconds"] == 3600.0


# ---------------------------------------------------------------------------
# Empty-queue reasons — restart with long delay
# ---------------------------------------------------------------------------

def test_no_more_tasks_restarts_with_long_delay():
    r = evaluate_restart_decision("no_more_tasks")
    assert r["should_restart"] is True
    assert r["wait_seconds"] == 300.0


def test_no_queued_tasks_restarts_with_long_delay():
    r = evaluate_restart_decision("no_queued_tasks")
    assert r["should_restart"] is True
    assert r["wait_seconds"] == 300.0


def test_seeded_queue_exhausted_restarts_with_long_delay():
    r = evaluate_restart_decision("seeded_queue_exhausted")
    assert r["should_restart"] is True
    assert r["wait_seconds"] == 300.0


# ---------------------------------------------------------------------------
# Normal session endings — short restart
# ---------------------------------------------------------------------------

def test_max_loop_tasks_restarts():
    r = evaluate_restart_decision("max_loop_tasks")
    assert r["should_restart"] is True
    assert r["wait_seconds"] == 30.0


def test_max_runtime_restarts():
    r = evaluate_restart_decision("max_runtime")
    assert r["should_restart"] is True


def test_stale_run_restarts():
    r = evaluate_restart_decision("stale_run")
    assert r["should_restart"] is True


def test_max_consecutive_failures_restarts():
    r = evaluate_restart_decision("max_consecutive_failures")
    assert r["should_restart"] is True


def test_max_repeated_errors_restarts():
    r = evaluate_restart_decision("max_repeated_errors")
    assert r["should_restart"] is True


def test_max_worker_timeouts_restarts():
    r = evaluate_restart_decision("max_worker_timeouts")
    assert r["should_restart"] is True


def test_custom_default_delay_applied():
    r = evaluate_restart_decision("max_loop_tasks", default_delay_s=60)
    assert r["wait_seconds"] == 60.0


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------

def test_result_always_has_all_keys():
    for reason in [None, "max_loop_tasks", "awaiting_resources", "claude_subscription_cooldown"]:
        r = evaluate_restart_decision(reason)
        assert "should_restart" in r
        assert "wait_seconds" in r
        assert "reason" in r


def test_no_restart_wait_seconds_is_zero():
    r = evaluate_restart_decision("awaiting_resources")
    assert r["wait_seconds"] == 0


def test_reason_string_nonempty():
    for stop in [None, "max_loop_tasks", "awaiting_resources"]:
        r = evaluate_restart_decision(stop)
        assert isinstance(r["reason"], str)
        assert len(r["reason"]) > 0


# ---------------------------------------------------------------------------
# Wiring (standalone runner)
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_no_stop_reason_restarts,
        test_no_stop_reason_empty_string_restarts,
        test_no_stop_reason_uses_default_delay,
        test_awaiting_resources_no_restart,
        test_merge_approval_no_restart,
        test_sql_approval_pending_no_restart,
        test_sql_approval_required_no_restart,
        test_strategic_gate_no_restart,
        test_git_conflict_no_restart,
        test_preflight_unsafe_no_restart,
        test_repo_unhealthy_no_restart,
        test_cost_budget_no_restart,
        test_cost_budget_exceeded_no_restart,
        test_hard_gate_reason_field_present,
        test_all_hard_gate_reasons_covered,
        test_max_restarts_zero_unlimited,
        test_max_restarts_ceiling_reached,
        test_max_restarts_below_ceiling,
        test_cooldown_with_future_timestamp_uses_remaining,
        test_cooldown_with_past_timestamp_uses_buffer_only,
        test_cooldown_without_timestamp_falls_back_to_1h,
        test_cooldown_no_state_falls_back_to_1h,
        test_cooldown_malformed_timestamp_falls_back,
        test_codex_usage_limit_restarts_after_1h,
        test_codex_usage_limit_alt_name,
        test_no_more_tasks_restarts_with_long_delay,
        test_no_queued_tasks_restarts_with_long_delay,
        test_seeded_queue_exhausted_restarts_with_long_delay,
        test_max_loop_tasks_restarts,
        test_max_runtime_restarts,
        test_stale_run_restarts,
        test_max_consecutive_failures_restarts,
        test_max_repeated_errors_restarts,
        test_max_worker_timeouts_restarts,
        test_custom_default_delay_applied,
        test_result_always_has_all_keys,
        test_no_restart_wait_seconds_is_zero,
        test_reason_string_nonempty,
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
