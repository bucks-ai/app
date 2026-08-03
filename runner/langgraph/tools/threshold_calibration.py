"""Threshold calibration — derive runner timeouts from observed run history.

Every timeout in ``config.py`` used to be a guess.  Guesses cascade: a
threshold set below the real p95 turns a healthy long run into a "timeout",
the timeout turns into a failed task, the failed task turns into a stale run,
and the stale run kills the session.  This module replaces the guessing with
measurement over ``logs/runs.jsonl``.

What it measures, and which config value each measurement calibrates:

- ``worker_finished.elapsed_seconds``      → ``CLAUDE_CLI_TIMEOUT_S``,
                                             ``WORKER_TIMEOUT_THRESHOLD``
- ``pr_checks_completed.elapsed``          → ``PR_CHECKS_TIMEOUT_S``
- ``pr_checks_poll_tick`` (first tick with
  ``total > 0``)                           → ``PR_CHECKS_EMPTY_GRACE_S``
- ``task_loaded`` → ``task_completed``     → ``MAX_STALE_TASK_MINUTES``,
                                             ``STALE_RUN_WARN_MINUTES``
- span between log-activity gaps           → ``MAX_RUNTIME_MINUTES``

Design: pure functions over an event iterable, no I/O beyond reading the log,
so the summaries are unit-testable against synthetic events.  Every summary
carries its own sample count (``n``) — a p95 over 4 samples is not evidence,
and the report must let a reader see that for themselves.

Regenerate the audit document with::

    python -m tools.threshold_calibration > ../../docs/M4C0-THRESHOLD-CALIBRATION.md
"""
from __future__ import annotations

import bisect
import json
from datetime import datetime
from pathlib import Path
from typing import Iterable, Iterator, Optional

# Wall-clock silence longer than this splits the log into separate loop
# sessions.  The runner is not running between sessions, so the gap is idle
# operator time, not runtime that MAX_RUNTIME_MINUTES needs to cover.
SESSION_GAP_SECONDS = 30 * 60

# Log silence longer than this inside a single task's window means the loop
# stopped mid-task, not that a worker was quietly working: no single worker run
# can exceed the CLI hard-kill ceiling, and this sits comfortably above it.
MAX_TASK_SILENCE_SECONDS = 60 * 60

# A worker run that finished within this margin of a known CLI ceiling was
# almost certainly killed *by* that ceiling rather than finishing on its own.
# Such samples right-censor the distribution: the true duration is unknown and
# at least this large, so a p95 computed over them understates the real tail.
CENSOR_MARGIN_SECONDS = 15.0


def percentile(sorted_values: list, q: float) -> Optional[float]:
    """Nearest-rank percentile over an already-sorted list.

    Nearest-rank (rather than interpolated) is deliberate: every reported
    number is an observation that actually happened, which is what makes the
    report auditable against the raw log.
    """
    if not sorted_values:
        return None
    idx = int(round(q * (len(sorted_values) - 1)))
    return sorted_values[max(0, min(idx, len(sorted_values) - 1))]


def summarize(values: Iterable[float]) -> dict:
    """Distribution summary carrying its own sample count."""
    vals = sorted(float(v) for v in values)
    if not vals:
        return {"n": 0, "min": None, "median": None, "p90": None,
                "p95": None, "p99": None, "max": None}
    return {
        "n": len(vals),
        "min": round(vals[0], 1),
        "median": round(percentile(vals, 0.50), 1),
        "p90": round(percentile(vals, 0.90), 1),
        "p95": round(percentile(vals, 0.95), 1),
        "p99": round(percentile(vals, 0.99), 1),
        "max": round(vals[-1], 1),
    }


def iter_events(log_path) -> Iterator[dict]:
    """Yield parsed events from a JSONL log, skipping unparseable lines.

    A truncated final line (the runner appends while this runs) must not
    abort the analysis.
    """
    path = Path(log_path)
    if not path.exists():
        return
    with path.open() as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except (ValueError, TypeError):
                continue
            if isinstance(event, dict):
                yield event


def _parse_ts(raw) -> Optional[datetime]:
    if not raw:
        return None
    try:
        return datetime.fromisoformat(raw)
    except (ValueError, TypeError):
        return None


