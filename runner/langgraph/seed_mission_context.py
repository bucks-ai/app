"""Seed m4c0-06 — Mission context briefing + already-satisfied precheck.

Run once:  python seed_mission_context.py

WHY (founder + architect, 2026-08-04): every worker invocation is a FRESH
`claude --print` call with no memory of anything before it. The prompt is ~1,900
characters built from title/type/branch/description. The worker therefore does
not know: which mission it belongs to, that a plan was already approved, what
the previous tasks in that mission already built, or what later tasks will
build. Three observed failure classes trace directly to that blindness:

  1. DUPLICATE IMPLEMENTATION. m4a-01 was implemented twice by two workers and
     resolved only because the founder hand-picked which copy to keep. m4c-03's
     work was written three separate times across halted sessions. Neither CI,
     nor the completion-evidence gate, nor the merge path can catch this: the
     duplicate is real work, it has file evidence, it may pass tests, and if it
     does not conflict it merges clean — leaving two implementations of one
     feature and no signal that anything is wrong.
  2. REFUSAL / CLARIFYING QUESTION. A worker judged a deploy "consequential and
     irreversible" and asked what to do instead of acting. It was step 3 of a
     mission the founder had already approved; nothing in its prompt said so.
  3. SCOPE CREEP. Workers occasionally implement adjacent tasks that belong to
     later positions in the same mission.

NOT the fix: giving workers a shared session or persistent memory. Statelessness
is deliberate — it makes retries reproducible, prevents context poisoning over
long runs, and keeps each task's token cost near-flat. The fix is BETTER INPUTS.

NOT the fix either: telling the worker to "explore the codebase first". Claude
Code already reads AGENTS.md/CLAUDE.md; unbounded exploration burns the CLI
timeout budget and still does not reveal WHICH files the previous task touched.
Targeted pointers beat exploration.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json

TASK = {
    "id": "m4c0-06-mission-context-briefing",
    "title": "M4c.0: give every worker its mission context and an already-satisfied precheck",
    "type": "backend",
    "branch": "feature/m4c0/mission-context",
    "description": (
        "Two changes, both aimed at work the runner currently cannot detect it is redoing.\n\n"
        "PART 1 — MISSION BRIEFING IN THE PROMPT. Add a pure function (new module, e.g. "
        "tools/mission_briefing.py) that takes the current task plus the local task queue and "
        "returns a briefing block, and inject it into _TASK_PROMPT_TEMPLATE and "
        "_BUSINESS_TASK_PROMPT_TEMPLATE in graph.generate_worker_prompt. All the data already "
        "exists in .runtime/tasks.local.json — no API calls, no extra cost. The block must state: "
        "(a) the mission name and goal; (b) this task's position, e.g. 'You are task 5 of 10'; "
        "(c) ALREADY DONE — the completed tasks of this same mission, most recent 5, each as id + "
        "title + the files it reported creating/modifying, under an explicit heading that says "
        "this work is already merged and must NOT be rebuilt; (d) STILL TO COME — the titles of "
        "later queued tasks in the mission, under a heading saying they are NOT this task's job; "
        "(e) one line stating the mission plan was approved by the founder, so the work is "
        "pre-authorised and the correct action is to execute, not to ask whether to proceed.\n\n"
        "CONSTRAINTS: cap ALREADY DONE at 5 entries plus a count of the rest so a 25-task mission "
        "cannot bloat the prompt; label those summaries as REPORTED BY THE WORKER, not verified "
        "(worker summaries can and do lie — that is what the completion-evidence gate exists for); "
        "omit the whole block cleanly for tasks with no mission (source != seeded_mission and no "
        "founder_seed mission), leaving today's prompt byte-identical. Log a prompt_briefing_added "
        "event with the block's character count so prompt growth stays observable.\n\n"
        "PART 2 — ALREADY-SATISFIED PRECHECK. Before the worker runs, cheaply test whether the "
        "task's deliverable already exists: parse file paths and exported symbol names out of the "
        "task description, check the working tree for them, and if everything named is already "
        "present, log task_already_satisfied with the evidence and mark the task complete WITHOUT "
        "dispatching a worker. Be conservative — this must never skip real work. Require an exact "
        "path match (not a fuzzy name match), require EVERY named artifact to exist (not any), and "
        "when the description names no concrete artifacts, always dispatch. Add a config flag "
        "(three-place rule) defaulting to ON, and a per-task override so a task can force a "
        "dispatch. Rationale: this is the one duplicate-work case nothing else catches — CI passes, "
        "the completion-evidence gate is satisfied by the duplicated files, and a non-conflicting "
        "reimplementation merges clean.\n\n"
        "TESTS: briefing content for a mid-mission task, a first task (empty ALREADY DONE), a "
        "no-mission task (block omitted entirely), and the 5-entry cap; precheck skips when all "
        "named artifacts exist, dispatches when any is missing, dispatches when none are named, and "
        "dispatches when the override is set. Pure functions — no worker invocation in tests.\n\n"
        "OUT OF SCOPE: persistent cross-task memory, shared worker sessions, and semantic duplicate "
        "detection at review time (a separate, later idea: prompt the existing independent-code-"
        "review gate to ask 'does this duplicate something already on main?')."
    ),
    "status": "queued",
    "source": "founder_seed",
    "mission": "M4c.0 — Error-Rate Reduction",
    "runner_target": "self",
}


def main() -> int:
    path = Path(__file__).parent / ".runtime" / "tasks.local.json"
    tasks = json.loads(path.read_text())

    if any(t.get("id") == TASK["id"] for t in tasks):
        print(f"already present: {TASK['id']}")
        return 0

    # Front of the queue: every later task benefits from the briefing, so this
    # must land before the rest of M4c runs.
    tasks = [TASK] + tasks
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(tasks, indent=2))
    tmp.replace(path)
    print(f"queued at front: {TASK['id']}")
    print("verify with: python main.py next-task")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
