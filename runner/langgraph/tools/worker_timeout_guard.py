"""Worker timeout guard.

Tracks how many times the worker process has timed out during the current
session and halts the loop once the total reaches the configured ceiling.
A single timeout is often transient (slow LLM, network blip); repeated
timeouts almost certainly indicate a broken environment — model unreachable,
runner misconfigured, or the task too large for the per-run timeout budget.

Two independent timeout signals are accepted:
- **elapsed_seconds** ≥ ``worker_timeout_threshold`` — the runner measured
  the wall-clock time of the dispatch and it exceeded the per-task ceiling.
- **error text** containing timeout markers produced by
  ``tools/shell_tools.run_command`` (e.g. ``"timed out after"``).

The decision logic here is pure (no disk/network I/O, no state mutation) so
it is unit-testable in isolation; the graph node in
``graph.update_logs_and_state`` does the state mutation around it. This
mirrors the pure-helper + thin-node pattern used by
``tools/failure_guard.py`` and ``tools/repeated_error_guard.py``.
"""
from typing import Optional

WORKER_TIMEOUT_STOP = "worker_timeouts"

_TIMEOUT_MARKERS = ("timed out after", "timeout expired", "timed out")


def _is_timeout_error(error: Optional[str]) -> bool:
    """True when the error string looks like a subprocess timeout."""
    if not error:
        return False
    lower = error.lower()
    return any(marker in lower for marker in _TIMEOUT_MARKERS)


def evaluate_worker_timeout(
    elapsed_seconds: Optional[float],
    error: Optional[str],
    timeout_count: int,
    max_worker_timeouts: int,
    worker_timeout_threshold: int,
) -> dict:
    """Decide whether this worker run was a timeout and whether to halt.

    Args:
        elapsed_seconds: Wall-clock seconds the dispatch_worker node ran.
                         ``None`` when timing was not captured.
        error:           The worker's error string (may be None on success).
        timeout_count:   Timeouts recorded so far this session (not including
                         the current run).
        max_worker_timeouts: Trip the breaker when the new count reaches this.
                             ``<= 0`` disables the guard entirely.
        worker_timeout_threshold: Elapsed-seconds ceiling; a run whose elapsed
                                  time meets or exceeds this counts as a timeout.
                                  ``<= 0`` disables the elapsed-time check.

    Returns a dict with:
        - ``timed_out``     — True if this run counts as a timeout.
        - ``timeout_count`` — Updated count (prior + 1 if timed_out else prior).
        - ``blocked``       — True when the guard should trip.
        - ``stop_reason``   — ``WORKER_TIMEOUT_STOP`` when blocked, else None.
    """
    if max_worker_timeouts <= 0:
        return {
            "timed_out": False,
            "timeout_count": timeout_count,
            "blocked": False,
            "stop_reason": None,
        }

    elapsed_timeout = (
        elapsed_seconds is not None
        and worker_timeout_threshold > 0
        and elapsed_seconds >= worker_timeout_threshold
    )
    timed_out = elapsed_timeout or _is_timeout_error(error)
    new_count = (timeout_count + 1) if timed_out else timeout_count
    blocked = new_count >= max_worker_timeouts

    return {
        "timed_out": timed_out,
        "timeout_count": new_count,
        "blocked": blocked,
        "stop_reason": WORKER_TIMEOUT_STOP if blocked else None,
    }
