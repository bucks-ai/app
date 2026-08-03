# DESTINATION: runner/langgraph/tests/test_cooldown_absolute_time.py  (new file)
"""Tests for absolute clock-time parsing in the subscription cooldown guard (v2)."""
from datetime import datetime

from tools.claude_subscription_cooldown import (
    CLAUDE_COOLDOWN_STOP,
    evaluate_subscription_cooldown,
)

LOCAL_NOON = datetime(2026, 7, 5, 12, 0, 0)   # local clock
UTC_NOW = datetime(2026, 7, 5, 19, 0, 0)      # arbitrary UTC anchor


def _eval(text, max_waits=0, count=0, local_now=LOCAL_NOON):
    return evaluate_subscription_cooldown(
        output=text,
        error=None,
        worker="claude",
        auth_mode="subscription",
        enabled=True,
        default_wait_s=3600,
        cooldown_count=count,
        max_cooldown_waits=max_waits,
        _now=UTC_NOW,
        _local_now=local_now,
    )


class TestAbsoluteTimeParsing:
    def test_reset_at_pm_time(self):
        r = _eval("Claude usage limit reached. Your limit will reset at 6pm.")
        assert r["detected"] is True
        # noon -> 6pm = 6h, plus 120s buffer
        assert r["wait_seconds"] == 6 * 3600 + 120

    def test_reset_at_time_with_minutes(self):
        r = _eval("Claude usage limit reached. Your limit will reset at 3:30pm.")
        assert r["wait_seconds"] == 3 * 3600 + 30 * 60 + 120

    def test_reset_time_in_past_rolls_to_next_day(self):
        r = _eval("Claude usage limit reached. Your limit will reset at 9am.")
        # 9am already passed at local noon -> tomorrow 9am = 21h
        assert r["wait_seconds"] == 21 * 3600 + 120

    def test_reset_at_time_with_timezone_suffix(self):
        r = _eval(
            "Claude usage limit reached. Your limit will reset at 6pm (America/Los_Angeles)."
        )
        assert r["wait_seconds"] == 6 * 3600 + 120

    def test_midnight_and_noon_edge_cases(self):
        r_noon_plus = _eval("usage limit reached — resets at 12:15pm")
        assert r_noon_plus["wait_seconds"] == 15 * 60 + 120
        r_midnight = _eval("usage limit reached — resets at 12am")
        assert r_midnight["wait_seconds"] == 12 * 3600 + 120

    def test_relative_duration_still_wins_over_absolute(self):
        r = _eval(
            "usage limit reached. Try again in 2 hours (limit resets at 6pm)."
        )
        assert r["wait_seconds"] == 2 * 3600

    def test_unparseable_falls_back_to_default(self):
        r = _eval("Claude usage limit reached. Please slow down.")
        assert r["wait_seconds"] == 3600

    def test_max_waits_zero_never_blocks(self):
        r = _eval(
            "Your limit will reset at 6pm.", max_waits=0, count=99
        )
        assert r["blocked"] is False
        assert r["stop_reason"] is None
        assert r["cooldown_count"] == 100

    def test_max_waits_still_blocks_when_positive(self):
        r = _eval("Your limit will reset at 6pm.", max_waits=3, count=2)
        assert r["blocked"] is True
        assert r["stop_reason"] == CLAUDE_COOLDOWN_STOP


class TestGuardScopeUnchanged:
    def test_api_key_mode_is_noop(self):
        r = evaluate_subscription_cooldown(
            output="usage limit reached",
            error=None,
            worker="claude",
            auth_mode="api_key",
            enabled=True,
            default_wait_s=3600,
            cooldown_count=0,
            max_cooldown_waits=3,
        )
        assert r["detected"] is False

    def test_non_claude_worker_is_noop(self):
        r = evaluate_subscription_cooldown(
            output="usage limit reached",
            error=None,
            worker="codex",
            auth_mode="subscription",
            enabled=True,
            default_wait_s=3600,
            cooldown_count=0,
            max_cooldown_waits=3,
        )
        assert r["detected"] is False
