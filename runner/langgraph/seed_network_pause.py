"""Seed the DERIVED network-pause task at the front of the queue.

Run once:  python seed_network_pause.py

WHY THIS REPLACES m4c4-05. The original m4c4-05 spec (see seed_m4c4.py) was
written before m4c-06 existed and had to build its own waiting mechanism:
probe, pause, poll interval, max patience, counter suppression, watchdog
suppression. m4c-06 has since merged (PR 111, f10358d) and already owns the
sleep-and-restart loop — `tools/loop_watchdog.py` restarts the loop after any
non-hard-gate exit with a 30s default delay, which IS the poll interval the
original spec asked for.

So the remaining work is only the part m4c-06 does not do: knowing that the
machine is offline, and making that a pause rather than a task failure.

Founder decision 2026-08-09: no VPS. The only problem the VPS meaningfully
solved for this setup was losing wifi while driving, and that is exactly what
this task fixes. Overnight-run setup is already in place.

The original m4c4-05 stays in the queue, at the back, marked superseded — see
docs/DEFERRED-BACKLOG.md §1.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json

SUPERSEDED_ID = "m4c4-05-network-pause"

TASKS = [
    {
        "id": "m4c4-05b-network-pause-watchdog",
        "title": "M4c.4: no network is a PAUSE — built on m4c-06's watchdog, not beside it",
        "type": "backend",
        "branch": "feature/m4c4/network-pause-watchdog",
        "description": (
            "SCENARIO (founder, unchanged): the laptop moves between locations — a 5-20 minute "
            "drive with no wifi. Every worker call needs the network (Anthropic, GitHub, Supabase, "
            "Vercel, Slack). Today the loop converts a driveway into a sequence of recorded "
            "failures: transient-retry counters burn, tasks can park as blocked, and those fake "
            "failures pollute the logs that feed threshold calibration and loop telemetry.\n\n"
            "WHAT ALREADY EXISTS — DO NOT REBUILD IT. m4c-06 merged as PR 111 (f10358d). "
            "`tools/loop_watchdog.py::evaluate_restart_decision` already provides the entire "
            "sleep-and-restart mechanism: HARD_GATE_REASONS that must not auto-restart, precise "
            "limits-aware waits for `claude_subscription_cooldown` (reads "
            "`claude_subscription_cooldown_until` from state and adds a 2-minute buffer), a "
            "5-minute delay for queue-empty stops, and a default 30s restart for everything else. "
            "That 30s default IS the poll interval the original m4c4-05 spec asked for. This task "
            "adds the missing INPUT to that machine — it does not build a second waiting "
            "mechanism, a second poll loop, or a second patience budget.\n\n"
            "WHAT IS ACTUALLY MISSING — three pieces:\n\n"
            "(a) A CONNECTIVITY PROBE. There is no network probe anywhere in tools/ today. Add a "
            "cheap one: DNS resolution plus one lightweight HEAD request, short timeout, no "
            "credentials, no tokens spent. It must be the single authority for 'the machine is "
            "offline'. Run it BEFORE claiming a task; if it fails, do not claim, and stop the loop "
            "with a new `network_unavailable` stop reason.\n\n"
            "(b) NETWORK-ERROR CLASSIFICATION MID-CALL. Classify network-shaped failures — DNS "
            "failure, connection refused/reset, no route to host, TLS handshake failure, request "
            "timeout with zero bytes received — as the same environmental pause. The in-flight "
            "task is left QUEUED and simply re-attempted after the restart. While paused nothing "
            "may be touched: no retry_count, no task_attempt_counts, no consecutive_failures, no "
            "error_history, no task status change, no Supabase sync. Confirm the probe before "
            "concluding offline — a single failing endpoint is NOT loss of connectivity.\n\n"
            "(c) WATCHDOG WIRING + ITS OWN DELAY + PATIENCE. `network_unavailable` must NOT be "
            "added to HARD_GATE_REASONS (a human is not required — the driver just needs to "
            "arrive). But it must NOT use the shared 30s default delay either, for a concrete "
            "reason: a watchdog restart re-enters loop start, which since m4c4-06 runs the "
            "repo-health preflight — a full ./scripts/check.sh (npm ci, lint, tsc, tests, build), "
            "~90 seconds of CPU. Restarting every 30s while offline would re-run that whole suite "
            "repeatedly for no benefit. Two required changes:\n"
            "  - Give this stop reason its OWN delay: NETWORK_RETRY_DELAY_S (default 300). Do not "
            "    change WATCHDOG_RESTART_DELAY_S — 30s remains correct for crashes and batch ends.\n"
            "  - CHEAP-PATH SHORT-CIRCUIT: on loop start, run the connectivity probe BEFORE the "
            "    repo-health preflight and before any other expensive startup work. If the probe "
            "    fails, exit immediately with `network_unavailable` — no check.sh, no npm, no git "
            "    fetch. An offline restart must cost approximately nothing.\n"
            "Then add a PATIENCE CEILING: track cumulative offline time across consecutive "
            "`network_unavailable` restarts and, past a configurable ceiling (default 90 minutes), "
            "stop restarting and report plainly that the machine has had no internet for N "
            "minutes. Without this the watchdog retries a dead network forever.\n\n"
            "DISTINGUISH CAREFULLY — these keep their existing handling and must never be "
            "classified as offline: a 5xx from one provider; a 401/403 auth failure (an OAuth "
            "token was revoked on 2026-08-08 and was recorded as 'worker returned no output' with "
            "a retry scheduled — wrong, but a SEPARATE bug, do not fix it here); a 429 rate limit "
            "(that is the subscription cooldown path and it already works).\n\n"
            "OBSERVABILITY: log `network_unavailable_detected` on entry with the probe result, and "
            "`network_restored` on exit with the total outage duration, so a drive shows up in the "
            "logs as one pause with a duration rather than as a cluster of failures.\n\n"
            "CONFIG (three-place rule): NETWORK_PAUSE_ENABLED (default true), "
            "NETWORK_PROBE_TIMEOUT_S (default 5), NETWORK_RETRY_DELAY_S (default 300 — founder "
            "decision 2026-08-09; a 5-minute cadence is deliberate, the probe is free but the "
            "restart path is not), NETWORK_MAX_PATIENCE_MINUTES (default 90). Disabled restores "
            "today's behaviour exactly.\n\n"
            "SCOPE BOUNDARY: do not modify the cooldown path, the transient-retry path for "
            "non-network errors, or `evaluate_restart_decision`'s existing branches. Do not add a "
            "poll loop inside the runner — the watchdog's restart cadence is the poll loop.\n\n"
            "TESTS: probe failure prevents task claim and produces the `network_unavailable` stop "
            "reason; a network error mid-call leaves the task queued and every counter untouched; "
            "a provider 5xx, a 401 and a 429 all still take their existing paths; "
            "`network_unavailable` is not a hard gate and restarts at NETWORK_RETRY_DELAY_S rather "
            "than the shared watchdog delay; a failed probe at loop start exits BEFORE the "
            "repo-health preflight runs (assert check.sh was never invoked); cumulative "
            "offline time past the patience ceiling stops restarting with a clear report; "
            "`network_restored` records the outage duration; disabling the flag restores prior "
            "behaviour. Mock the probe and all git/HTTP calls — no real network calls in tests."
        ),
    },
]


def main() -> int:
    path = Path(__file__).parent / ".runtime" / "tasks.local.json"
    tasks = json.loads(path.read_text())
    by_id = {t.get("id"): t for t in tasks}

    added = []
    for spec in TASKS:
        if spec["id"] in by_id:
            print(f"skip (already present): {spec['id']}")
            continue
        added.append({
            **spec,
            "status": "queued",
            "source": "founder_seed",
            "mission": "M4c.4 — Force Multipliers",
            "runner_target": "self",
        })

    old = by_id.get(SUPERSEDED_ID)
    if old is None:
        print(f"WARNING: {SUPERSEDED_ID} not found")
    else:
        old["superseded_by"] = TASKS[0]["id"]
        old["deferred_note"] = (
            "SUPERSEDED by m4c4-05b-network-pause-watchdog (2026-08-09). m4c-06 "
            "shipped the sleep-and-restart machinery this task would have "
            "duplicated; the derived task adds only the probe, the classification "
            "and the patience ceiling. Do not build both. See "
            "docs/DEFERRED-BACKLOG.md §1."
        )
        print(f"marked superseded: {SUPERSEDED_ID} -> {TASKS[0]['id']}")

    # Front of queue: this is the one blocking the founder's actual daily use.
    pool = {t["id"]: t for t in (added + tasks)}
    front = [pool.pop(TASKS[0]["id"])] if TASKS[0]["id"] in pool else []
    rest = [t for t in (added + tasks) if t["id"] in pool]

    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(front + rest, indent=2))
    tmp.replace(path)

    for t in front:
        print(f"front of queue: {t['id']}  [{t['status']}]")
    print(f"\n{len(added)} new task(s) added. Verify: python main.py next-task")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
