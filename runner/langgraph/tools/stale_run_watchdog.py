"""Stale run watchdog.

Detects when the runner has been active for a long time but has not
completed any task recently — a sign that it is stuck in a loop, waiting
on a blocked resource, or otherwise not making forward progress.  This is
especially important for overnight autonomous runs where a human is not
watching and the loop could spin indefinitely without shipping any work.

The watchdog compares ``last_task_completed_at`` (an ISO-8601 UTC timestamp
written to state at the end of each successful task loop) against the current
wall-clock time.  If the gap exceeds ``max_stale_task_minutes`` **and** at
least one task loop has already completed, the guard trips.  We require that
at least one task completed so we do not halt a brand-new run that simply
hasn't gotten to its first task yet.

Design: pure helper ``evaluate_stale_run()`` returns a plain dict with no
I/O, following the same pattern as ``tools/failure_guard.py``.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

STALE_RUN_STOP = "stale_run"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _parse_iso(ts: str) -> Optional[datetime]:
    """Parse an ISO-8601 string produced by ``datetime.utcnow().isoformat()``."""
    if not ts:
        return None
    try:
        # datetime.fromisoformat handles "2025-01-01T12:00:00" and
        # "2025-01-01T12:00:00.123456"; it does NOT require a timezone suffix.
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return None


def evaluate_stale_run(
    last_task_completed_at: Optional[str],
    loop_count: int,
    max_stale_task_minutes: int,
    enabled: bool = True,
) -> dict:
    """Decide whether the runner is stuck without making forward progress.

    Args:
        last_task_completed_at: ISO-8601 UTC timestamp of the last completed
                                task loop, or None if no task has finished yet.
        loop_count:             Total task loops executed so far this session.
        max_stale_task_minutes: Minutes of inactivity that trip the watchdog.
                                ``<= 0`` disables the guard.
        enabled:                Master enable flag; False means no-op.

    Returns a dict with:
        - ``stale``                 — True when inactivity exceeds the threshold.
        - ``stale_minutes``         — Minutes since the last completed task
                                      (``None`` when not computable).
        - ``blocked``               — True when the guard should halt the loop.
        - ``stop_reason``           — ``STALE_RUN_STOP`` when blocked, else None.
    """
    if not enabled or max_stale_task_minutes <= 0:
        return {
            "stale": False,
            "stale_minutes": None,
            "blocked": False,
            "stop_reason": None,
        }

    # Don't trip on a brand-new run that hasn't completed any task yet.
    if not last_task_completed_at or loop_count == 0:
        return {
            "stale": False,
            "stale_minutes": None,
            "blocked": False,
            "stop_reason": None,
        }

    last_dt = _parse_iso(last_task_completed_at)
    if last_dt is None:
        return {
            "stale": False,
            "stale_minutes": None,
            "blocked": False,
            "stop_reason": None,
        }

    elapsed_minutes = (_utcnow() - last_dt).total_seconds() / 60.0
    stale = elapsed_minutes >= max_stale_task_minutes

    return {
        "stale": stale,
        "stale_minutes": round(elapsed_minutes, 1),
        "blocked": stale,
        "stop_reason": STALE_RUN_STOP if stale else None,
    }