def _spans_stopped_loop(sorted_timestamps: list, start, end) -> bool:
    """True when the loop was evidently not running for part of this window.

    A ``task_loaded`` can be followed by a ``task_completed`` for the same task
    a day later, after the loop stopped and was restarted; unfiltered, that
    produced a 1864-minute "task" in the observed log. The tell is a stretch of
    total log silence longer than any single worker run could produce —
    ``MAX_TASK_SILENCE_SECONDS``, which sits above the CLI hard-kill ceiling.
    Ordinary silence *inside* a task is normal (a worker running 40 minutes
    emits nothing), so the bar has to be well above that, not at it.
    """
    lo = bisect.bisect_left(sorted_timestamps, start)
    hi = bisect.bisect_right(sorted_timestamps, end)
    points = [start] + sorted_timestamps[lo:hi] + [end]
    return any(
        (b - a).total_seconds() > MAX_TASK_SILENCE_SECONDS
        for a, b in zip(points, points[1:])
    )


def analyze(events: Iterable[dict], censor_at: Optional[float] = None) -> dict:
    """Compute every calibration input from a stream of runner log events.

    Args:
        events:    Iterable of decoded ``runs.jsonl`` records.
        censor_at: Known CLI hard-kill ceiling in seconds at the time the log
                   was written.  Worker runs that landed within
                   ``CENSOR_MARGIN_SECONDS`` of it are counted separately as
                   right-censored samples.

    Returns a dict of summaries plus the sample counts behind them.
    """
    task_types: dict = {}
    task_loaded_at: dict = {}
    task_completed_at: dict = {}
    worker_rows: list = []       # (task_id, elapsed_seconds, success)
    pr_check_rows: list = []     # elapsed seconds to all checks complete
    registration_rows: list = []  # seconds until the first check run appeared
    pr_check_timeouts: list = []
    first_nonempty_poll: dict = {}
    all_timestamps: list = []
    seen_worker: set = set()
    seen_pr_check: set = set()

    for event in events:
        etype = event.get("event_type")
        payload = event.get("payload") or {}
        if not isinstance(payload, dict):
            payload = {}
        ts = _parse_ts(event.get("timestamp"))
        if ts is not None:
            all_timestamps.append(ts)

        if etype == "task_loaded":
            task = payload.get("task") or {}
            tid = task.get("id")
            if tid:
                task_types[tid] = task.get("type") or "unknown"
                if ts is not None:
                    task_loaded_at.setdefault(tid, []).append(ts)

        elif etype == "task_completed":
            tid = payload.get("task_id") or event.get("task_id")
            if tid and ts is not None:
                task_completed_at.setdefault(tid, []).append(ts)

        elif etype == "worker_finished":
            elapsed = payload.get("elapsed_seconds")
            if not isinstance(elapsed, (int, float)):
                # Pre-instrumentation events carry no duration; counting them
                # as zero would drag every percentile down.
                continue
            # The dispatch path logs worker_finished twice for some runs.
            key = (payload.get("task_id"), round(float(elapsed), 3),
                   (event.get("timestamp") or "")[:19])
            if key in seen_worker:
                continue
            seen_worker.add(key)
            worker_rows.append((payload.get("task_id"), float(elapsed),
                                bool(payload.get("success"))))

        elif etype == "pr_checks_completed":
            elapsed = payload.get("elapsed")
            if not isinstance(elapsed, (int, float)):
                continue
            key = (payload.get("sha"), round(float(elapsed), 3))
            if key in seen_pr_check:
                continue
            seen_pr_check.add(key)
            pr_check_rows.append(float(elapsed))

        elif etype == "pr_checks_timeout":
            elapsed = payload.get("elapsed")
            if isinstance(elapsed, (int, float)):
                pr_check_timeouts.append(float(elapsed))

        elif etype == "pr_checks_poll_tick":
            sha = payload.get("sha")
            elapsed = payload.get("elapsed")
            total = payload.get("total") or 0
            if sha and isinstance(elapsed, (int, float)) and total > 0:
                if sha not in first_nonempty_poll:
                    first_nonempty_poll[sha] = float(elapsed)

    registration_rows = list(first_nonempty_poll.values())

    # --- worker durations, overall / by type / by outcome -----------------
    by_type: dict = {}
    for tid, elapsed, _success in worker_rows:
        by_type.setdefault(task_types.get(tid, "unknown"), []).append(elapsed)

    censored = 0
    if censor_at:
        censored = sum(1 for _t, e, _s in worker_rows
                       if e >= censor_at - CENSOR_MARGIN_SECONDS)

    successes = [e for _t, e, s in worker_rows if s]
    failures = [e for _t, e, s in worker_rows if not s]

    # --- end-to-end task durations ---------------------------------------
    all_timestamps.sort()
    end_to_end: list = []
    for tid, completions in task_completed_at.items():
        for done_at in sorted(set(completions)):
            starts = [s for s in task_loaded_at.get(tid, []) if s <= done_at]
            if not starts:
                continue
            started_at = max(starts)
            if _spans_stopped_loop(all_timestamps, started_at, done_at):
                continue
            minutes = (done_at - started_at).total_seconds() / 60.0
            # Zero-length pairs are dry-run / skipped tasks that never
            # dispatched a worker; they measure nothing about real durations.
            if minutes > 0:
                end_to_end.append((minutes, task_types.get(tid, "unknown")))

    end_to_end_by_type: dict = {}
    for minutes, ttype in end_to_end:
        end_to_end_by_type.setdefault(ttype, []).append(minutes)

    # --- loop session spans -----------------------------------------------
    sessions: list = []
    current: list = []
    for ts in all_timestamps:
        if current and (ts - current[-1]).total_seconds() > SESSION_GAP_SECONDS:
            sessions.append(current)
            current = []
        current.append(ts)
    if current:
        sessions.append(current)
    # A handful of events is a CLI invocation, not a loop session.
    session_spans = [(s[-1] - s[0]).total_seconds() / 60.0
                     for s in sessions if len(s) > 5]

    return {
        "window": {
            "first_event_at": all_timestamps[0].isoformat() if all_timestamps else None,
            "last_event_at": all_timestamps[-1].isoformat() if all_timestamps else None,
            "events_read": len(all_timestamps),
        },
        "worker_overall": summarize(e for _t, e, _s in worker_rows),
        "worker_by_type": {k: summarize(v) for k, v in sorted(
            by_type.items(), key=lambda kv: -len(kv[1]))},
        "worker_success": summarize(successes),
        "worker_failed": summarize(failures),
        "worker_censored_at": censor_at,
        "worker_censored_n": censored,
        "pr_checks_completed": summarize(pr_check_rows),
        "pr_checks_timeout_n": len(pr_check_timeouts),
        "pr_checks_timeout_elapsed": summarize(pr_check_timeouts),
        "pr_checks_registration": summarize(registration_rows),
        "task_end_to_end_minutes": summarize(m for m, _t in end_to_end),
        "task_end_to_end_by_type": {k: summarize(v) for k, v in sorted(
            end_to_end_by_type.items(), key=lambda kv: -len(kv[1]))},
        "session_span_minutes": summarize(session_spans),
    }


