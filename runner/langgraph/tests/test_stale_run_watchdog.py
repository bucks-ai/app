"""Unit tests for the stale run watchdog.

Runs standalone (no pytest dependency):

    python tests/test_stale_run_watchdog.py

Covers ``evaluate_stale_run()`` in ``tools/stale_run_watchdog.py``.
Wall-clock time (``_utcnow``) is monkey-patched so tests run deterministically
without real delays.
"""
import os
import sys
import traceback
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tools.stale_run_watchdog as srw
from tools.stale_run_watchdog import evaluate_stale_run, STALE_RUN_STOP


def _set_now(dt: datetime):
    """Patch ``_utcnow`` to return a fixed datetime."""
    srw._utcnow = lambda: dt


def _ts(dt: datetime) -> str:
    return dt.isoformat()


_BASE = datetime(2025, 6, 1, 10, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Guard disabled
# ---------------------------------------------------------------------------

def test_disabled_max_zero():
    r = evaluate_stale_run(
        last_task_completed_at=_ts(_BASE - timedelta(hours=5)),
        loop_count=10,
        max_stale_task_minutes=0,
    )
    assert r["stale"] is False
    assert r["blocked"] is False
    assert r["stop_reason"] is None


def test_disabled_flag():
    r = evaluate_stale_run(
        last_task_completed_at=_ts(_BASE - timedelta(hours=5)),
        loop_count=10,
        max_stale_task_minutes=30,
        enabled=False,
    )
    assert r["stale"] is False
    assert r["blocked"] is False


# ---------------------------------------------------------------------------
# No completed tasks yet — should not trip
# ---------------------------------------------------------------------------

def test_no_completed_task_yet_none_timestamp():
    _set_now(_BASE)
    r = evaluate_stale_run(
        last_task_completed_at=None,
        loop_count=5,
        max_stale_task_minutes=30,
    )
    assert r["stale"] is False
    assert r["stale_minutes"] is None


def test_no_completed_task_yet_zero_loop_count():
    _set_now(_BASE)
    r = evaluate_stale_run(
        last_task_completed_at=_ts(_BASE - timedelta(hours=2)),
        loop_count=0,
        max_stale_task_minutes=30,
    )
    assert r["stale"] is False


# ---------------------------------------------------------------------------
# Healthy: completed recently
# ---------------------------------------------------------------------------

def test_healthy_run_not_stale():
    now = _BASE
    _set_now(now)
    last = now - timedelta(minutes=20)
    r = evaluate_stale_run(
        last_task_completed_at=_ts(last),
        loop_count=3,
        max_stale_task_minutes=60,
    )
    assert r["stale"] is False
    assert r["blocked"] is False
    assert r["stop_reason"] is None
    assert r["stale_minutes"] is not None
    assert r["stale_minutes"] < 60


# ---------------------------------------------------------------------------
# Stale: inactivity exceeds threshold
# ---------------------------------------------------------------------------

def test_stale_run_trips_watchdog():
    now = _BASE
    _set_now(now)
    last = now - timedelta(minutes=61)
    r = evaluate_stale_run(
        last_task_completed_at=_ts(last),
        loop_count=5,
        max_stale_task_minutes=60,
    )
    assert r["stale"] is True
    assert r["blocked"] is True
    assert r["stop_reason"] == STALE_RUN_STOP
    assert r["stale_minutes"] >= 61


def test_stale_exact_boundary_triggers():
    now = _BASE
    _set_now(now)
    last = now - timedelta(minutes=60)
    r = evaluate_stale_run(
        last_task_completed_at=_ts(last),
        loop_count=1,
        max_stale_task_minutes=60,
    )
    assert r["stale"] is True


def test_stale_one_second_short_does_not_trigger():
    now = _BASE
    _set_now(now)
    last = now - timedelta(seconds=3599)  # 59m 59s
    r = evaluate_stale_run(
        last_task_completed_at=_ts(last),
        loop_count=2,
        max_stale_task_minutes=60,
    )
    assert r["stale"] is False


# ---------------------------------------------------------------------------
# Malformed timestamp — should not crash
# ---------------------------------------------------------------------------

def test_malformed_timestamp_does_not_crash():
    _set_now(_BASE)
    r = evaluate_stale_run(
        last_task_completed_at="not-a-date",
        loop_count=3,
        max_stale_task_minutes=30,
    )
    assert r["stale"] is False
    assert r["blocked"] is False


def test_empty_string_timestamp():
    _set_now(_BASE)
    r = evaluate_stale_run(
        last_task_completed_at="",
        loop_count=3,
        max_stale_task_minutes=30,
    )
    assert r["stale"] is False


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_disabled_max_zero,
        test_disabled_flag,
        test_no_completed_task_yet_none_timestamp,
        test_no_completed_task_yet_zero_loop_count,
        test_healthy_run_not_stale,
        test_stale_run_trips_watchdog,
        test_stale_exact_boundary_triggers,
        test_stale_one_second_short_does_not_trigger,
        test_malformed_timestamp_does_not_crash,
        test_empty_string_timestamp,
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
