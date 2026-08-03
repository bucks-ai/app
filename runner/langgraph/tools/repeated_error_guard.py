"""Repeated-error and repeated-task guards.

Two complementary guards that catch infinite loops the failure-guard circuit
breaker misses:

1. **Repeated-error guard** — identical (or nearly identical) error messages
   appearing across multiple tasks signal a systemic issue the runner cannot
   self-repair (broken environment, missing dependency, invalid config). Once the
   same error appears ``max_repeated_errors`` times within the recent history
   window the guard trips and sets ``stop_reason`` so the loop halts cleanly.

2. **Repeated-task guard** — tracks how many times each task ID has been run in
   the current session. If the same task is attempted more than
   ``max_task_attempts`` times (regardless of success/failure) the guard halts
   the loop: a task cycling through the queue indefinitely wastes loop budget and
   indicates an unresolvable problem (planner re-queuing the same task, a bug in
   the task queue mutation logic, etc.).

Both helpers are pure (no disk/network I/O, no state mutation) so they are
unit-testable in isolation, following the same pure-helper + thin-node pattern as
``tools/failure_guard.py`` and ``tools/resource_gate.py``.
"""

REPEATED_ERROR_STOP = "repeated_errors"
REPEATED_TASK_STOP = "repeated_task"


def _errors_match(a: str, b: str) -> bool:
    """True when two error strings are similar enough to count as the same error.

    Uses case-insensitive substring containment: if the shorter string (>=10
    chars) is contained in the longer one they are considered the same error.
    Short strings (<10 chars) must match exactly to avoid false positives from
    generic tokens like "error" or "failed".
    """
    a = (a or "").lower().strip()
    b = (b or "").lower().strip()
    if not a or not b:
        return False
    if a == b:
        return True
    if len(a) >= 10 and len(b) >= 10:
        shorter, longer = (a, b) if len(a) <= len(b) else (b, a)
        return shorter in longer
    return False


def evaluate_error_repetition(
    error: str,
    error_history: list,
    max_repeated_errors: int,
    window: int,
) -> dict:
    """Decide whether the current error has appeared too many times recently.

    ``error_history`` is a list of ``{"error": str, "task_id": str}`` records
    from prior failures in this session (not including the current one).
    ``window`` limits how far back to look (0 = unbounded).
    ``max_repeated_errors <= 0`` disables the guard entirely.

    The current error itself counts as one occurrence, so setting
    ``max_repeated_errors=3`` trips on the third time the same error is seen.

    Returns:
    - ``blocked``     — True when the guard should trip.
    - ``stop_reason`` — ``REPEATED_ERROR_STOP`` when blocked, else ``None``.
    - ``match_count`` — total occurrences including the current one.
    """
    if max_repeated_errors <= 0:
        return {"blocked": False, "stop_reason": None, "match_count": 0}

    recent = error_history[-window:] if window > 0 else list(error_history)
    prior_matches = sum(
        1 for entry in recent
        if _errors_match(error, entry.get("error") or "")
    )
    total = prior_matches + 1  # +1 for the current occurrence

    blocked = total >= max_repeated_errors
    return {
        "blocked": blocked,
        "stop_reason": REPEATED_ERROR_STOP if blocked else None,
        "match_count": total,
    }


def evaluate_task_repetition(
    task_id: str,
    task_attempt_counts: dict,
    max_task_attempts: int,
) -> dict:
    """Decide whether task_id has been attempted too many times.

    ``task_attempt_counts`` maps task IDs to the number of times they have
    already been run (not yet including the current attempt).
    ``max_task_attempts <= 0`` disables the guard entirely.

    Returns:
    - ``blocked``       — True when the guard should trip (attempt_count > max).
    - ``stop_reason``   — ``REPEATED_TASK_STOP`` when blocked, else ``None``.
    - ``attempt_count`` — the new attempt count after recording this run.
    """
    if max_task_attempts <= 0:
        return {"blocked": False, "stop_reason": None, "attempt_count": 0}

    prior = (task_attempt_counts or {}).get(task_id, 0)
    new_count = prior + 1
    blocked = new_count > max_task_attempts

    return {
        "blocked": blocked,
        "stop_reason": REPEATED_TASK_STOP if blocked else None,
        "attempt_count": new_count,
    }
