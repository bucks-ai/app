"""Loop watchdog — restart decision logic for the babysitter wrapper.

Pure functions (no I/O, no subprocess, no sleep) so the decision logic is
testable in isolation.  The outer watchdog command in main.py owns the actual
subprocess management, heartbeat emission, and Slack notifications.

Restart policy
--------------
Hard gate reasons (require human action — watchdog does NOT restart):
  awaiting_resources, merge_approval_required, sql_approval_pending,
  strategic_gate_blocked, git_conflict_escalated, preflight_unsafe,
  repo_unhealthy, loop_blocked_on_cost_budget

Long-delay reasons (queue empty — restart after 5 min wait):
  no_more_tasks, no_queued_tasks, seeded_queue_exhausted

Limits-aware restarts (sleep until the quota window resets):
  claude_subscription_cooldown — reads cooldown_until from state for precise wait
  loop_blocked_on_codex_usage_limit — fixed 1-hour wait

Everything else (max_loop_tasks, max_runtime, stale_run, crashes) restarts
immediately with the configured default_delay_s.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

# M4c: stop reasons that require a human to act before the loop can safely
# resume.  Auto-restarting on these would spin-loop forever against a gate
# nobody has unblocked.
HARD_GATE_REASONS = frozenset({
    "awaiting_resources",
    "merge_approval_required",
    "sql_approval_required",
    "sql_approval_pending",
    "strategic_gate_blocked",
    "git_conflict_escalated",
    "preflight_unsafe",
    "repo_unhealthy",
    "loop_blocked_on_cost_budget",
    "cost_budget_exceeded",
    "loop_blocked_on_worker_health",
    "worker_health_blocked",
})

# Queue-empty stops: restart is safe but pointless until new tasks appear.
# Use a 5-min delay so the watchdog doesn't burn CPU polling an empty queue.
_LONG_DELAY_REASONS = frozenset({
    "no_more_tasks",
    "no_queued_tasks",
    "seeded_queue_exhausted",
})

_DEFAULT_RESTART_DELAY_S: int = 30
_NO_TASK_RESTART_DELAY_S: int = 300     # 5 min
_QUOTA_RESTART_DELAY_S: int = 3600      # 1 hour
_COOLDOWN_BUFFER_S: int = 120           # 2-min buffer after cooldown_until


def evaluate_restart_decision(
    stop_reason: Optional[str],
    state: Optional[dict] = None,
    *,
    max_restarts: int = 0,
    restart_count: int = 0,
    default_delay_s: int = _DEFAULT_RESTART_DELAY_S,
    _now: Optional[datetime] = None,
) -> dict:
    """Decide whether the watchdog should restart the loop after it exits.

    Args:
        stop_reason:      stop_reason field from RunnerState, or None when the
                          loop exited unexpectedly (crash / signal).
        state:            Full state dict read from .runtime/state.local.json;
                          used to extract cooldown_until and other context.
        max_restarts:     Hard ceiling on total restarts this watchdog session
                          allows.  0 = unlimited.
        restart_count:    How many times the watchdog has already restarted.
        default_delay_s:  Seconds to wait before a normal restart.
        _now:             Override for UTC now (testing only).

    Returns a dict:
        - ``should_restart``  — True if the watchdog should restart the loop.
        - ``wait_seconds``    — Seconds to wait before restarting (0 if no restart).
        - ``reason``          — Human-readable explanation logged to flight recorder.
    """
    _no_restart = {
        "should_restart": False,
        "wait_seconds": 0,
        "reason": "",
    }

    def _restart(wait: float, reason: str) -> dict:
        return {
            "should_restart": True,
            "wait_seconds": max(0, float(wait)),
            "reason": reason,
        }

    # Respect max_restarts ceiling (0 = unlimited)
    if max_restarts > 0 and restart_count >= max_restarts:
        return {
            **_no_restart,
            "reason": f"max_restarts ({max_restarts}) reached after {restart_count} restarts",
        }

    # No stop_reason = unexpected exit (crash / SIGTERM) → restart promptly
    if not stop_reason:
        return _restart(default_delay_s, "unexpected exit (no stop_reason) — restarting")

    # Hard human gate → stop and wait for human
    if stop_reason in HARD_GATE_REASONS:
        return {**_no_restart, "reason": f"hard human gate: {stop_reason}"}

    # Claude subscription cooldown — use the precise resume timestamp when available
    if stop_reason == "claude_subscription_cooldown":
        cooldown_until = (state or {}).get("claude_subscription_cooldown_until")
        if cooldown_until:
            try:
                resume_dt = datetime.fromisoformat(cooldown_until)
                if resume_dt.tzinfo is None:
                    resume_dt = resume_dt.replace(tzinfo=timezone.utc)
                now = _now or datetime.now(timezone.utc)
                if now.tzinfo is None:
                    now = now.replace(tzinfo=timezone.utc)
                remaining = max(0.0, (resume_dt - now).total_seconds())
                wait = remaining + _COOLDOWN_BUFFER_S
                return _restart(
                    wait,
                    f"claude subscription cooldown — resuming after {cooldown_until}",
                )
            except (ValueError, TypeError):
                pass
        return _restart(
            _QUOTA_RESTART_DELAY_S,
            "claude subscription cooldown — no parsed reset time, waiting 1h",
        )

    # Codex quota exhaustion — fixed 1-hour wait (no reset timestamp available)
    if stop_reason in ("loop_blocked_on_codex_usage_limit", "codex_usage_limit"):
        return _restart(
            _QUOTA_RESTART_DELAY_S,
            "codex usage limit exhausted — waiting 1h before restart",
        )

    # Empty queue — restart is safe but pointless until tasks arrive
    if stop_reason in _LONG_DELAY_REASONS:
        return _restart(
            _NO_TASK_RESTART_DELAY_S,
            f"queue empty ({stop_reason}) — waiting 5 min for new tasks",
        )

    # Everything else (max_loop_tasks, max_runtime, stale_run, failures, …)
    return _restart(
        default_delay_s,
        f"loop exited with stop_reason={stop_reason!r} — restarting",
    )
