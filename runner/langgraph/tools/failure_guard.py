"""Failure & retry guard.

When a worker fails, the runner must not just record a bare failure and barrel
on — that loses transient-failure work and lets a broken run burn its whole
loop/runtime budget producing more failures. This guard adds two protections:

1. **Per-task retry** — a failed task is requeued (status → ``queued``, its
   ``retry_count`` bumped) up to ``max_task_retries`` times before being marked
   permanently ``failed``. A transient failure (flaky check, timeout) then gets
   another attempt instead of being abandoned.
2. **Consecutive-failure circuit breaker** — the runner tracks how many tasks
   have failed back-to-back. Once that reaches ``max_consecutive_failures`` the
   guard trips and sets ``stop_reason`` so the loop halts cleanly at
   ``decide_continue_or_stop`` rather than piling new tasks onto a run that's
   clearly going sideways. Any successful task resets the counter.

The decision logic here is pure (no disk/network I/O, no state mutation) so it
is unit-testable in isolation; the graph node in ``graph.update_logs_and_state``
does the requeue/mark-failed I/O and state mutation around it. This mirrors the
pure-helper + thin-node split used by ``tools/resource_gate.py``.
"""
from typing import Optional


# Sentinel stop reason set when the circuit breaker trips, surfaced by
# decide_continue_or_stop / loop_stopped and matched by tests.
CONSECUTIVE_FAILURES_STOP = "consecutive_failures"


def task_retry_count(task: Optional[dict]) -> int:
    """Return how many times this task has already been retried (0 if never).

    Tolerates a missing/garbage ``retry_count`` (older task records won't have
    one) by treating anything non-int-coercible as 0.
    """
    if not task:
        return 0
    try:
        return max(0, int(task.get("retry_count", 0) or 0))
    except (TypeError, ValueError):
        return 0


def evaluate_failure(
    task: Optional[dict],
    consecutive_failures: int,
    max_task_retries: int,
    max_consecutive_failures: int,
) -> dict:
    """Decide what to do about a just-failed task.

    ``consecutive_failures`` is the count *before* this failure. Returns:

    - ``action``       — ``"retry"`` (requeue for another attempt) or
                         ``"give_up"`` (mark permanently failed).
    - ``retry_count``  — the new retry count to persist on the task when
                         retrying (the prior count + 1); the prior count
                         unchanged when giving up.
    - ``consecutive_failures`` — the new running count (prior + 1).
    - ``circuit_open`` — whether the consecutive-failure breaker has tripped.
    - ``stop_reason``  — ``CONSECUTIVE_FAILURES_STOP`` when the breaker tripped,
                         else ``None``.

    Retry and the circuit breaker are independent: a task can be requeued for a
    retry *and* still trip the breaker (so the requeued task is preserved for the
    next run while this run halts).
    """
    prior_retries = task_retry_count(task)
    new_consecutive = consecutive_failures + 1

    if max_task_retries > 0 and prior_retries < max_task_retries:
        action = "retry"
        retry_count = prior_retries + 1
    else:
        action = "give_up"
        retry_count = prior_retries

    # max_consecutive_failures <= 0 disables the breaker entirely.
    circuit_open = max_consecutive_failures > 0 and new_consecutive >= max_consecutive_failures

    return {
        "action": action,
        "retry_count": retry_count,
        "consecutive_failures": new_consecutive,
        "circuit_open": circuit_open,
        "stop_reason": CONSECUTIVE_FAILURES_STOP if circuit_open else None,
    }
