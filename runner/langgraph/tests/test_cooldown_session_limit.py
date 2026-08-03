"""Regression tests for the 2026-07-06 M0.9 overnight failure.

The Claude CLI's subscription rate-limit message changed wording to
"You've hit your session limit · resets 4am (America/New_York)".  None of the
existing _COOLDOWN_MARKERS matched, so the cooldown guard never fired, the
429s were counted as ordinary worker failures, and the failure guard halted
the loop at 3 consecutive failures (loop_stopped: consecutive_failures at
2026-07-06T06:45:52 — see logs/runs.jsonl lines 7173/7191/7203).

These tests pin:
1. Marker detection of the new "session limit" wording.
2. Wording-independent detection via "api_error_status": 429 in the CLI JSON.
3. Absolute-time parsing of "resets 4am" (no "at", timezone in parens).
4. End-to-end evaluate_subscription_cooldown detection on the real payload.
"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from tools.claude_subscription_cooldown import (
    _is_cooldown_error,
    _parse_wait_seconds,
    evaluate_subscription_cooldown,
)

# Verbatim (truncated) CLI output captured from logs/runs.jsonl line 7173.
REAL_PAYLOAD = (
    '{"type":"result","subtype":"success","is_error":true,'
    '"api_error_status":429,"duration_ms":18204,"duration_api_ms":18509,'
    '"num_turns":7,'
    '"result":"You\'ve hit your session limit · resets 4am (America/New_York)",'
    '"stop_reason":"stop_sequence",'
    '"session_id":"7583da26-588f-48e9-b8d3-b4a9c842a065",'
    '"total_cost_usd":0.1503279}'
)


def test_detects_new_session_limit_wording():
    assert _is_cooldown_error(REAL_PAYLOAD, None) is True


def test_detects_session_limit_in_error_field():
    assert _is_cooldown_error(None, "You've hit your session limit · resets 4am") is True


def test_detects_api_error_status_429_regardless_of_wording():
    # If Anthropic rewrites the message entirely, the 429 status still triggers.
    payload = '{"is_error":true,"api_error_status":429,"result":"some brand new copy"}'
    assert _is_cooldown_error(payload, None) is True
    spaced = '{"api_error_status": 429}'
    assert _is_cooldown_error(spaced, None) is True


def test_non_cooldown_output_still_ignored():
    assert _is_cooldown_error('{"is_error":true,"result":"SyntaxError in foo.py"}', None) is False
    assert _is_cooldown_error(None, "Command failed with exit code 1") is False


def test_parses_resets_4am_without_at():
    # Local clock 2:45am → "resets 4am" is 1h15m away (+120s resume buffer).
    local_now = datetime(2026, 7, 6, 2, 45, 0)
    wait = _parse_wait_seconds(REAL_PAYLOAD, None, default_wait_s=1800, local_now=local_now)
    assert wait == 75 * 60 + 120


def test_parses_resets_with_minutes_and_meridiem():
    local_now = datetime(2026, 7, 6, 2, 0, 0)
    wait = _parse_wait_seconds("session limit · resets 4:30pm", None, 1800, local_now=local_now)
    assert wait == (14 * 3600 + 30 * 60) + 120


def test_end_to_end_detection_on_real_payload():
    result = evaluate_subscription_cooldown(
        REAL_PAYLOAD,
        None,
        worker="claude",
        auth_mode="subscription",
        enabled=True,
        default_wait_s=1800,
        cooldown_count=0,
        max_cooldown_waits=0,
        _local_now=datetime(2026, 7, 6, 2, 45, 0),
    )
    assert result["detected"] is True
    assert result["blocked"] is False
    assert result["cooldown_count"] == 1
    assert result["wait_seconds"] == 75 * 60 + 120


def test_end_to_end_not_detected_for_api_key_mode():
    # Guard only applies in subscription mode.
    result = evaluate_subscription_cooldown(
        REAL_PAYLOAD,
        None,
        worker="claude",
        auth_mode="api_key",
        enabled=True,
        default_wait_s=1800,
        cooldown_count=0,
        max_cooldown_waits=0,
    )
    assert result["detected"] is False