def analyze_log(log_path, censor_at: Optional[float] = None) -> dict:
    """Convenience wrapper: read a JSONL log from disk and analyze it."""
    return analyze(iter_events(log_path), censor_at=censor_at)


def count_above(events: Iterable[dict], threshold: float, success_only: bool = True) -> tuple:
    """Count worker runs at or above ``threshold`` — the false-positive rate.

    ``WORKER_TIMEOUT_THRESHOLD`` classifies any run at or above it as a
    timeout.  Applied to *successful* runs that number is the rate at which
    the guard mislabels healthy work, which is the single most useful figure
    for judging the current setting.  Returns ``(above, total)``.
    """
    above = total = 0
    seen: set = set()
    for event in events:
        if event.get("event_type") != "worker_finished":
            continue
        payload = event.get("payload") or {}
        elapsed = payload.get("elapsed_seconds")
        if not isinstance(elapsed, (int, float)):
            continue
        key = (payload.get("task_id"), round(float(elapsed), 3),
               (event.get("timestamp") or "")[:19])
        if key in seen:
            continue
        seen.add(key)
        if success_only and not payload.get("success"):
            continue
        total += 1
        if elapsed >= threshold:
            above += 1
    return above, total


def _fmt(value, suffix: str = "") -> str:
    return "—" if value is None else f"{value:g}{suffix}"


