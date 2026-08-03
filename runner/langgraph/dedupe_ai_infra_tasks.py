"""One-off cleanup: de-duplicate the triple-seeded "Execute: AI Infra" tasks.

Problem this fixes
------------------
The AI Infra business mission was seeded THREE times across relaunches, because
nothing guarded against re-seeding a mission whose tasks were not all terminal.
That produced three sets of tasks with COLLIDING ids (ai-infra-1..5 x3), where
the sets don't even agree on content:

  * Set 1 (stale)  — compiled by the OLD mission compiler: "Build MVP",
                     "Set up infrastructure", "Execute go-to-market"
  * Sets 2 & 3     — compiled by the NEW m4b-07 fresh-repo compiler:
                     "Build landing page section", "Wire analytics stub",
                     "Deploy the scaffolded app", + GTM + risk mitigation

Colliding ids make status writes ambiguous (which "ai-infra-1" does an update
hit?), and the duplicates are why the loop kept finding nothing claimable.

What this script does
---------------------
  1. Backs up tasks.local.json next to itself (.bak.<timestamp>).
  2. Groups AI-Infra seeded tasks by TITLE (the only reliable key here).
  3. Keeps exactly ONE task per title:
       - if any copy is "complete", keep that one as complete
       - otherwise keep one copy, and reset a stranded "running" -> "queued"
  4. Retires the two stale OLD-compiler titles as "complete" (they already
      ran; marking rather than deleting so nothing is silently lost, and so
      they never re-run the wrong work).
  5. Reassigns unique ids (ai-infra-01..NN) so status writes are unambiguous.
  6. Prints a before/after report and writes the file back.

Idempotent: running it twice is harmless.

Run:  cd ~/bucks-ai/runner/langgraph && python dedupe_ai_infra_tasks.py
"""
import json
import shutil
from datetime import datetime
from pathlib import Path

TASKS_PATH = Path(__file__).parent / ".runtime" / "tasks.local.json"

# Titles produced by the OLD compiler, superseded by the m4b-07 fresh-repo
# compiler output. Retire (mark complete), never re-run.
STALE_TITLES = {
    "Build MVP: Automated security assessment tool",
    "Set up infrastructure: Node.js, React, AWS for cloud infrastructure",
}


def is_ai_infra(task: dict) -> bool:
    return str(task.get("id", "")).startswith("ai-infra-") or "AI Infra" in str(
        task.get("mission", "")
    )


def main() -> None:
    if not TASKS_PATH.exists():
        raise SystemExit(f"not found: {TASKS_PATH}")

    tasks = json.loads(TASKS_PATH.read_text())
    if not isinstance(tasks, list):
        raise SystemExit("unexpected tasks.local.json shape (expected a list)")

    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup = TASKS_PATH.with_suffix(f".json.bak.{stamp}")
    shutil.copy2(TASKS_PATH, backup)
    print(f"backup written: {backup.name}\n")

    others = [t for t in tasks if not is_ai_infra(t)]
    ai_infra = [t for t in tasks if is_ai_infra(t)]

    print(f"BEFORE: {len(ai_infra)} AI-Infra tasks, {len(others)} other tasks")
    for t in ai_infra:
        print(f"   [{t.get('status'):9}] {t.get('id'):14} {t.get('title')}")

    # ---- collapse by title -------------------------------------------------
    by_title: dict[str, dict] = {}
    for t in ai_infra:
        title = str(t.get("title", ""))
        keep = by_title.get(title)
        if keep is None:
            by_title[title] = dict(t)
            continue
        # prefer whichever copy is already complete
        if t.get("status") == "complete" and keep.get("status") != "complete":
            by_title[title] = dict(t)

    # ---- normalise status + unique ids -------------------------------------
    deduped: list[dict] = []
    for index, (title, task) in enumerate(sorted(by_title.items()), start=1):
        if title in STALE_TITLES:
            task["status"] = "complete"
            task["dedupe_note"] = "retired: superseded by m4b-07 fresh-repo compiler output"
        elif task.get("status") == "running":
            # stranded by an interrupted run — nothing owns it, so requeue
            task["status"] = "queued"
            task["dedupe_note"] = "requeued: orphaned 'running' with no live worker"
        task["id"] = f"ai-infra-{index:02d}"
        deduped.append(task)

    print(f"\nAFTER: {len(deduped)} AI-Infra tasks (was {len(ai_infra)})")
    for t in deduped:
        note = f"  <- {t['dedupe_note']}" if "dedupe_note" in t else ""
        print(f"   [{t.get('status'):9}] {t.get('id'):14} {t.get('title')}{note}")

    queued = [t for t in deduped if t.get("status") == "queued"]
    print(f"\n{len(queued)} task(s) queued and claimable on next run:")
    for t in queued:
        print(f"   - {t['id']}  {t['title']}")

    TASKS_PATH.write_text(json.dumps(others + deduped, indent=2))
    print(f"\nwrote {TASKS_PATH.name}")


if __name__ == "__main__":
    main()
