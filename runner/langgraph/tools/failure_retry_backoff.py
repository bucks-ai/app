"""Failure retry backoff for degraded worker conditions.

When a worker fails under degraded conditions (timeout, health-probe failure,
or sustained consecutive failures), an immediate retry will likely hit the
same wall again.  This tool computes an exponential-backoff delay before the
task is retried, giving the environment time to recover.

Degradation signals:
- Error text contains a timeout or health-probe marker.
- Wall-clock elapsed time exceeded the worker timeout threshold.
- More than one consecutive failure in the session (sustained trouble).

Design: pure ``is_degraded_failure``, ``compute_backoff``, and
``compute_retry_not_before`` helpers with no disk/network I/O, mirroring the
pure-helper + thin-node split used by ``tools/failure_guard.py``.  The graph
node in ``graph.update_logs_and_state`` calls these helpers and passes the
resulting ``retry_not_before`` timestamp to ``task_tools.requeue_task``.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from typing import Optional

_DEGRADED_MARKERS = (
    "timed out",
    "timeout",
    "binary not found",
    "not found on path",
    "health probe",
    "cli binary not found",
)


def is_degraded_failure(
    error: Optional[str],
    worker_elapsed_seconds: Optional[float],
    worker_timeout_threshold: int,
    consecutive_failures: int,
) -> bool:
    """Return True when the failure looks like a degraded-worker condition.

    Degraded means: timeout, missing binary/credential, or the runner has
    seen more than one consecutive failure (indicating sustained trouble
    rather than a one-off flake).
    """
    if error:
        lower = error.lower()
        if any(marker in lower for marker in _DEGRADED_MARKERS):
            return True
    if (
        worker_elapsed_seconds is not None
        and worker_timeout_threshold > 0
        and worker_elapsed_seconds >= worker_timeout_threshold
    ):
        return True
    if consecutive_failures > 1:
        return True
    return False


def compute_backoff(
    attempt: int,
    base_s: float,
    multiplier: float,
    max_s: float,
) -> float:
    """Compute backoff delay in seconds for the given 1-based attempt number.

    Formula: ``base_s * multiplier^(attempt - 1)``, capped at ``max_s``.
    Returns 0.0 when any parameter is non-positive or attempt < 1.
    """
    if base_s <= 0 or multiplier <= 0 or max_s <= 0 or attempt < 1:
        return 0.0
    delay = base_s * (multiplier ** (attempt - 1))
    return min(delay, max_s)


def compute_retry_not_before(
    attempt: int,
    base_s: float,
    multiplier: float,
    max_s: float,
    *,
    _now: Optional[datetime] = None,
) -> Optional[str]:
    """Return the ISO-8601 UTC timestamp after which this task may be retried.

    Returns ``None`` when the computed backoff delay is 0 (disabled or
    attempt < 1), meaning the task can be retried immediately.
    """
    delay = compute_backoff(attempt, base_s, multiplier, max_s)
    if delay <= 0:
        return None
    now = _now or datetime.utcnow()
    return (now + timedelta(seconds=delay)).isoformat()
