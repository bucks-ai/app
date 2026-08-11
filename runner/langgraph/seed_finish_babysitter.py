"""Seed the truncation re-fix and order the last three babysitter tasks.

Run once:  python seed_network_pause.py && python seed_finish_babysitter.py

FINAL ORDER SET HERE:
  1. m4c0-06-mission-context-briefing   — already half-built and checkpointed
                                          at 391232025e9b (6 files, pushed);
                                          finishing is now cheaper than the
                                          deferral, so it is un-deferred.
  2. m4c4-05b-network-pause-watchdog    — from seed_network_pause.py
  3. m4c4-12-path-truncation-refix      — new, seeded here

After these three, the M4c babysitter mission is complete: M4c core 11/11,
M4c.0 6/6, M4c.4 8/8.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json

TASKS = [
    {
        "id": "m4c4-12-path-truncation-refix",
        "title": "M4c.4: the first path in every list still loses its first character",
        "type": "backend",
        "branch": "feature/m4c4/path-truncation-refix",
        "description": (
            "m4c4-07 SHIPPED AND HALF-WORKED. Its part (c) — make the failure loud instead of "
            "fallback-masked — works: `wip_checkpoint_add_targeted_failed` is a new event and it "
            "fired correctly on 2026-08-11 at 04:00:51. Its part (a), the actual truncation fix, "
            "did NOT land. The bug is still live on main.\n\n"
            "THE SIGNATURE IS NOW PRECISE, AND IT IS NOT WHAT WAS ORIGINALLY GUESSED. Every "
            "observed instance truncates the FIRST element of the path list and leaves every "
            "other element intact:\n\n"
            "  2026-08-07  [\"unner/langgraph/tools/auto_repair_loop.py\"]\n"
            "              single-item list — the one item is truncated\n"
            "  (tests)     [\"ools/x.py\", \"NOTES.md\"]\n"
            "              'tools/x.py' -> 'ools/x.py'; the sibling is untouched\n"
            "  2026-08-11  [\"unner/langgraph/README.md\", \"runner/langgraph/config.py\",\n"
            "               \"runner/langgraph/graph.py\", \"runner/langgraph/state.py\",\n"
            "               \"runner/langgraph/tests/test_mission_briefing.py\",\n"
            "               \"runner/langgraph/tools/mission_briefing.py\"]\n"
            "              index 0 truncated; indices 1-5 all correct\n\n"
            "ALWAYS index 0. NEVER any other index. That rules out the per-path `lstrip()` "
            "hypothesis recorded in m4c4-07 (which would corrupt every element whose first "
            "character happened to appear in the prefix) and points instead at LIST handling — a "
            "slice, a split/join round-trip, an argv assembly step that drops one character from "
            "the head, or an off-by-one where a separator is stripped from a concatenated string. "
            "FIND THE SITE. Do not fix it by guessing; the previous attempt guessed and shipped "
            "the wrong half.\n\n"
            "WHY IT MATTERS despite work not being lost so far: the targeted `git add` genuinely "
            "FAILS (`returncode: 128, fatal: pathspec ... did not match any files`) and only a "
            "`git add -A` fallback saves the commit. Every recovery instruction the runner prints "
            "— the stop report's 'UNCOMMITTED WORK AT THE STOP' file list, the checkpoint commit "
            "body, the Slack message — names a file that does not exist. A founder following those "
            "instructions is sent to a path that cannot be checked out. The checkpoint's entire "
            "purpose (m4c4-01) is that work is never lost; a recovery pointer that lies is a "
            "silent liability the moment the fallback is removed or fails.\n\n"
            "REQUIRED: (a) locate the actual truncation site by reproducing it in a test FIRST — "
            "a list of >=2 repo-relative paths must survive whatever transformation the checkpoint "
            "applies, with index 0 intact; (b) fix it; (c) verify the same list flows correctly "
            "into ALL FOUR consumers: the `wip_checkpointed` event payload, "
            "outbox/loop_stop_report.txt, the checkpoint commit message body, and the Slack "
            "payload; (d) audit `git_work_stashed` / `git_work_restored` / `excluded_paths`, which "
            "carry file lists through the same helpers and show the same corruption in test "
            "fixtures.\n\n"
            "SCOPE BOUNDARY: do NOT remove the `git add -A` fallback — it is what has prevented "
            "data loss so far. Do NOT rewrite the checkpoint mechanism. Do NOT touch the loud-"
            "failure logging m4c4-07 added; it is correct and it is how this bug was caught. This "
            "is a string/list correctness fix and its verification, nothing more.\n\n"
            "TESTS (write the failing test before the fix): a 6-element repo-relative path list "
            "round-trips with index 0 byte-identical; a 1-element list round-trips; a 2-element "
            "list round-trips; an absolute path under the repo root converts to the correct "
            "repo-relative path with no character loss; the four consumers above all receive the "
            "uncorrupted list; a targeted `git add` built from a generated list succeeds against a "
            "real temp repo (this is the assertion that would have caught m4c4-07's miss — it "
            "shipped with mocks that never exercised the real pathspec). Mock git elsewhere; no "
            "operations against the live repo."
        ),
    },
]

# Final order for the last three babysitter tasks.
ORDER = [
    "m4c0-06-mission-context-briefing",
    "m4c4-05b-network-pause-watchdog",
    "m4c4-12-path-truncation-refix",
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

    # m4c0-06 was deferred by queue POSITION, not status. It is now half-built
    # and checkpointed, so finishing it is cheaper than leaving it parked.
    briefing = by_id.get("m4c0-06-mission-context-briefing")
    if briefing is None:
        print("WARNING: m4c0-06-mission-context-briefing not found")
    else:
        if briefing.get("status") == "running":
            print("m4c0-06: status 'running' (stranded) -> queued")
            briefing["status"] = "queued"
        briefing.pop("deferred_note", None)
        briefing["wip_note"] = (
            "Partial work checkpointed at 391232025e9b on "
            "feature/m4c0/mission-context (6 files, pushed). Continue from it; "
            "do not restart from scratch."
        )
        print("m4c0-06: un-deferred, WIP checkpoint recorded")

    if "m4c4-05b-network-pause-watchdog" not in by_id:
        print("NOTE: m4c4-05b not found — run `python seed_network_pause.py` first")

    pool = {t["id"]: t for t in (added + tasks)}
    front = [pool.pop(tid) for tid in ORDER if tid in pool]
    rest = [t for t in (added + tasks) if t["id"] in pool]

    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(front + rest, indent=2))
    tmp.replace(path)

    print("\nREMAINING BABYSITTER TASKS:")
    for i, t in enumerate(front, 1):
        print(f"  {i}. {t['id']}  [{t['status']}]")
    print("\nVerify: python main.py next-task")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
