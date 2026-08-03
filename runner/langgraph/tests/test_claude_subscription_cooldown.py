"""Unit tests for Claude subscription cooldown auto-resume guard.

Runs standalone:

    python tests/test_claude_subscription_cooldown.py
"""
import os
import sys
import traceback
from datetime import datetime, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.claude_subscription_cooldown import (
    evaluate_subscription_cooldown,
    CLAUDE_COOLDOWN_STOP,
    _is_cooldown_error,
    _parse_wait_seconds,
)


# ── _is_cooldown_error ────────────────────────────────────────────────────────

def test_detects_usage_limit_in_output():
    assert _is_cooldown_error("Claude usage limit reached. Try again later.", None) is True


def test_detects_usage_limit_in_error():
    assert _is_cooldown_error(None, "usage limit exceeded") is True


def test_detects_rate_limit_phrase():
    assert _is_cooldown_error("rate limit exceeded", None) is True


def test_detects_try_again_in():
    assert _is_cooldown_error("please try again in 2 hours", None) is True


def test_detects_overloaded():
    assert _is_cooldown_error("Claude is overloaded with requests", None) is True


def test_no_cooldown_on_normal_output():
    assert _is_cooldown_error("Task completed successfully.", None) is False


def test_no_cooldown_on_none():
    assert _is_cooldown_error(None, None) is False


# ── _parse_wait_seconds ───────────────────────────────────────────────────────

def test_parses_hours_from_output():
    result = _parse_wait_seconds("Try again in 2 hours.", None, 3600)
    assert result == 7200


def test_parses_minutes_from_output():
    result = _parse_wait_seconds("Please wait 30 minutes before retrying.", None, 3600)
    assert result == 1800


def test_parses_resets_in_hours():
    result = _parse_wait_seconds("Your limit resets in 1 hour.", None, 3600)
    assert result == 3600


def test_parses_resets_after_minutes():
    result = _parse_wait_seconds("Usage resets after 45 minutes.", None, 3600)
    assert result == 2700


def test_falls_back_to_default_when_no_duration():
    result = _parse_wait_seconds("Claude usage limit reached.", None, 3600)
    assert result == 3600


def test_default_wait_respected():
    result = _parse_wait_seconds("Some error without timing info.", None, 1800)
    assert result == 1800


# ── evaluate_subscription_cooldown ────────────────────────────────────────────

_FIXED_NOW = datetime(2026, 7, 3, 10, 0, 0)


def test_returns_no_op_when_disabled():
    result = evaluate_subscription_cooldown(
        "Claude usage limit reached", None,
        worker="claude", auth_mode="subscription",
        enabled=False,
        default_wait_s=3600,
        cooldown_count=0,
        max_cooldown_waits=3,
        _now=_FIXED_NOW,
    )
    assert result["detected"] is False
    assert result["cooldown_count"] == 0


def test_returns_no_op_for_non_claude_worker():
    result = evaluate_subscription_cooldown(
        "rate limit exceeded", None,
        worker="codex", auth_mode="subscription",
        enabled=True,
        default_wait_s=3600,
        cooldown_count=0,
        max_cooldown_waits=3,
        _now=_FIXED_NOW,
    )
    assert result["detected"] is False


def test_returns_no_op_for_api_key_mode():
    result = evaluate_subscription_cooldown(
        "Claude usage limit reached", None,
        worker="claude", auth_mode="api_key",
        enabled=True,
        default_wait_s=3600,
        cooldown_count=0,
        max_cooldown_waits=3,
        _now=_FIXED_NOW,
    )
    assert result["detected"] is False


def test_detects_cooldown_in_subscription_mode():
    result = evaluate_subscription_cooldown(
        "Claude usage limit reached. Try again in 1 hour.", None,
        worker="claude", auth_mode="subscription",
        enabled=True,
        default_wait_s=3600,
        cooldown_count=0,
        max_cooldown_waits=3,
        _now=_FIXED_NOW,
    )
    assert result["detected"] is True
    assert result["wait_seconds"] == 3600
    assert result["cooldown_count"] == 1
    assert result["blocked"] is False
    assert result["stop_reason"] is None
    expected_resume = (_FIXED_NOW + timedelta(seconds=3600)).isoformat()
    assert result["resume_at_iso"] == expected_resume


def test_detects_cooldown_with_minute_duration():
    result = evaluate_subscription_cooldown(
        "Please try again in 30 minutes.", None,
        worker="claude", auth_mode="subscription",
        enabled=True,
        default_wait_s=3600,
        cooldown_count=0,
        max_cooldown_waits=3,
        _now=_FIXED_NOW,
    )
    assert result["detected"] is True
    assert result["wait_seconds"] == 1800


def test_uses_default_wait_when_duration_unparseable():
    result = evaluate_subscription_cooldown(
        "Claude usage limit reached.", None,
        worker="claude", auth_mode="subscription",
        enabled=True,
        default_wait_s=900,
        cooldown_count=0,
        max_cooldown_waits=3,
        _now=_FIXED_NOW,
    )
    assert result["detected"] is True
    assert result["wait_seconds"] == 900


def test_increments_cooldown_count():
    result = evaluate_subscription_cooldown(
        "Claude usage limit reached.", None,
        worker="claude", auth_mode="subscription",
        enabled=True,
        default_wait_s=3600,
        cooldown_count=1,
        max_cooldown_waits=3,
        _now=_FIXED_NOW,
    )
    assert result["cooldown_count"] == 2


