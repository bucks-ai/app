"""Seed M4c.4 follow-ups (2 tasks) at the FRONT of the local queue.

Run once:  python seed_m4c4_followups.py

BOTH TASKS COME FROM ONE INCIDENT, 2026-08-05..08. A single broken file
(package-lock.json, missing the @emnapi optional-platform entries) made
`npm ci` fail, which under `set -euo pipefail` aborted scripts/check.sh at
line 7 — before lint, typecheck, tests, or build ever ran. Every worker
therefore did its full task, failed verification for a reason that had
nothing to do with its task, correctly refused to commit unverified work,
and reported `Commit: skipped`. The completion-evidence gate then found no
sha and blocked the task. Work was left uncommitted; the next run started
over. This repeated for DAYS across every task in the queue.

Cost of not detecting it: m4c4-05-network-pause burned 1260s of worker time
and m4c4-02 burned 447s and $1.38 in a single call, both producing zero
committed output. The founder's usage credits were exhausted (101% of the
monthly limit) entirely on work that was performed and then discarded. The
runner never once said "the repo was already broken" — it only ever said
"Commit: skipped", which reads as a worker problem.

The founder fixed the lockfile by hand in 75a0e28. These two tasks make
sure the class of failure is impossible to miss next time.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json

TASKS = [
    {
        "id": "m4c4-06-repo-health-preflight",
        "title": "M4c.4: never dispatch a worker into an already-broken repo",
        "type": "backend",
        "branch": "feature/m4c4/repo-health-preflight",
        "description": (
            "THE INCIDENT (2026-08-05..08): the committed package-lock.json was missing two "
            "optional-platform entries (@emnapi/core@2.0.0-alpha.3, @emnapi/runtime@2.0.0-alpha.3). "
            "`npm ci` is strict about that and exits non-zero. scripts/check.sh runs `npm ci` on "
            "line 7 under `set -euo pipefail`, so the script aborted there EVERY TIME — lint, "
            "`next typegen`, `tsc --noEmit`, `npm test` and `npm run build` never executed at all.\n\n"
            "WHAT THAT DID TO THE LOOP, precisely: a worker was dispatched, did its full task and "
            "wrote real files to the working tree, ran ./scripts/check.sh as its final verification "
            "step, saw it fail, and — correctly, per its instructions — refused to commit "
            "unverified work. It reported `Files: created none; modified none` and "
            "`Commit Result: skipped`. The completion-evidence gate found no commit sha and no "
            "claimed artifacts, so it blocked the task (`task_completion_evidence_missing` -> "
            "`gate_blocked`). The task was requeued and the uncommitted work was left in the tree "
            "for the next run to trip over or discard.\n\n"
            "PROOF THE WORK WAS REAL, NOT ABSENT: after m4c4-02 reported 'created none; modified "
            "none', `git status --short` showed tools/failure_context_repair.py and "
            "tests/test_failure_context_repair.py as new untracked files plus a modified graph.py. "
            "The worker's own summary was FALSE — not because the worker lied, but because the "
            "runner asks the worker what it did instead of asking the repo.\n\n"
            "COST: m4c4-05-network-pause ran 1260.44s and m4c4-02 ran 447.07s at $1.38 in one "
            "call, both producing zero committed output. The founder's monthly usage credits hit "
            "101% on work that was performed and thrown away. Diagnosis took days of founder time "
            "and was found only by running scripts/check.sh by hand.\n\n"
            "REQUIRED — (a) A REPO-HEALTH PREFLIGHT at loop start, before any task is claimed and "
            "before any worker is dispatched: run scripts/check.sh once against the starting "
            "branch. If it fails, DO NOT dispatch. Stop the loop with a `repo_unhealthy` stop "
            "reason whose report states plainly which command failed, its exit code, and the "
            "relevant excerpt of its output (cap the excerpt), and says in one sentence that this "
            "is a PRE-EXISTING repo problem, not a task failure, and that no task can complete "
            "until it is fixed. Reuse the existing startup_preflight reporting surface (it already "
            "runs at loop start and already has a Slack path) rather than inventing a second one — "
            "but note this check HALTS, unlike the reporting-only checks already there.\n\n"
            "(b) DISTINGUISH THE TWO CHECK FAILURES EVERYWHERE DOWNSTREAM. A check.sh failure that "
            "reproduces on the pristine base commit is an ENVIRONMENT failure and must never be "
            "attributed to the task, must not burn retry_count or task_attempt_counts, must not "
            "feed consecutive_failures or the repeated-error guard, and must not mark the task "
            "failed or blocked. A check.sh failure that passes on base and fails on the task's "
            "branch is a genuine TASK failure and keeps today's handling exactly. When a worker's "
            "check fails mid-task, determine which case it is before deciding what to record.\n\n"
            "(c) SAY SO IN THE COMPLETION-EVIDENCE BLOCK. When the gate blocks a task for missing "
            "artifacts AND the most recent check failure was classified environmental, the gate's "
            "reasons must say that the work may exist uncommitted because verification was blocked "
            "by a broken repo — and list the actual dirty paths from `git status`. The founder must "
            "never again have to run `git status` by hand to discover that the work was done.\n\n"
            "TIMING/CONFIG: the preflight adds one check.sh run (~90s observed) per loop start, not "
            "per task — acceptable against a 20-minute worker. Config flag REPO_HEALTH_PREFLIGHT, "
            "three-place rule, default ON. A timeout config too, so a hanging check cannot wedge "
            "startup. When disabled, behaviour is exactly as today.\n\n"
            "SCOPE BOUNDARY: do NOT change scripts/check.sh itself, do not reorder its commands, "
            "and do not make any of its steps non-fatal. The script being strict is correct; the "
            "bug is that the runner dispatched work into a repo where it could not pass.\n\n"
            "TESTS: a failing base check halts at startup with the `repo_unhealthy` reason and the "
            "failing command in the report; a passing base check dispatches normally; a check that "
            "fails on base AND on branch is classified environmental and burns no counters and "
            "leaves task status untouched; a check that passes on base and fails on branch is "
            "classified a task failure and keeps existing handling; the completion-evidence block "
            "names the uncommitted paths when the failure was environmental; the preflight is "
            "skipped entirely when disabled; a check.sh timeout is handled and does not wedge "
            "startup. Mock the subprocess and the git calls — no real npm or network in tests."
        ),
    },
    {
        "id": "m4c4-07-checkpoint-path-truncation",
        "title": "M4c.4: stop truncating the first character off reported file paths",
        "type": "backend",
        "branch": "feature/m4c4/checkpoint-path-truncation",
        "description": (
            "THE BUG: the leading character is being stripped off file paths in the WIP-checkpoint "
            "file list. Observed verbatim in runs.jsonl on 2026-08-07:\n\n"
            "  {\"cmd\": [\"git\", \"add\", \"-A\", \"--\", \"unner/langgraph/tools/auto_repair_loop.py\"], "
            "\"returncode\": 128, \"output\": \"fatal: pathspec 'unner/langgraph/tools/"
            "auto_repair_loop.py' did not match any files\"}\n\n"
            "'runner/' became 'unner/'. The same corruption appears in a git_work_stashed payload "
            "as [\"ools/x.py\", \"NOTES.md\"] — 'tools/x.py' became 'ools/x.py' while the sibling "
            "path in the same list was untouched. One leading character, only on paths that have a "
            "directory prefix. Strongly suggests a prefix-stripping calculation off by one, or "
            "`lstrip()` being used with a prefix string where `removeprefix()` was meant (lstrip "
            "takes a CHARACTER SET, not a prefix — `'runner/x'.lstrip('/home/arnav/bucks-ai/')` "
            "eats the leading 'r'). Find the actual site; do not guess from this description.\n\n"
            "WHY IT MATTERS DESPITE LOOKING COSMETIC: the targeted `git add` FAILED (exit 128). "
            "Work survived only because a `git add -A` fallback happened to stage the file anyway — "
            "commit 0203cd3 does contain the correct path runner/langgraph/tools/auto_repair_loop.py "
            "with 287 insertions. So today this is one failed command masked by a fallback. But the "
            "checkpoint's whole purpose (m4c4-01) is that work is never lost, and the corrupted "
            "list is what gets reported: the `wip_checkpointed` event payload, the 'Files:' section "
            "of outbox/loop_stop_report.txt, the commit message body, and the Slack message all "
            "printed the wrong path. A founder recovering work is told to look at a file that does "
            "not exist. If the fallback is ever removed or fails, this silently loses the file.\n\n"
            "REQUIRED: (a) find and fix the truncation at its source — one bug, likely one line; "
            "(b) audit every OTHER path that flows through the same helper (stash file lists, "
            "checkpoint file lists, excluded_paths, the stop report, the commit message body, the "
            "Slack payload) and confirm each is correct; (c) make the failure loud rather than "
            "silently fallback-masked — if a targeted `git add` fails on a path the runner itself "
            "generated, that is an internal inconsistency and must log at error level with both "
            "the generated path and the path as git reports it, even when a fallback subsequently "
            "succeeds.\n\n"
            "SCOPE BOUNDARY: do not rewrite the checkpoint mechanism, do not remove the `git add -A` "
            "fallback (it is what saved the work), and do not change what gets checkpointed. This "
            "is a path-string correctness fix plus the logging that would have surfaced it.\n\n"
            "TESTS: a repo-relative path with a directory prefix survives round-trip unmodified; an "
            "absolute path under the repo root converts to the correct repo-relative path with no "
            "character loss; a path whose first character matches a character in the repo root "
            "string is NOT truncated (this is the regression that would catch an lstrip misuse — "
            "e.g. repo root /home/arnav/bucks-ai and a path starting with 'a', 'b', 'h', 'r' or "
            "'/'); a top-level file with no directory prefix is unaffected; a failed targeted "
            "`git add` logs an error even when the fallback succeeds. Mock all git calls — no real "
            "repo operations in tests."
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

    # Repo-health preflight goes first: it is the one that stops a broken repo
    # from silently eating every task behind it. The truncation fix follows.
    order = [
        "m4c4-06-repo-health-preflight",
        "m4c4-07-checkpoint-path-truncation",
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
