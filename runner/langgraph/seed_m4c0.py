"""Seed M4c.0 — Error-Rate Reduction (5 tasks) at the FRONT of the local queue.

Run once:  python seed_m4c0.py

WHY THIS MISSION EXISTS (founder call, 2026-08-02): across M1→M4b the runner
has generated a high, steady error rate, and almost none of it is "the AI wrote
bad code". Sorted by root cause, the recurring failures are:

  1. THE RUNNER IS STRICTER THAN REALITY. Gates written to be conservative in
     isolation over-block on contact with a real repo. Canonical case: PR #94 —
     every required check green, one advisory job red, runner invents a failure
     the repo's own branch protection does not recognise, m4c-01 dies with
     retries exhausted, loop dies on stale_run. Same shape as the resource gate
     halting on credentials that were already in .env.
  2. CONFIG DRIFT / SECOND-ORDER TIMEOUTS. Limits set for a smaller, faster
     world and never revisited: CLI timeout 600s vs 30-min tasks,
     MAX_STALE_TASK_MINUTES=60 vs tasks that legitimately exceed it. These
     cascade: timeout -> failed task -> stale run -> dead loop.
  3. STATE WITH NO OWNER. tasks.local.json is mutated by a long-running process
     with no invariants, no reconciliation against Supabase, no restart repair.
     The founder has hand-edited it 5+ times.
  4. ENVIRONMENT ASSUMPTIONS THAT ONLY HOLD LOCALLY. _runner_migrations absent
     in prod, merged migrations never applied, Vercel not git-connected,
     middleware in the wrong directory for a src/ project.

M4c addresses (3) and (4) via m4c-03/m4c-05. It does NOT address (1) or (2) —
and the babysitter would happily automate *around* a false failure forever
without reducing the error rate. M4c's acceptance test is an unattended
overnight run; running it on today's noise floor means measuring the babysitter
against errors that should not exist. Hence: M4c.0 first, then M4c.

These tasks are runner-internal (runner_target=self) and intentionally not a
Supabase mission — the M4c mission tasks are already queued locally and would
otherwise run first.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json

TASKS = [
    {
        "id": "m4c0-01-gate-authority-audit",
        "title": "M4c.0: every gate defers to the external authority — stop over-blocking",
        "type": "backend",
        "branch": "feature/m4c0/gate-authority-audit",
        "description": (
            "Audit EVERY blocking gate in the runner and make each one defer to the external "
            "authority where one exists, instead of enforcing its own stricter private policy. "
            "Motivating case (2026-08-02): poll_pr_checks failed PR #94 because an advisory job "
            "named '... [informational]' reported failure, while all five required checks were "
            "green — the runner was stricter than GitHub branch protection, which is the actual "
            "authority on what blocks a merge. That single false failure exhausted m4c-01's "
            "retries and killed the loop. A fix for that specific case already shipped "
            "(PR_CHECKS_NON_BLOCKING); this task generalises it. "
            "For each gate — merge approval, PR checks, SQL approval, resource/credential, "
            "acceptance criteria, definition of done, independent code review, high-risk review, "
            "strategic, cost budget, worker timeout, stale run — determine and document: (a) what "
            "external authority, if any, already governs this (branch protection, config presence, "
            "the SQL guard, CI itself); (b) whether the gate can consult that authority instead of "
            "guessing; (c) whether blocking the ENTIRE LOOP is proportionate, or whether the right "
            "behaviour is skip-this-task-and-continue. Default to skip-and-continue: one blocked "
            "task must not stop 9 healthy ones (this is also m4c-07's core value). "
            "Concrete required fixes: (1) the resource gate must filter out credential names "
            "already present in the runner config/env before writing a request — during M2 and "
            "M4b it repeatedly halted for VERCEL_TOKEN and VERCEL_PROJECT_ID that were in .env "
            "the whole time; (2) any gate that blocks must record WHICH authority it consulted in "
            "its event payload. "
            "Deliverable: docs/M4C0-GATE-AUDIT.md with a row per gate (authority, current "
            "behaviour, new behaviour, proportionality), plus the code changes and unit tests for "
            "each behaviour change. Do not weaken genuinely destructive-action gates: non-additive "
            "SQL, spend past cap, and irreversible operations still block."
        ),
    },
    {
        "id": "m4c0-02-threshold-calibration",
        "title": "M4c.0: calibrate every timeout/threshold from observed data, with ordering invariants",
        "type": "backend",
        "branch": "feature/m4c0/threshold-calibration",
        "description": (
            "Every timeout and threshold in the runner was guessed, and several are provably wrong "
            "against real task durations — producing cascading failures where a timeout becomes a "
            "failed task becomes a stale run becomes a dead loop. "
            "Step 1 — MEASURE: write a small analysis over runner/langgraph/logs/runs.jsonl that "
            "computes, per task type, the observed distribution of worker elapsed_seconds "
            "(median/p95/max) from worker_finished events, plus PR check completion durations from "
            "pr_checks_completed. Save as docs/M4C0-THRESHOLD-CALIBRATION.md including the sample "
            "counts, so the numbers are auditable rather than asserted. "
            "Step 2 — SET: derive defaults from p95 with headroom, and update config defaults "
            "accordingly (three-place rule: config.py, .env.example, README table). Cover at "
            "minimum CLAUDE_CLI_TIMEOUT_S, WORKER_TIMEOUT_THRESHOLD, MAX_STALE_TASK_MINUTES, "
            "PR_CHECKS_TIMEOUT_S, PR_CHECKS_EMPTY_GRACE_S, MAX_RUNTIME_MINUTES, and the retry "
            "backoff bounds. "
            "Step 3 — INVARIANTS: add a startup validation plus unit tests asserting the ordering "
            "that makes cascades impossible: CLAUDE_CLI_TIMEOUT_S < WORKER_TIMEOUT_THRESHOLD < "
            "MAX_STALE_TASK_MINUTES*60, and PR_CHECKS_EMPTY_GRACE_S*2 < PR_CHECKS_TIMEOUT_S. A "
            "config that violates an invariant must fail loudly at startup with the exact fix, "
            "not silently mis-behave hours later. Known real instance: MAX_STALE_TASK_MINUTES=60 "
            "while single tasks legitimately ran 30+ minutes, so the watchdog killed sessions that "
            "were working correctly."
        ),
    },
    {
        "id": "m4c0-03-task-state-integrity",
        "title": "M4c.0: tasks.local.json gets invariants, validation, and auto-repair",
        "type": "backend",
        "branch": "feature/m4c0/task-state-integrity",
        "description": (
            "The local task queue is a JSON file mutated by a long-running process with no schema, "
            "no invariants, and no repair — the founder has hand-edited it at least five times to "
            "recover from states the runner created and could not exit (stranded 'running' tasks, "
            "colliding ids from triple-seeding, transient errors written as terminal 'failed'). "
            "Required: (a) a schema definition for a task record (required fields, allowed status "
            "values, allowed transitions) enforced on every load and save; (b) AUTO-REPAIR on load "
            "for impossible states, each logged distinctly: a task 'running' with no live session "
            "owner -> queued; duplicate ids -> deduplicate keyed on seeded_task_id, keeping the "
            "row with real progress; a task both terminal and holding a future retry_not_before -> "
            "clear the stale field; unknown status -> queued with a loud event. (c) a "
            "`python main.py doctor` command that reports queue health (counts by status, orphans, "
            "duplicates, invariant violations, and for seeded missions any divergence from the "
            "Supabase mission_tasks rows) and with --fix applies the same auto-repairs — so the "
            "founder never again edits runtime JSON by hand. (d) atomic writes (write temp + "
            "rename) so an interrupted save cannot truncate the queue. "
            "NOTE ON SCOPE: m4c-03 covers the same orphan/duplicate/transient failure modes at the "
            "graph level; this task is the DATA layer beneath it (schema, invariants, repair, "
            "doctor). Read m4c-03's description first and do not duplicate its graph-level work — "
            "build the substrate it will use, and say plainly in the summary where the boundary "
            "was drawn."
        ),
    },
    {
        "id": "m4c0-04-startup-preflight",
        "title": "M4c.0: startup preflight — verify production assumptions once, loudly, before working",
        "type": "infra",
        "branch": "feature/m4c0/startup-preflight",
        "description": (
            "A recurring failure shape: the runner assumes something about the world that is only "
            "true on the founder's laptop, then discovers it 40 minutes into a task, or never. "
            "Real instances: public._runner_migrations existed locally but not in the production "
            "database (the M1 RLS migration failed on it); three merged additive SQL files were "
            "never applied to production, leaving Execute 500ing (M4a); the Vercel project was not "
            "git-connected, so main merged for hours while production served stale code and the "
            "founder debugged a 'missing feature' that was in the repo the whole time (M4b); a "
            "wrong repo name (testflow vs testflow-demo) burned a full run before failing at clone. "
            "Required: a preflight that runs ONCE at loop startup and reports a single consolidated "
            "PASS/WARN/FAIL summary before any task is claimed. Checks: pending migrations in "
            "supabase/migrations not present in the _runner_migrations ledger; deployed production "
            "SHA vs origin/main; Vercel project reachable and git-connected; configured GitHub repo "
            "reachable (GET /repos/{owner}/{repo}); required tables present; git working tree clean "
            "and on main; every credential named in config actually resolvable. "
            "CRITICAL BEHAVIOUR: preflight REPORTS, it does not halt — except for the two "
            "conditions that make work actively unsafe (dirty tree / wrong branch, per m4c-01). "
            "Everything else is a loud Slack warning and the loop continues; a preflight that "
            "blocks would just become a new source of stops, which is exactly what this mission "
            "exists to reduce. Emit `preflight_report` with per-check status so a later failure can "
            "be traced back to a warning that was already visible at startup."
        ),
    },
    {
        "id": "m4c0-05-stop-reason-diagnostics",
        "title": "M4c.0: every loop stop names its cause and its fix",
        "type": "backend",
        "branch": "feature/m4c0/stop-diagnostics",
        "description": (
            "Today a stop reason is a bare token — 'awaiting_resources', 'stale_run', "
            "'chatgpt_no_task', 'consecutive_failures' — and the founder reconstructs what actually "
            "happened by grepping runs.jsonl and reading graph.py. That reconstruction cost is a "
            "large share of the debugging time this mission is meant to eliminate, and it is why "
            "the same stop has been misdiagnosed more than once (chatgpt_no_task looked like a "
            "planner problem when the queue was strict-mode-exhausted; stale_run looked like a hang "
            "when it was a 4106-minute-old timestamp from a previous session). "
            "Required: a single diagnostics module that, whenever the loop stops, writes ONE "
            "structured record to outbox/loop_stop_report.txt and one Slack message containing: the "
            "stop reason; the triggering task and its status; the immediately preceding 5 events; "
            "the specific config values that produced the stop (e.g. stale_minutes vs "
            "MAX_STALE_TASK_MINUTES, both printed); a plain-language CAUSE sentence; and a "
            "RECOMMENDED ACTION naming the exact command or config change that resolves it. Every "
            "existing stop reason must have a handler with a written cause/action; a stop reason "
            "with no handler is itself a test failure, so new stop reasons cannot be added without "
            "diagnostics. Also classify each stop as EXPECTED (seeded_queue_exhausted, "
            "max_loop_tasks, cooldown) or ANOMALOUS (everything else) and mark it in the message — "
            "so a glance at the phone distinguishes 'finished' from 'broke'. This is the direct "
            "input to m4c-06's watchdog: it decides whether to auto-restart based on this "
            "classification."
        ),
    },
]


def main() -> int:
    path = Path(__file__).parent / ".runtime" / "tasks.local.json"
    tasks = json.loads(path.read_text())

    existing = {t.get("id") for t in tasks}
    new = []
    for spec in TASKS:
        if spec["id"] in existing:
            print(f"skip (already present): {spec['id']}")
            continue
        new.append({
            **spec,
            "status": "queued",
            "source": "founder_seed",
            "mission": "M4c.0 — Error-Rate Reduction",
            "runner_target": "self",
        })

    if not new:
        print("nothing to insert")
        return 0

    # Front of the file: get_next_queued_task() returns the first queued entry,
    # so M4c.0 must precede the already-queued M4c tasks.
    tasks = new + tasks
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(tasks, indent=2))
    tmp.replace(path)

    for t in new:
        print(f"queued at front: {t['id']}")
    print(f"\n{len(new)} M4c.0 tasks inserted. Verify with: python main.py next-task")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