def test_count_unchanged_when_no_cooldown():
    result = evaluate_subscription_cooldown(
        "Task completed.", None,
        worker="claude", auth_mode="subscription",
        enabled=True,
        default_wait_s=3600,
        cooldown_count=2,
        max_cooldown_waits=3,
        _now=_FIXED_NOW,
    )
    assert result["cooldown_count"] == 2


def test_blocked_when_max_waits_reached():
    result = evaluate_subscription_cooldown(
        "Claude usage limit reached.", None,
        worker="claude", auth_mode="subscription",
        enabled=True,
        default_wait_s=3600,
        cooldown_count=2,
        max_cooldown_waits=3,
        _now=_FIXED_NOW,
    )
    assert result["detected"] is True
    assert result["blocked"] is True
    assert result["stop_reason"] == CLAUDE_COOLDOWN_STOP


def test_not_blocked_below_max_waits():
    result = evaluate_subscription_cooldown(
        "Claude usage limit reached.", None,
        worker="claude", auth_mode="subscription",
        enabled=True,
        default_wait_s=3600,
        cooldown_count=1,
        max_cooldown_waits=3,
        _now=_FIXED_NOW,
    )
    assert result["detected"] is True
    assert result["blocked"] is False


def test_max_waits_zero_disables_limit():
    result = evaluate_subscription_cooldown(
        "Claude usage limit reached.", None,
        worker="claude", auth_mode="subscription",
        enabled=True,
        default_wait_s=3600,
        cooldown_count=100,
        max_cooldown_waits=0,
        _now=_FIXED_NOW,
    )
    assert result["detected"] is True
    assert result["blocked"] is False
    assert result["stop_reason"] is None


# ── Config integration ────────────────────────────────────────────────────────

def test_config_has_cooldown_fields():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "claude_subscription_cooldown_enabled")
    assert hasattr(cfg, "claude_subscription_cooldown_wait_s")
    assert hasattr(cfg, "claude_subscription_cooldown_max_waits")


def test_config_defaults():
    from config import RunnerConfig
    import unittest.mock as mock
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("CLAUDE_SUBSCRIPTION_COOLDOWN", None)
        os.environ.pop("CLAUDE_SUBSCRIPTION_COOLDOWN_WAIT_S", None)
        os.environ.pop("CLAUDE_SUBSCRIPTION_COOLDOWN_MAX_WAITS", None)
        cfg = RunnerConfig()
    assert cfg.claude_subscription_cooldown_enabled is True
    assert cfg.claude_subscription_cooldown_wait_s == 3600
    assert cfg.claude_subscription_cooldown_max_waits == 3


def test_config_from_env():
    from config import RunnerConfig
    import unittest.mock as mock
    with mock.patch.dict(os.environ, {
        "CLAUDE_SUBSCRIPTION_COOLDOWN": "false",
        "CLAUDE_SUBSCRIPTION_COOLDOWN_WAIT_S": "1800",
        "CLAUDE_SUBSCRIPTION_COOLDOWN_MAX_WAITS": "5",
    }):
        cfg = RunnerConfig()
    assert cfg.claude_subscription_cooldown_enabled is False
    assert cfg.claude_subscription_cooldown_wait_s == 1800
    assert cfg.claude_subscription_cooldown_max_waits == 5


def test_config_report_includes_cooldown_fields():
    from config import RunnerConfig
    cfg = RunnerConfig()
    report = cfg.report()
    assert "claude_subscription_cooldown_enabled" in report
    assert "claude_subscription_cooldown_wait_s" in report
    assert "claude_subscription_cooldown_max_waits" in report


# ── State integration ─────────────────────────────────────────────────────────

def test_state_has_cooldown_fields():
    from state import RunnerState
    s = RunnerState()
    assert s.claude_subscription_cooldown_until is None
    assert s.claude_subscription_cooldown_count == 0


def test_state_cooldown_fields_serialise():
    from state import RunnerState
    s = RunnerState(
        claude_subscription_cooldown_until="2026-07-03T11:00:00",
        claude_subscription_cooldown_count=2,
    )
    d = s.model_dump()
    assert d["claude_subscription_cooldown_until"] == "2026-07-03T11:00:00"
    assert d["claude_subscription_cooldown_count"] == 2


if __name__ == "__main__":
    tests = [
        test_detects_usage_limit_in_output,
        test_detects_usage_limit_in_error,
        test_detects_rate_limit_phrase,
        test_detects_try_again_in,
        test_detects_overloaded,
        test_no_cooldown_on_normal_output,
        test_no_cooldown_on_none,
        test_parses_hours_from_output,
        test_parses_minutes_from_output,
        test_parses_resets_in_hours,
        test_parses_resets_after_minutes,
        test_falls_back_to_default_when_no_duration,
        test_default_wait_respected,
        test_returns_no_op_when_disabled,
        test_returns_no_op_for_non_claude_worker,
        test_returns_no_op_for_api_key_mode,
        test_detects_cooldown_in_subscription_mode,
        test_detects_cooldown_with_minute_duration,
        test_uses_default_wait_when_duration_unparseable,
        test_increments_cooldown_count,
        test_count_unchanged_when_no_cooldown,
        test_blocked_when_max_waits_reached,
        test_not_blocked_below_max_waits,
        test_max_waits_zero_disables_limit,
        test_config_has_cooldown_fields,
        test_config_defaults,
        test_config_from_env,
        test_config_report_includes_cooldown_fields,
        test_state_has_cooldown_fields,
        test_state_cooldown_fields_serialise,
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
