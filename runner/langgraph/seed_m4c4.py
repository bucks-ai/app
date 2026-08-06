"""Seed M4c.4 — Force Multipliers (4 tasks) at the FRONT of the local queue.

Run once:  python seed_m4c4.py

Full rationale: docs/BABYSITTER-DESIGN-REVIEW.md §6.

WHY THESE FOUR, FIRST: each one raises the first-attempt success rate of the ~29
tasks that follow (M4c remainder, M4c.5, M4d). Run last, their compounding is
wasted entirely. All four are small and independent of each other.

Task 03 (mission briefing) is already queued as `m4c0-06-mission-context-briefing`;
this script only reorders it into position rather than duplicating it.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json

BRIEFING_ID = "m4c0-06-mission-context-briefing"

TASKS = [
    {
        "id": "m4c4-01-crash-safe-checkpointing",
        "title": "M4c.4: never lose work — checkpoint WIP on every exit path",
        "type": "backend",
        "branch": "feature/m4c4/crash-safe-checkpointing",
        "description": (
            "THE INCIDENT: m4c-03 was implemented, then halted by a guard before the commit "
            "step — three separate times. 1,552 lines of finished work (tools/state_self_healing.py, "
            "its tests, and edits across 11 files) sat uncommitted in the working tree for days "
            "and were only recovered because the founder happened to run `git status` and "
            "recognise them. Nothing in the runner noticed. Any of the intervening `git checkout` "
            "operations could have destroyed the lot, and a worker's routine branch operation did "
            "exactly that to founder doc edits during M4b.\n\n"
            "THE RULE: work that exists only in the working tree is work that can vanish. Every "
            "exit path must checkpoint first.\n\n"
            "REQUIRED: (a) install SIGINT/SIGTERM handlers and an atexit hook in main.py's "
            "run-loop path that, before exiting for ANY reason — Ctrl+C, guard stop, unhandled "
            "exception, watchdog kill — commit any dirty working tree to the CURRENT task's "
            "branch with a clearly-marked WIP message (task id, stop reason, timestamp) and push "
            "it if a remote exists; (b) the same checkpoint runs whenever a guard sets a "
            "stop_reason, before the loop unwinds; (c) log a `wip_checkpointed` event with the "
            "commit sha and the file list, and include the sha in the stop report so a recovery "
            "is one `git checkout` away; (d) on startup, detect any WIP checkpoint commit on the "
            "current task's branch and tell the worker in its prompt that partial work already "
            "exists there and should be continued, not restarted.\n\n"
            "SAFETY: never checkpoint onto main or any protected branch — if the current branch "
            "is protected, create `wip/<task-id>` instead. Never `git add` paths outside the "
            "repo. Never force-push. If the checkpoint itself fails, log loudly and continue "
            "exiting — a failed checkpoint must not prevent a clean shutdown.\n\n"
            "TESTS: checkpoint on SIGTERM; checkpoint on guard stop; protected-branch redirect to "
            "wip/ branch; no-op when the tree is clean; startup detection of an existing WIP "
            "commit; checkpoint failure does not block exit. Mock all git calls — no real repo "
            "operations in tests."
        ),
    },
    {
        "id": "m4c4-02-failure-context-repair-loop",
        "title": "M4c.4: repair deterministic failures with the error attached — stop blind-retrying",
        "type": "backend",
        "branch": "feature/m4c4/failure-context-repair",
        "description": (
            "THE EVIDENCE: across every mission logged in runs.jsonl, blind retries have recovered "
            "TRANSIENT failures (timeouts, cooldowns) and have NEVER ONCE recovered a "
            "deterministic one. m4c-01 (false gate failure), m4c-02 (a real test failure: "
            "`assert 0 == 1` in test_agent_run_sync.py), m4c0-02 and m4c0-04 (merge conflicts) — "
            "each retried to exhaustion with an identical outcome, and each was ultimately fixed "
            "by the founder by hand. This is structural, not tuning: a retry re-runs identical "
            "input and expects a different output. Raising MAX_TASK_RETRIES only wastes more "
            "usage limit.\n\n"
            "THE FIX — the primitive already exists and is wired to the wrong trigger. "
            "`auto_repair_loop` / `build_auto_repair_prompt` currently fire ONLY on a local "
            "check.sh failure. Extend the same mechanism to every deterministic failure class, "
            "with the actual failure evidence attached to the repair prompt:\n"
            "  - CI check failure -> the failing check name, the failing test id, and the relevant "
            "    excerpt of the CI log (fetch via the GitHub checks/annotations API; cap the "
            "    excerpt so a huge log cannot blow the prompt).\n"
            "  - Merge conflict -> the conflicted file list and the conflict hunks themselves.\n"
            "  - Completion-evidence block -> the specific reasons the gate gave.\n"
            "  - Gate block (any authority) -> which gate, which authority, what it wanted.\n"
            "A repair attempt is a FRESH worker whose prompt states: what was attempted, what "
            "specifically failed, the evidence, and that its job is to fix that failure — not to "
            "redo the task from scratch.\n\n"
            "BOUNDARIES: a repair attempt must not count against MAX_TASK_RETRIES (different "
            "budget, MAX_REPAIR_ATTEMPTS, three-place rule); cap repair depth (a repair of a "
            "repair of a repair escalates to a human, it does not become a fourth attempt); if a "
            "repair produces the identical failure signature twice, stop and mark blocked with "
            "the signature recorded — repeating a failed repair is the same bug this task exists "
            "to kill. Transient failures keep today's retry-with-backoff path unchanged; this is "
            "strictly for deterministic ones.\n\n"
            "TESTS: each failure class routes to repair with its evidence present in the prompt; "
            "repair attempts consume the repair budget not the retry budget; depth cap escalates; "
            "identical repeated failure signature stops rather than loops; transient failures "
            "still take the old path. Mock the GitHub API and the worker."
        ),
    },
    {
        "id": "m4c4-05-network-pause",
        "title": "M4c.4: no network is a PAUSE, not a failure",
        "type": "backend",
        "branch": "feature/m4c4/network-pause",
        "description": (
            "SCENARIO (founder, 2026-08-04): the laptop moves between locations — a 5-20 minute "
            "drive with no wifi in between. Every worker call needs the network (Anthropic, "
            "GitHub, Supabase, Vercel, Slack), so the loop currently converts a driveway into a "
            "sequence of recorded failures: attempt counters burn, tasks flip to failed/blocked, "
            "those statuses sync to Supabase, and the consecutive-failure and repeated-error "
            "guards accumulate toward a stop. Worse, those fake failures pollute the very logs "
            "that feed threshold calibration, loop telemetry, and m4c-10's 'how many times was "
            "the founder touched' measure.\n\n"
            "PRINCIPLE: total loss of connectivity is an environmental PAUSE — exactly like a "
            "subscription cooldown — not a statement about the task. Reuse that machinery; do not "
            "invent a second waiting mechanism.\n\n"
            "REQUIRED, BOTH HALVES: (a) BEFORE dispatch, a cheap connectivity probe (DNS "
            "resolution plus one lightweight HEAD request, short timeout). If it fails, enter a "
            "`network_unavailable` wait instead of claiming a task. (b) DURING a call, classify "
            "network-shaped errors (DNS failure, connection refused/reset, no route to host, TLS "
            "handshake failure, request timeout with zero bytes received) as the same pause — the "
            "in-flight task is left queued and simply re-attempted after the wait, NOT counted as "
            "a transient failure and NOT parked.\n\n"
            "WHILE PAUSED, nothing may be touched: no retry_count, no task_attempt_counts, no "
            "consecutive_failures, no error_history, no task status change, no Supabase sync, and "
            "the stale-run watchdog is suppressed (mirror how the cooldown wait already refreshes "
            "last_task_completed_at at both ends of the sleep). Log `network_unavailable_detected` "
            "on entry and `network_restored` on exit with the outage duration.\n\n"
            "TIMING — two separate knobs, do not conflate them: POLL INTERVAL should be short "
            "(default 30s; a DNS probe costs no tokens and no money) so the loop resumes within a "
            "minute of arrival rather than idling; MAX PATIENCE should be long (default 90 "
            "minutes) so a genuinely long outage is ridden out rather than escalated. Both config, "
            "three-place rule. Beyond max patience, stop the loop with a `network_unavailable` "
            "stop reason whose stop report says plainly that the machine had no internet for N "
            "minutes — and let the supervisor's restart path pick it up when connectivity "
            "returns.\n\n"
            "DISTINGUISH CAREFULLY: a 5xx from one provider, an auth failure, or a rate limit are "
            "NOT loss of connectivity and must keep their existing handling. The probe is the "
            "authority for 'the machine is offline'; a single failing endpoint is not.\n\n"
            "TESTS: probe failure pauses instead of dispatching; every counter is untouched across "
            "a pause; a network error mid-call pauses and re-attempts the same task; a provider "
            "5xx and a 401 still take their existing paths; max patience stops with the right "
            "reason and report; poll interval and patience are independently configurable; the "
            "stale watchdog does not fire during a pause. Mock the probe — no real network calls "
            "in tests."
        ),
    },
    {
        "id": "m4c4-04-plan-then-execute",
        "title": "M4c.4: plan the whole mission before writing any code",
        "type": "backend",
        "branch": "feature/m4c4/plan-then-execute",
        "description": (
            "THE INCIDENT: five M4c.0 tasks all edited config.py and graph.py, each on its own "
            "branch cut from the same base. The first merged; every other branch then conflicted, "
            "two tasks died on `pr_merge_failed: Pull Request has merge conflicts`, the loop "
            "halted, and the founder hand-rebased each one. Separately, m4a-01 was implemented "
            "twice by two workers, and m4c-03's work was written three times. Nothing detected "
            "any of it in advance — because nothing knows what a task will touch until it has "
            "already touched it.\n\n"
            "REQUIRED — a cheap planning pass before a mission executes. For each task, dispatch a "
            "PLANNING worker (cheap model — this is deliberately not the execution model) that "
            "reads the relevant code and returns a structured plan: (a) the files it expects to "
            "create or modify; (b) a two-or-three sentence approach; (c) whether the deliverable "
            "ALREADY EXISTS in the codebase, with the path if so; (d) any task it depends on "
            "landing first. Persist plans alongside the tasks.\n\n"
            "THEN USE THEM: (1) CONFLICT DETECTION — tasks whose expected file sets intersect are "
            "marked as needing sequential execution, and the queue orders them so each starts "
            "from the merged predecessor rather than a stale base; log a `plan_conflict_detected` "
            "event naming the tasks and the shared files. (2) DUPLICATE DETECTION — a task whose "
            "deliverable already exists is flagged for founder review or auto-completed with the "
            "evidence, never silently rebuilt. (3) RIGHT-SIZING — a plan listing more than N files "
            "is flagged as too large and recommended for splitting. (4) The expected-file list "
            "becomes the declared scope that a later task (M4c.5) enforces against the actual "
            "diff.\n\n"
            "CONSTRAINTS: planning must be cheap and bounded — one short call per task, hard cap "
            "on output size, and the whole pass must degrade gracefully (if planning fails or is "
            "disabled, execution proceeds exactly as it does today). Config flag, three-place "
            "rule, default ON for seeded missions. Plans are advisory for content and "
            "authoritative only for ordering and scope — a worker is never required to follow the "
            "planned approach, because the plan was made with less information than the executor "
            "will have.\n\n"
            "TESTS: intersecting file sets produce a sequential ordering; disjoint sets are left "
            "parallel-eligible; an already-existing deliverable is flagged; an oversized plan is "
            "flagged; planning failure falls back to today's behaviour; the pass is skipped "
            "entirely when disabled. Pure functions for the ordering logic — no worker calls in "
            "tests."
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

    if BRIEFING_ID not in by_id:
        print(f"WARNING: {BRIEFING_ID} not found — run seed_mission_context.py first")

    # Desired front-of-queue order: checkpoint -> repair loop -> briefing -> plan pass.
    order = [
        "m4c4-01-crash-safe-checkpointing",
        "m4c4-02-failure-context-repair-loop",
        "m4c4-05-network-pause",
        BRIEFING_ID,
        "m4c4-04-plan-then-execute",
    ]
    pool = {t["id"]: t for t in (added + tasks)}
    front = [pool.pop(tid) for tid in order if tid in pool]
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
