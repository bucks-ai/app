"""Seed m4c-11-supervisory-early-stop, sequenced BEFORE m4c-10.

Run once:  python seed_supervisory_early_stop.py

WHY BEFORE m4c-10: m4c-10's acceptance test is "run a real mission overnight,
unattended, and report exactly how many times the founder was touched." Running
that before these rules exist certifies a system that still needs a human ~6
times a week. Build the rules, then measure.

WHY DETERMINISTIC AND NOT AN LLM SUPERVISOR (founder decision 2026-08-11):
every founder intervention during 2026-08-04..11 was pattern-matching over
events the runner had already logged — not judgment. A 401 is a 401. The same
named check failing on four unrelated branches is a fact. 4.4M tokens with zero
merges is arithmetic. An LLM supervisor would spend tokens to reach conclusions
a pure function reaches for free, cannot be unit-tested, and its failure mode
(overriding a gate wrongly, unauditably) is the exact inversion of this
mission's founding rule: trustworthy state BEFORE autonomy.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json

BEFORE_ID = "m4c-10-verification-report"

TASKS = [
    {
        "id": "m4c-11-supervisory-early-stop",
        "title": "M4c: stop early on failures no worker can fix — the babysitter watches the run, not just the task",
        "type": "backend",
        "branch": "feature/m4c/supervisory-early-stop",
        "description": (
            "THE EVIDENCE (2026-08-04..11, one week, six founder interventions). In EVERY case "
            "the signal the runner needed was already in its own runs.jsonl. It never asked.\n\n"
            "  1. A stale package-lock.json failed `npm ci`, aborting scripts/check.sh at line 7 "
            "     under `set -euo pipefail`. Every worker did its full task, could not verify, "
            "     correctly refused to commit, and reported 'Commit Result: skipped'. Days lost; "
            "     ~2,900s of worker time discarded; the founder's monthly credits hit 101% on work "
            "     that was performed and thrown away. (m4c4-06 now DETECTS this class.)\n"
            "  2. A revoked OAuth token returned `api_error_status: 401, \"OAuth access token has "
            "     been revoked\"`. The runner recorded it verbatim as 'worker returned no output', "
            "     scheduled a RETRY, and logged `claude_subscription_cooldown_resumed`. A revoked "
            "     token can never be fixed by retrying.\n"
            "  3. `E2E (Playwright)` failed identically on PRs 113, 114, 115 and 116 — four "
            "     unrelated branches, byte-identical `conclusions` payloads, while 'Lint, "
            "     typecheck, build' and 'Runner tests' were green on all four. The runner "
            "     dispatched `deterministic_repair_attempted` workers anyway. One of those main "
            "     attempts alone consumed 4,367,840 tokens.\n"
            "  4. PRs 110, 111 and 112 merged after a SINGLE poll: `poll: 1, elapsed: 0.26, "
            "     total: 1, completed: 1` — the runner saw one registered check, concluded "
            "     everything passed, and merged. App CI had been red for 13 consecutive runs.\n"
            "  5. The founder removed `E2E (Playwright)` from GitHub's required checks, but the "
            "     runner's own gate still failed on it because PR_CHECKS_NON_BLOCKING did not "
            "     match. Two gates, one repo, disagreeing silently.\n"
            "  6. 4.4M tokens spent across a session with zero merges, and nothing said so.\n\n"
            "THE PRINCIPLE: the babysitter currently judges TASKS. It must also judge the RUN. A "
            "failure that no worker can fix must be recognised BEFORE the repair budget is spent "
            "on it, not after.\n\n"
            "REQUIRED — five rules. All are PURE FUNCTIONS over already-logged events and config; "
            "none may call a model, and none may override an existing gate's decision. They only "
            "ever STOP EARLIER or SKIP, never proceed where a gate said stop.\n\n"
            "(a) CI FAILURE: ENVIRONMENTAL vs TASK. Before routing a `ci_check_failure` to "
            "repair, determine whether the SAME NAMED CHECK is also failing on the base commit or "
            "on other open PRs. If it is, classify environmental: do NOT repair, do NOT burn the "
            "repair or retry budget, mark the task skip-and-continue (the m4c-07 path), and emit "
            "ONE `ci_failure_environmental` event naming the check and the corroborating "
            "branches. This is m4c4-06's check.sh classification generalised to CI.\n\n"
            "(b) AUTH FAILURES ARE NEVER RETRYABLE. A 401/403 from the worker CLI, or any body "
            "matching revoked/expired/invalid token or 'failed to authenticate', halts the loop "
            "immediately with a `worker_auth_failed` stop reason whose report says plainly that "
            "re-authentication is required and names the command (`claude` then `/login`). Never "
            "a retry, never a cooldown, never 'worker returned no output'. Add it to "
            "loop_watchdog.HARD_GATE_REASONS — a human must act.\n\n"
            "(c) CHECK-COUNT STABILITY BEFORE TRUSTING CONCLUSIONS. A check set is only "
            "trustworthy once its total has been stable across two consecutive polls, or matches "
            "the repository's branch-protection required-checks list. Until then, keep polling — "
            "PR_CHECKS_EMPTY_GRACE_S covers zero checks but nothing covers 'some registered, "
            "others have not yet'. This is the bug that merged three unverified PRs.\n\n"
            "(d) RECONCILE THE TWO GATES AT STARTUP. Fetch the repo's actual required-status-check "
            "contexts and compare against what the runner will treat as blocking "
            "(PR_CHECKS_NON_BLOCKING). If they disagree, log `pr_gate_mismatch` at startup naming "
            "both sets. The runner must never be stricter than the repo without saying so out "
            "loud. Report only — do not auto-change either side.\n\n"
            "(e) SPEND-WITHOUT-PROGRESS CEILING. Track cumulative tokens and elapsed time against "
            "merges completed this session. Past a configurable ceiling with zero merges, stop "
            "with a `no_progress_for_spend` reason and a report stating tokens spent, tasks "
            "attempted, and merges achieved.\n"
            "  PREREQUISITE, IN SCOPE HERE: the runner currently parses `total_cost_usd` and the "
            "  `usage` block from the Claude CLI JSON ONLY on the failure path — successful runs "
            "  record `session_cost: 0.0`, so per-task cost and tokens do not exist for any task "
            "  that worked. Parse them on the SUCCESS path too, accumulate into session_cost, and "
            "  include tokens/cost in `run_summary_digest` and "
            "  `live_batch_validation_complete`. Rule (e) cannot function without this, and it "
            "  also closes the observability gap that made 'what does a task cost?' unanswerable.\n\n"
            "SCOPE BOUNDARY — read carefully. Do NOT build an LLM supervisor, a second agent, or "
            "anything that reasons about whether a run is 'going well'. Do NOT let any rule here "
            "cause work to PROCEED that a gate blocked; these rules only stop earlier or skip. Do "
            "NOT modify the repair mechanism itself (m4c4-02), the completion-evidence gate, or "
            "the cooldown path — only the routing decision that precedes repair. Do NOT auto-fix "
            "environmental problems (lockfiles, tokens, CI config): detect, classify, report, "
            "halt. Fixing them is a human's job by design.\n\n"
            "CONFIG (three-place rule): SUPERVISORY_EARLY_STOP_ENABLED (default true), "
            "MAX_SESSION_TOKENS_WITHOUT_MERGE, MAX_SESSION_MINUTES_WITHOUT_MERGE. Disabled "
            "restores today's behaviour exactly.\n\n"
            "TESTS: a CI check failing on base AND branch classifies environmental and spends no "
            "repair budget; a check failing only on the branch still routes to repair as today; a "
            "401 halts with `worker_auth_failed` and is never retried; a 429 still takes the "
            "cooldown path and a 5xx still takes the transient path; an unstable check count keeps "
            "polling and does not merge; a stable count merges as today; mismatched gate sets emit "
            "`pr_gate_mismatch` and change nothing; the spend ceiling stops with the right reason "
            "and figures; tokens and cost are recorded on the SUCCESS path and appear in the run "
            "digest; every rule is a no-op when disabled. Pure functions for all five decisions — "
            "mock the GitHub API, the CLI and the clock; no network in tests."
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
            "mission": "M4c — Loop Babysitter & Continuous Operation",
            "runner_target": "self",
        })

    if BEFORE_ID not in by_id:
        print(f"WARNING: {BEFORE_ID} not found — appending instead of inserting")

    # Insert immediately BEFORE m4c-10 so verification measures the system we
    # actually want, rather than certifying one that still needs a human.
    merged = added + tasks
    new_task = added[0] if added else None
    if new_task:
        merged = [t for t in merged if t["id"] != new_task["id"]]
        out, placed = [], False
        for t in merged:
            if t.get("id") == BEFORE_ID and not placed:
                out.append(new_task)
                placed = True
            out.append(t)
        if not placed:
            out.append(new_task)
        merged = out

    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(merged, indent=2))
    tmp.replace(path)

    for t in added:
        print(f"seeded before {BEFORE_ID}: {t['id']}  [{t['status']}]")
    print(f"\n{len(added)} new task(s) added. Verify: python main.py next-task")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
