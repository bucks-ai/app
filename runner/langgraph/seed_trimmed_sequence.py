"""Reorder the queue into the trimmed post-review sequence (2026-08-08).

Run once:  python seed_trimmed_sequence.py

Adds no new tasks. It reconciles stale statuses, orders the active sequence,
and pushes consciously-deferred work to the BACK of the queue (never deletes
it, never invents a status the integrity checker would reject).

Everything deferred here is documented with a revisit trigger in
docs/DEFERRED-BACKLOG.md. Read that file before adding anything new.

ACTIVE SEQUENCE (rationale):
  1. m4c4-02  finish it — work is already committed at 6e2c77e, nearly free
  2. m4c-06   FIRST of the M4c line: limits-aware pause/resume is the fix for
              the problem that consumed 2026-08-04..08 of founder time
  3. m4c4-04  plan-then-execute — raises first-attempt success for everything
              after it AND cuts the cache-read tokens that dominate cost
  4. m4c-05   environment & deploy ownership — cheap upfront checks that
              prevent expensive mid-run discoveries (same class as the
              package-lock deadlock)
  5. m4c-07   auto-approval — build the SKIP-AND-CONTINUE half only; the
              merge half already works (see DEFERRED-BACKLOG.md §6)
  6. m4c-09   provisioning framework + GitHub/Vercel/Supabase adapters +
              dependency batch-ahead + phone push. Speculative adapters
              (Stripe/AWS/Resend/Twilio/PostHog) deferred — §3 of the doc
  7. m4c-08   roadmap-as-data — kept in sequence by founder decision; see
              DEFERRED-BACKLOG.md §7 for its unmet prerequisite
  8. m4c-10   verification: run a real mission overnight, count founder touches

DEFERRED TO BACK OF QUEUE: m4c4-05 (network pause), m4c0-06 (mission briefing).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import json

# Stale statuses from the pre-m4c4-08 era, when a successful merge was recorded
# as a completion-evidence block.
RECONCILE = {
    "m4c4-01-crash-safe-checkpointing": (
        "complete",
        "Merged as PR 106 (98ff3d7). Gate-blocked by the pre-m4c4-08 path; "
        "reconciled 2026-08-08.",
    ),
    "m4c4-02-failure-context-repair-loop": (
        "queued",
        None,  # real work outstanding: 6e2c77e is committed but never PR'd
    ),
}

ACTIVE_ORDER = [
    "m4c4-02-failure-context-repair-loop",
    "m4c-06-continuous-operation",
    "m4c4-04-plan-then-execute",
    "m4c-05-environment-deploy-ownership",
    "m4c-07-auto-approval-policy",
    "m4c-09-self-provisioning-and-notify",
    "m4c-08-roadmap-as-data",
    "m4c-10-verification-report",
]

# Kept queued (so nothing is lost or given an unknown status) but moved behind
# every active task. Each has a revisit trigger in docs/DEFERRED-BACKLOG.md.
DEFERRED = [
    "m4c4-05-network-pause",
    "m4c0-06-mission-context-briefing",
]


def main() -> int:
    path = Path(__file__).parent / ".runtime" / "tasks.local.json"
    tasks = json.loads(path.read_text())
    by_id = {t.get("id"): t for t in tasks}

    for tid, (status, note) in RECONCILE.items():
        t = by_id.get(tid)
        if t is None:
            print(f"WARNING: {tid} not found")
            continue
        if t.get("status") != status:
            print(f"reconciled: {tid}  {t.get('status')} -> {status}")
            t["status"] = status
            t.pop("retry_not_before", None)
            if note:
                t["completion_note"] = note
        else:
            print(f"already {status}: {tid}")

    for tid in DEFERRED:
        t = by_id.get(tid)
        if t is None:
            print(f"WARNING: {tid} not found")
            continue
        t["deferred_note"] = (
            "Consciously deferred 2026-08-08 — see docs/DEFERRED-BACKLOG.md for "
            "the reason and the trigger to revisit. Status left 'queued' on "
            "purpose; ordering, not status, is what defers it."
        )
        print(f"deferred to back: {tid}")

    missing = [tid for tid in ACTIVE_ORDER if tid not in by_id]
    if missing:
        print("\nWARNING: active-sequence tasks not found in queue:")
        for tid in missing:
            print(f"  - {tid}")

    pool = dict(by_id)
    active = [pool.pop(tid) for tid in ACTIVE_ORDER if tid in pool]
    deferred = [pool.pop(tid) for tid in DEFERRED if tid in pool]
    rest = [t for t in tasks if t.get("id") in pool]

    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(active + rest + deferred, indent=2))
    tmp.replace(path)

    print("\nACTIVE SEQUENCE:")
    for i, t in enumerate(active, 1):
        print(f"  {i}. {t['id']}  [{t['status']}]")
    print("\nDEFERRED (back of queue, see docs/DEFERRED-BACKLOG.md):")
    for t in deferred:
        print(f"  - {t['id']}  [{t['status']}]")
    print("\nVerify: python main.py next-task")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