def _table(rows: list, header: str, unit: str) -> list:
    lines = [
        f"| {header} | n | min | median | p90 | p95 | p99 | max |",
        "| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |",
    ]
    for label, s in rows:
        lines.append(
            f"| {label} | {s['n']} | {_fmt(s['min'], unit)} | {_fmt(s['median'], unit)} "
            f"| {_fmt(s['p90'], unit)} | {_fmt(s['p95'], unit)} | {_fmt(s['p99'], unit)} "
            f"| {_fmt(s['max'], unit)} |"
        )
    return lines


def render_measurements(analysis: dict) -> str:
    """Render the measured distributions as auditable markdown tables."""
    window = analysis["window"]
    lines = [
        "## Measurements",
        "",
        f"Source: `runner/langgraph/logs/runs.jsonl` — {window['events_read']} events, "
        f"`{window['first_event_at']}` → `{window['last_event_at']}`.",
        "",
        "### Worker run duration (`worker_finished.elapsed_seconds`)",
        "",
    ]
    lines += _table([("all task types", analysis["worker_overall"])], "scope", "s")
    lines += ["", "By task type:", ""]
    lines += _table(list(analysis["worker_by_type"].items()), "task type", "s")
    lines += ["", "By outcome:", ""]
    lines += _table(
        [("success", analysis["worker_success"]), ("failed", analysis["worker_failed"])],
        "outcome", "s",
    )
    if analysis.get("worker_censored_at"):
        lines += [
            "",
            f"**Right-censored:** {analysis['worker_censored_n']} run(s) finished within "
            f"{CENSOR_MARGIN_SECONDS:g}s of the CLI ceiling in force when the log was written "
            f"(`{_fmt(analysis['worker_censored_at'], 's')}`). Those runs were *killed* at the "
            "ceiling, so the true tail is longer than the max shown above — an argument for "
            "headroom, never for a tighter bound.",
        ]
    lines += [
        "",
        "### PR check-run duration (`pr_checks_completed.elapsed`)",
        "",
    ]
    lines += _table([("all checks complete", analysis["pr_checks_completed"])], "scope", "s")
    lines += [
        "",
        f"`pr_checks_timeout` events: {analysis['pr_checks_timeout_n']} "
        f"(elapsed at timeout: {_fmt(analysis['pr_checks_timeout_elapsed']['median'], 's')} median).",
        "",
        "Time until the *first* check run appears (`pr_checks_poll_tick` with `total > 0`) — "
        "the quantity `PR_CHECKS_EMPTY_GRACE_S` must cover:",
        "",
    ]
    lines += _table([("check registration", analysis["pr_checks_registration"])], "scope", "s")
    lines += [
        "",
        "### End-to-end task duration (`task_loaded` → `task_completed`)",
        "",
        "This is the quantity the stale-run watchdog actually measures: a whole task, "
        "including checks, PR polling, and deploy — not just the worker.",
        "",
    ]
    lines += _table([("all task types", analysis["task_end_to_end_minutes"])], "scope", " min")
    lines += ["", "By task type:", ""]
    lines += _table(list(analysis["task_end_to_end_by_type"].items()), "task type", " min")
    lines += [
        "",
        "### Loop session span",
        "",
        f"Contiguous log activity, split on gaps > {SESSION_GAP_SECONDS // 60} minutes. "
        "This is what `MAX_RUNTIME_MINUTES` bounds.",
        "",
    ]
    lines += _table([("session", analysis["session_span_minutes"])], "scope", " min")
    return "\n".join(lines)


def _default_log_path() -> Path:
    return Path(__file__).resolve().parent.parent / "logs" / "runs.jsonl"


if __name__ == "__main__":  # pragma: no cover - operator entry point
    import sys

    log = sys.argv[1] if len(sys.argv) > 1 else _default_log_path()
    print(render_measurements(analyze_log(log, censor_at=1800)))
