"""Ordering invariants between runner timeouts and thresholds.

Timeouts in this runner are not independent knobs — they are nested windows.
A worker is killed by the CLI ceiling, the guard *classifies* that kill, the
watchdog bounds the whole task, and the runtime budget bounds the session.
When that nesting is violated, nothing errors: the runner simply does the
wrong thing hours later, and the symptom (a dead loop) points nowhere near
the cause (a number in `.env`).

Two such violations were live in the defaults before M4c.0:

- ``CLAUDE_CLI_TIMEOUT_S=1800`` with ``WORKER_TIMEOUT_THRESHOLD=570``: the
  guard sat *below* the observed p90 of healthy runs, so 12.2% of successful
  worker runs were classified as timeouts. The CLI never killed them; the
  guard invented the failure.
- ``MAX_STALE_TASK_MINUTES=60`` while single tasks legitimately ran 30+
  minutes (observed max 41.1 min): the watchdog killed sessions that were
  working correctly.

So the ordering is checked at startup and the process refuses to start,
naming the exact fix. Design: pure function over a config snapshot dict
(``RunnerConfig.report()``), no imports from ``config`` — so it stays
unit-testable and free of import cycles.
"""
from __future__ import annotations

from typing import Optional


def _num(snapshot: dict, key: str) -> Optional[float]:
    value = snapshot.get(key)
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return float(value)


