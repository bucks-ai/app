"""Final live-batch validation report.

Produces a structured summary at the end of an autonomous batch run:
  - task-level outcomes (complete, failed, blocked, queued)
  - session health metrics (cost, loop count, stop reason, elapsed time)
  - per-task digest (up to 50 entries)

Written to outbox/live_batch_validation_report.txt and logged as
``live_batch_validation_complete``.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from tools.log_tools import log_event
from tools.task_tools import load_tasks


# ---------------------------------------------------------------------------
# Metrics aggregation
# ---------------------------------------------------------------------------

def collect_batch_metrics(tasks: list[dict]) -> dict:
    """Aggregate task outcomes from a task list into a metrics dict.

    Returns:
        total        — total number of tasks in the queue
        complete     — tasks that reached "complete"
        failed       — tasks that reached "failed"
        blocked      — tasks blocked on a human action
        queued       — tasks that never ran (still queued)
        running      — tasks still marked running (stale)
        success_rate — fraction of tasks that completed (0.0–1.0)
        failure_rate — fraction that failed or were blocked
    """
    total = len(tasks)
    counts: dict = {
        "complete": 0,
        "failed": 0,
        "blocked": 0,
        "queued": 0,
        "running": 0,
    }
    for task in tasks:
        status = task.get("status", "unknown")
        if status in counts:
            counts[status] += 1
        else:
            counts.setdefault(status, 0)
            counts[status] += 1

    success_rate = counts["complete"] / total if total > 0 else 0.0
    failure_rate = (counts["failed"] + counts["blocked"]) / total if total > 0 else 0.0

    return {
        "total": total,
        **counts,
        "success_rate": round(success_rate, 3),
        "failure_rate": round(failure_rate, 3),
    }


def compute_elapsed_minutes(started_at: Optional[str]) -> Optional[float]:
    """Return elapsed minutes from started_at to now, or None if unavailable."""
    if not started_at:
        return None
    try:
        start = datetime.fromisoformat(started_at)
        now = datetime.utcnow()
        return round((now - start).total_seconds() / 60, 1)
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# Report formatter
# ---------------------------------------------------------------------------

_STATUS_ICON = {
    "complete": "+",
    "failed": "x",
    "blocked": "!",
    "queued": "~",
    "running": ">",
}

_MAX_TASK_LINES = 50


def format_batch_report(
    batch_metrics: dict,
    session_state: dict,
    tasks: list[dict],
) -> str:
    """Build a human-readable live-batch validation report string."""
    stop_reason = session_state.get("stop_reason") or "none"
    loop_count = int(session_state.get("loop_count") or 0)
    session_cost = float(session_state.get("session_cost") or 0.0)
    worker_timeout_count = int(session_state.get("worker_timeout_count") or 0)
    consecutive_failures = int(session_state.get("consecutive_failures") or 0)
    elapsed = compute_elapsed_minutes(session_state.get("started_at"))
    elapsed_str = f"{elapsed:.1f} min" if elapsed is not None else "unknown"

    success_pct = batch_metrics.get("success_rate", 0.0) * 100

    lines = [
        "=" * 60,
        "Live-Batch Validation Report",
        "=" * 60,
        "",
        "Session",
        "-" * 40,
        f"  Stop reason     : {stop_reason}",
        f"  Loop count      : {loop_count}",
        f"  Session cost    : ${session_cost:.4f}",
        f"  Elapsed         : {elapsed_str}",
        f"  Worker timeouts : {worker_timeout_count}",
        f"  Consec failures : {consecutive_failures}",
        "",
        "Task Outcomes",
        "-" * 40,
        f"  Total   : {batch_metrics.get('total', 0)}",
        f"  Complete: {batch_metrics.get('complete', 0)}  ({success_pct:.1f}%)",
        f"  Failed  : {batch_metrics.get('failed', 0)}",
        f"  Blocked : {batch_metrics.get('blocked', 0)}",
        f"  Queued  : {batch_metrics.get('queued', 0)}  (did not run)",
    ]

    if tasks:
        lines.append("")
        lines.append("Per-Task Summary")
        lines.append("-" * 40)
        for task in tasks[:_MAX_TASK_LINES]:
            tid = (task.get("id") or "?")[:20]
            title = (task.get("title") or "")[:55]
            status = task.get("status", "?")
            icon = _STATUS_ICON.get(status, "?")
            lines.append(f"  [{icon}] {tid:<20} {status:<10} {title}")
        if len(tasks) > _MAX_TASK_LINES:
            lines.append(f"  ... and {len(tasks) - _MAX_TASK_LINES} more task(s)")

    lines.append("")
    lines.append("=" * 60)
    lines.append("")

    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Top-level generator
# ---------------------------------------------------------------------------

def generate_live_batch_report(
    session_state: dict,
    *,
    context: str = "",
) -> dict:
    """Generate the final live-batch validation report.

    Args:
        session_state — dict with loop_count, session_cost, stop_reason,
                        started_at, consecutive_failures, worker_timeout_count
        context       — caller label for log events

    Returns:
        report      — human-readable text (str)
        metrics     — batch_metrics dict (task counts + rates)
        passed      — True when success_rate >= 0.5
        stop_reason — from session_state
    """
    tasks = load_tasks()
    batch_metrics = collect_batch_metrics(tasks)
    report = format_batch_report(batch_metrics, session_state, tasks)

    stop_reason = session_state.get("stop_reason") or "none"
    passed = batch_metrics.get("success_rate", 0.0) >= 0.5

    log_event("live_batch_validation_complete", {
        "stop_reason": stop_reason,
        "loop_count": session_state.get("loop_count"),
        "session_cost": session_state.get("session_cost"),
        "metrics": batch_metrics,
        "passed": passed,
        "context": context,
    })

    return {
        "report": report,
        "metrics": batch_metrics,
        "passed": passed,
        "stop_reason": stop_reason,
    }
