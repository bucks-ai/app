"""Seed M4c.4 post-merge-sync fix + reconcile the queue after the 2026-08-08 run.

Run once:  python seed_m4c4_post_merge_sync.py

THIS SCRIPT DOES THREE THINGS (all to .runtime/tasks.local.json):
  1. Adds m4c4-08-post-merge-main-sync at the FRONT of the queue.
  2. Marks m4c4-06-repo-health-preflight complete — it is merged (PR 107,
     1866d93) and deployed, but the completion-evidence gate blocked it for
     the very bug m4c4-08 fixes. Left alone it would be rebuilt from scratch.
  3. Amends m4c4-07's description with new evidence found in the same run.

THE RUN THAT PRODUCED ALL THIS (2026-08-08 16:23-16:40): the first fully
successful task since the check.sh deadlock was cleared. The worker wrote
914 lines across 7 files, check.sh passed, it committed e7b1004, pushed,
opened PR 107, checks passed, the PR MERGED as 1866d93, Vercel deployed
READY, and e2e passed. Every stage succeeded. The task was then marked
BLOCKED, and the founder had to recover it by hand with `git pull`.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json

COMPLETED_ID = "m4c4-06-repo-health-preflight"
TRUNCATION_ID = "m4c4-07-checkpoint-path-truncation"

TASKS = [
    {
        "id": "m4c4-08-post-merge-main-sync",
        "title": "M4c.4: land the merge locally before deleting the branch that holds it",
        "type": "backend",
        "branch": "feature/m4c4/post-merge-main-sync",
        "description": (
            "THE INCIDENT (2026-08-08, m4c4-06-repo-health-preflight): every stage of the pipeline "
            "succeeded and the task was still marked blocked. Verbatim event sequence from "
            "runs.jsonl:\n\n"
            "  16:40:29  branch_created  feature/m4c4/repo-health-preflight   <- runner checks out the feature branch\n"
            "  16:40:31  pr_created      number 107\n"
            "  16:40:31  pr_checks_completed  success\n"
            "  16:40:33  pr_merged       sha 1866d939...                      <- merged on GitHub\n"
            "  16:40:33  git_sync        step: fetch_pull_main\n"
            "  16:40:34  git_rebase_completed  upstream origin/main, success  <- rebased the CHECKED-OUT branch, not main\n"
            "  16:40:34  error           git branch -d ... 'not fully merged'\n"
            "  16:40:34  branch_cleanup_forced                                 <- -D forced\n"
            "  16:40:35  branch_cleanup_completed  'Deleted branch ... (was 1866d93)'\n"
            "  16:40:39  task_completion_evidence_missing  'none of the 7 claimed file(s) exist on disk;\n"
            "                                              no new commit - the tree was already clean,\n"
            "                                              so HEAD predates this task'\n"
            "  16:40:39  gate_blocked    completion_evidence\n\n"
            "THE DEFECT: `fetch_pull_main` ran while the FEATURE branch was checked out, so the "
            "rebase advanced that branch to the merge commit (1866d93) and local `main` was never "
            "moved. The cleanup step then force-deleted the feature branch — the only local ref "
            "holding the merged state — and dropped the tree back to a `main` two commits behind. "
            "The files disappeared from disk, so the completion-evidence gate correctly observed "
            "that nothing existed and blocked a task that had in fact fully succeeded.\n\n"
            "  Founder's local main : b3f4fb5   (behind 2)\n"
            "  origin/main          : 1866d93   (merge) <- e7b1004 (the actual work, 914 lines / 7 files)\n\n"
            "Recovery was a single `git pull --ff-only`. Nothing was lost THIS time because the "
            "branch had been pushed — but the runner force-deleted a local branch holding state "
            "that existed nowhere else locally, which is precisely the class of move that caused "
            "the m4c-03 incident m4c4-01 exists to prevent.\n\n"
            "BLAST RADIUS: this is not one unlucky task. Every task that merges successfully takes "
            "this same path, so EVERY success is recorded as a blocked failure, the work is "
            "invisible on disk afterwards, and the queue will rebuild already-merged work from "
            "scratch. It also silently defeats the completion-evidence gate's purpose: the gate "
            "can no longer distinguish 'the worker did nothing' from 'the runner threw the result "
            "away', because both look identical to it.\n\n"
            "REQUIRED: (a) after a successful merge, check out the base branch (main) and "
            "fast-forward it to the merge commit BEFORE any branch cleanup runs. Never rebase or "
            "pull 'main' while a different branch is checked out and call it a main sync. (b) "
            "VERIFY before destroying: refuse to delete the feature branch unless the merge commit "
            "is provably reachable from local main (`git merge-base --is-ancestor <merge_sha> "
            "main`). If it is not reachable, skip the cleanup, log loudly, and leave the branch "
            "alone — an undeleted branch is a trivial cleanup task, a deleted one can be data "
            "loss. (c) never use `git branch -D` on a branch whose head is not reachable from "
            "main; today's code force-deletes on `-d` refusal, which is exactly backwards — `-d` "
            "refusing IS the signal that the state is not safely landed. (d) log a "
            "`main_fast_forwarded` event with the before/after shas so the sync is auditable.\n\n"
            "(e) THE GATE MUST SEE THE MERGE. Completion evidence should accept a merged PR as "
            "artifact evidence in its own right — the merge sha, the PR number, and the files in "
            "that commit are stronger proof than files sitting on disk. Checking only the working "
            "tree means the gate is blind to work that has already landed.\n\n"
            "SCOPE BOUNDARY: do not change the merge decision, the PR flow, the checks polling, or "
            "what the completion-evidence gate requires for tasks that did NOT merge. This is the "
            "post-merge local-state sync, the safety condition on branch deletion, and teaching "
            "the gate to count a merge as evidence.\n\n"
            "TESTS: after a successful merge, local main is fast-forwarded to the merge commit "
            "before cleanup; branch deletion is SKIPPED when the merge commit is not an ancestor "
            "of local main; `-D` is never issued for an unreachable head; a merged PR satisfies "
            "the completion-evidence artifact requirement even when the working tree is clean and "
            "the branch is gone; a task that genuinely produced nothing is still blocked; the "
            "`main_fast_forwarded` event records before/after shas; a failed fast-forward aborts "
            "cleanup rather than proceeding. Mock every git call and the GitHub API — no real repo "
            "or network operations in tests."
        ),
    },
]

# Appended to m4c4-07: the same run proved the truncation bug is not cosmetic.
TRUNCATION_EVIDENCE = (
    "\n\nFURTHER EVIDENCE (2026-08-08, m4c4-06 run): the completion-evidence gate emitted "
    "this reason verbatim —\n\n"
    "  \"none of the 7 claimed file(s) exist on disk: `runner/langgraph/tools/"
    "repo_health_preflight.py`, `runner/langgraph/tests/test_repo_health_preflight.py`, ...\"\n\n"
    "The paths carry their markdown BACKTICKS into the existence check, so the gate is "
    "calling exists() on the literal string \"`runner/...py`\" — which can never match. That "
    "is the same parser that produced 'unner/' and 'ools/': a naive strip of the leading "
    "backtick (path[1:]) that eats the first real character when the backticks were already "
    "removed, and leaves them in place when they were not. Fix the backtick handling and the "
    "off-by-one together — they are one bug — and add a test asserting a backtick-wrapped "
    "path from a worker summary resolves to the bare path.\n\n"
    "NOTE ON PRIORITY: in that run the files were ALSO genuinely absent from disk for an "
    "unrelated reason (see m4c4-08 — local main was never fast-forwarded past the merge). "
    "Both bugs must be fixed; do not assume fixing the backticks alone will make the gate "
    "pass."
)


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

    # 2. Reconcile m4c4-06: merged as 1866d93 and deployed, but gate-blocked.
    target = by_id.get(COMPLETED_ID)
    if target is None:
        print(f"WARNING: {COMPLETED_ID} not found — cannot reconcile its status")
    elif target.get("status") == "complete":
        print(f"already complete: {COMPLETED_ID}")
    else:
        was = target.get("status")
        target["status"] = "complete"
        target["completion_note"] = (
            "Merged as 1866d93 (PR 107) and deployed READY; e2e passed. The "
            "completion-evidence gate blocked it because local main was never "
            "fast-forwarded past the merge (see m4c4-08). Reconciled by hand."
        )
        print(f"reconciled: {COMPLETED_ID}  {was} -> complete")

    # 3. Amend m4c4-07 with the backtick evidence from the same run.
    trunc = by_id.get(TRUNCATION_ID)
    if trunc is None:
        print(f"WARNING: {TRUNCATION_ID} not found — evidence not appended")
    elif "FURTHER EVIDENCE" in (trunc.get("description") or ""):
        print(f"evidence already present: {TRUNCATION_ID}")
    else:
        trunc["description"] = (trunc.get("description") or "") + TRUNCATION_EVIDENCE
        print(f"amended with new evidence: {TRUNCATION_ID}")

    # Post-merge sync first: it turns every success into a false failure, so it
    # blocks the value of everything behind it. Truncation fix second.
    order = [
        "m4c4-08-post-merge-main-sync",
        TRUNCATION_ID,
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