def check_threshold_invariants(snapshot: dict) -> list:
    """Return the list of violated ordering invariants, empty when healthy.

    Args:
        snapshot: A ``RunnerConfig.report()`` dict. Keys that are absent or
                  non-numeric are skipped rather than raising — a partial
                  snapshot in a test should not manufacture a violation.

    Each violation is a dict with:
        - ``invariant`` — the rule in symbolic form, e.g. ``"A < B"``.
        - ``message``   — what actually goes wrong when it is violated.
        - ``fix``       — a concrete, copy-pasteable env change.
        - ``values``    — the offending values, for the log record.
    """
    violations: list = []

    cli = _num(snapshot, "claude_cli_timeout_s")
    guard = _num(snapshot, "worker_timeout_threshold")
    stale_min = _num(snapshot, "max_stale_task_minutes")
    warn_min = _num(snapshot, "stale_run_warn_minutes")
    runtime_min = _num(snapshot, "max_runtime_minutes")
    grace = _num(snapshot, "pr_checks_empty_grace_s")
    checks_timeout = _num(snapshot, "pr_checks_timeout_s")
    backoff_max = _num(snapshot, "failure_retry_backoff_max_s")
    attempts = _num(snapshot, "max_task_attempts")

    def add(invariant, message, fix, values):
        violations.append({
            "invariant": invariant,
            "message": message,
            "fix": fix,
            "values": values,
        })

    # 1. The CLI ceiling must sit below the guard that classifies its kills.
    #    Inverted, the guard fires on runs the CLI would have let finish.
    if cli is not None and guard is not None and guard > 0 and cli >= guard:
        add(
            "CLAUDE_CLI_TIMEOUT_S < WORKER_TIMEOUT_THRESHOLD",
            f"WORKER_TIMEOUT_THRESHOLD ({guard:g}s) is at or below the CLI hard "
            f"kill ({cli:g}s), so healthy runs longer than {guard:g}s are "
            "classified as timeouts even though the CLI never killed them. "
            "Each false timeout burns a retry and feeds the failure guard.",
            f"set WORKER_TIMEOUT_THRESHOLD to more than CLAUDE_CLI_TIMEOUT_S "
            f"(e.g. WORKER_TIMEOUT_THRESHOLD={int(cli) + 300})",
            {"claude_cli_timeout_s": cli, "worker_timeout_threshold": guard},
        )

    # 2. A whole task must be allowed to outlive its own worker.
    if guard is not None and stale_min is not None and stale_min > 0 and guard >= stale_min * 60:
        add(
            "WORKER_TIMEOUT_THRESHOLD < MAX_STALE_TASK_MINUTES * 60",
            f"The stale-run watchdog trips at {stale_min:g} min ({stale_min * 60:g}s), "
            f"at or before the worker timeout threshold ({guard:g}s). The watchdog "
            "kills the session while the worker is still legitimately running, so "
            "the worker timeout guard can never actually fire.",
            f"set MAX_STALE_TASK_MINUTES to more than {int(guard // 60) + 1} "
            f"(e.g. MAX_STALE_TASK_MINUTES={int(guard // 60) * 2})",
            {"worker_timeout_threshold": guard, "max_stale_task_minutes": stale_min},
        )

    # 3. The empty-grace recovery path needs two full grace windows: one to
    #    detect zero check runs, one to confirm after refreshing the branch.
    if (
        grace is not None and checks_timeout is not None
        and grace > 0 and grace * 2 >= checks_timeout
    ):
        add(
            "PR_CHECKS_EMPTY_GRACE_S * 2 < PR_CHECKS_TIMEOUT_S",
            f"The zero-check recovery needs two grace windows ({grace * 2:g}s total) "
            f"but the poll budget is only {checks_timeout:g}s, so the poll times out "
            "before the recovery can confirm. A PR with no checks reports "
            "pr_checks_timeout instead of the true cause, pr_checks_no_runs.",
            f"set PR_CHECKS_TIMEOUT_S above {int(grace * 2)} "
            f"(e.g. PR_CHECKS_TIMEOUT_S={int(grace * 4)})",
            {"pr_checks_empty_grace_s": grace, "pr_checks_timeout_s": checks_timeout},
        )

    # 4. A warning that fires at or after the hard stop is never seen.
    if (
        warn_min is not None and stale_min is not None
        and warn_min > 0 and stale_min > 0 and warn_min >= stale_min
    ):
        add(
            "STALE_RUN_WARN_MINUTES < MAX_STALE_TASK_MINUTES",
            f"The stale-run warning ({warn_min:g} min) fires at or after the hard "
            f"stop ({stale_min:g} min), so the loop halts with no advance warning "
            "and an operator gets no chance to intervene.",
            f"set STALE_RUN_WARN_MINUTES below MAX_STALE_TASK_MINUTES "
            f"(e.g. STALE_RUN_WARN_MINUTES={int(stale_min * 0.6)})",
            {"stale_run_warn_minutes": warn_min, "max_stale_task_minutes": stale_min},
        )

    # 5. A session must be able to reach its own watchdog.
    if (
        stale_min is not None and runtime_min is not None
        and stale_min > 0 and runtime_min > 0 and stale_min >= runtime_min
    ):
        add(
            "MAX_STALE_TASK_MINUTES < MAX_RUNTIME_MINUTES",
            f"The runtime budget ({runtime_min:g} min) expires at or before the stale "
            f"watchdog ({stale_min:g} min), so a genuinely stuck loop always stops with "
            "reason max_runtime and the real cause is never reported.",
            f"raise MAX_RUNTIME_MINUTES above MAX_STALE_TASK_MINUTES "
            f"(e.g. MAX_RUNTIME_MINUTES={int(stale_min * 4)})",
            {"max_stale_task_minutes": stale_min, "max_runtime_minutes": runtime_min},
        )

    # 6. Worst-case retry backoff must fit inside the stale window alongside
    #    the worker ceiling, or the backoff itself trips the watchdog.
    if (
        guard is not None and backoff_max is not None and attempts is not None
        and stale_min is not None and stale_min > 0 and attempts > 1
    ):
        worst = guard + backoff_max * (attempts - 1)
        if worst >= stale_min * 60:
            add(
                "WORKER_TIMEOUT_THRESHOLD + FAILURE_RETRY_BACKOFF_MAX_S * "
                "(MAX_TASK_ATTEMPTS - 1) < MAX_STALE_TASK_MINUTES * 60",
                f"A task that exhausts its {attempts:g} attempts can occupy "
                f"{worst:g}s, at or beyond the {stale_min * 60:g}s stale window — so "
                "retrying a slow task trips the watchdog and kills the session "
                "mid-recovery.",
                f"lower FAILURE_RETRY_BACKOFF_MAX_S or raise MAX_STALE_TASK_MINUTES "
                f"above {int(worst // 60) + 1}",
                {
                    "worker_timeout_threshold": guard,
                    "failure_retry_backoff_max_s": backoff_max,
                    "max_task_attempts": attempts,
                    "max_stale_task_minutes": stale_min,
                },
            )

    return violations


def format_violations(violations: list) -> str:
    """Human-readable startup error naming every violation and its fix."""
    if not violations:
        return ""
    lines = [
        f"✗ Runner config violates {len(violations)} threshold ordering "
        f"invariant{'s' if len(violations) != 1 else ''}:",
        "",
    ]
    for i, v in enumerate(violations, 1):
        lines.append(f"  {i}. {v['invariant']}")
        lines.append(f"     Problem: {v['message']}")
        lines.append(f"     Fix:     {v['fix']}")
        lines.append("")
    lines.append("  See docs/M4C0-THRESHOLD-CALIBRATION.md for the observed data")
    lines.append("  these thresholds are derived from.")
    return "\n".join(lines)
