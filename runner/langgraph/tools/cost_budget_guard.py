"""Cost and budget tracking guard.

Tracks cumulative API spend across all worker runs in a session and halts
the loop once either a per-task limit or a session-wide budget ceiling is
exceeded. When a worker does not report actual cost (the common case for
CLI-mode workers), a configurable per-task estimate is used as a proxy so
the guard degrades gracefully to a rough run-count budget.

Setting both ``max_session_cost_dollars`` and ``max_task_cost_dollars`` to
0.0 (the default) disables all hard stops; the guard then records cost events
for observability only when ``estimated_cost_per_task_dollars`` > 0.

The decision logic is pure (no I/O, no state mutation) for the same reason
as the other guards — unit-testable in isolation, with graph wiring kept in
``graph.update_logs_and_state``.
"""

COST_BUDGET_STOP = "cost_budget_exceeded"


def evaluate_cost_budget(
    task_cost: float,
    session_cost: float,
    max_session_cost: float,
    max_task_cost: float,
) -> dict:
    """Decide whether cost thresholds have been exceeded.

    Args:
        task_cost:        Cost attributed to this worker run (0.0 if unknown).
        session_cost:     Cumulative cost *before* this task.
        max_session_cost: Session ceiling in dollars. ``<= 0`` disables the
                          session-level check.
        max_task_cost:    Per-task ceiling in dollars. ``<= 0`` disables the
                          per-task check.

    Returns a dict with:
        - ``task_cost``        — Resolved task cost (input, unchanged).
        - ``session_cost``     — Updated cumulative cost (prior + task_cost).
        - ``task_exceeded``    — True when task_cost > max_task_cost (and check enabled).
        - ``session_exceeded`` — True when new session_cost >= max_session_cost (and check enabled).
        - ``blocked``          — True when either threshold is exceeded.
        - ``stop_reason``      — ``COST_BUDGET_STOP`` when blocked, else None.
    """
    new_session_cost = session_cost + task_cost
    task_exceeded = max_task_cost > 0 and task_cost > max_task_cost
    session_exceeded = max_session_cost > 0 and new_session_cost >= max_session_cost
    blocked = task_exceeded or session_exceeded

    return {
        "task_cost": task_cost,
        "session_cost": new_session_cost,
        "task_exceeded": task_exceeded,
        "session_exceeded": session_exceeded,
        "blocked": blocked,
        "stop_reason": COST_BUDGET_STOP if blocked else None,
    }
