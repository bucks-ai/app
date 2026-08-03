"""Queue health report — ``python main.py doctor`` (M4c.0).

The founder hand-edited ``.runtime/tasks.local.json`` at least five times
during M4b to recover from states the runner created and could not exit. Every
one of those edits started the same way: opening a 100-entry JSON file and
reading it by eye to work out what was wrong. This is that step, automated.

``doctor`` answers four questions:

  1. What is in the queue?      — counts by status
  2. What is stuck?             — ``running`` rows with no live session owner
  3. What is malformed?         — schema violations, duplicate ids, stale
                                  retry windows on finished tasks
  4. Does it match Supabase?    — for seeded missions, where the local rows and
                                  the ``mission_tasks`` rows disagree

With ``--fix`` it applies exactly the auto-repairs that ``load_tasks`` applies,
plus the cosmetic field defaults that load-time repair deliberately withholds
(see ``tools/task_schema.apply_field_defaults``). Nothing here writes to
Supabase: divergence is *reported*, never resolved. Reconciling the two sides
is m4c-03's job, and doing it from a diagnostic command would make a read-only
health check silently authoritative over the database.
"""
from __future__ import annotations

import socket
from collections import Counter
from datetime import datetime
from typing import Callable, Optional

from tools.task_schema import (
    ORPHAN_GRACE_SECONDS,
    apply_field_defaults,
    classify_running_tasks,
    repair_tasks,
    validate_tasks,
)

#: Local statuses that mean "the runner is finished with this task", used to
#: judge whether a Supabase mission_tasks row has fallen behind.
_LOCAL_TERMINAL = frozenset({"complete", "failed"})


def diff_against_mission_tasks(tasks: list, mission_rows: list) -> list[dict]:
    """Compare seeded local tasks against their Supabase ``mission_tasks`` rows.

    Pure — the caller supplies both sides. Returns one dict per divergence:

      - ``status_mismatch``     — both sides exist and disagree on status
      - ``missing_in_supabase`` — a local row names a ``seeded_task_id`` that
                                  has no matching ``mission_tasks`` row
      - ``missing_locally``     — a ``mission_tasks`` row for a mission the
                                  local queue is executing has no local task
    """
    by_seeded_id = {
        str(row.get("id")): row for row in mission_rows if row.get("id") is not None
    }
    local_by_seeded_id = {
        t["seeded_task_id"]: t
        for t in tasks
        if isinstance(t, dict) and t.get("seeded_task_id")
    }

    divergences: list[dict] = []
    for seeded_id, task in sorted(local_by_seeded_id.items()):
        row = by_seeded_id.get(seeded_id)
        if row is None:
            divergences.append({
                "kind": "missing_in_supabase",
                "task_id": task.get("id"),
                "seeded_task_id": seeded_id,
                "local_status": task.get("status"),
                "remote_status": None,
                "detail": "local task references a mission_tasks row that no longer exists",
            })
            continue
        local_status = task.get("status")
        remote_status = row.get("status")
        if local_status != remote_status:
            divergences.append({
                "kind": "status_mismatch",
                "task_id": task.get("id"),
                "seeded_task_id": seeded_id,
                "local_status": local_status,
                "remote_status": remote_status,
                "detail": (
                    f"local '{local_status}' vs Supabase '{remote_status}'"
                    + (
                        " — the sync-back to Supabase did not land"
                        if local_status in _LOCAL_TERMINAL
                        else ""
                    )
                ),
            })

    missions_in_play = {
        t.get("seeded_mission_id")
        for t in tasks
        if isinstance(t, dict) and t.get("seeded_mission_id")
    }
    for seeded_id, row in sorted(by_seeded_id.items()):
        if seeded_id in local_by_seeded_id:
            continue
        if str(row.get("mission_id")) not in missions_in_play:
            continue
        divergences.append({
            "kind": "missing_locally",
            "task_id": row.get("task_id"),
            "seeded_task_id": seeded_id,
            "local_status": None,
            "remote_status": row.get("status"),
            "detail": "Supabase has a mission task the local queue never seeded",
        })

    return divergences


def _fetch_mission_divergence(tasks: list) -> dict:
    """Fetch ``mission_tasks`` for every seeded mission in the local queue.

    Degrades to ``{"checked": False, ...}`` whenever Supabase is unconfigured
    or unreachable — a health check must still be useful offline.
    """
    mission_ids = sorted({
        str(t["seeded_mission_id"])
        for t in tasks
        if isinstance(t, dict) and t.get("seeded_mission_id")
    })
    if not mission_ids:
        return {"checked": False, "reason": "no_seeded_missions", "missions": [], "divergences": []}

    try:
        from config import get_config
        if not get_config().has_supabase:
            return {
                "checked": False,
                "reason": "supabase_not_configured",
                "missions": mission_ids,
                "divergences": [],
            }
        from tools.seeded_mission_queue import fetch_mission_tasks
    except Exception as exc:  # pragma: no cover - import/config failure path
        return {
            "checked": False,
            "reason": f"supabase_unavailable: {exc}",
            "missions": mission_ids,
            "divergences": [],
        }

    rows: list = []
    for mission_id in mission_ids:
        rows.extend(fetch_mission_tasks(mission_id) or [])
    if not rows:
        return {
            "checked": False,
            "reason": "no_mission_tasks_returned",
            "missions": mission_ids,
            "divergences": [],
        }
    return {
        "checked": True,
        "reason": None,
        "missions": mission_ids,
        "divergences": diff_against_mission_tasks(tasks, rows),
    }


def build_report(
    tasks: list,
    *,
    live_task_ids=(),
    now: Optional[datetime] = None,
    host: Optional[str] = None,
    pid_alive: Optional[Callable[[int], bool]] = None,
    grace_seconds: int = ORPHAN_GRACE_SECONDS,
    supabase: Optional[dict] = None,
) -> dict:
    """Build the full health report for *tasks*. Pure; no I/O of its own."""
    tasks = tasks if isinstance(tasks, list) else []
    running = classify_running_tasks(
        tasks,
        live_task_ids=live_task_ids,
        now=now,
        host=host,
        pid_alive=pid_alive,
        grace_seconds=grace_seconds,
    )
    violations = validate_tasks(tasks)
    duplicates = [v for v in violations if v["kind"].startswith("duplicate_")]
    counts = Counter(
        t.get("status") if isinstance(t, dict) and isinstance(t.get("status"), str) else "<none>"
        for t in tasks
    )
    supabase = supabase if supabase is not None else {
        "checked": False, "reason": "not_requested", "missions": [], "divergences": []
    }

    return {
        "task_count": len(tasks),
        "counts_by_status": dict(sorted(counts.items())),
        "orphans": running["orphaned"],
        "unverifiable_running": running["unverifiable"],
        "live_running": running["live"],
        "duplicates": duplicates,
        "violations": violations,
        "supabase": supabase,
        "healthy": not (running["orphaned"] or violations or supabase.get("divergences")),
    }


def format_report(report: dict) -> str:
    """Render the report as the text the founder reads instead of the JSON."""
    lines = ["=== Task queue health ===", ""]
    lines.append(f"  Tasks: {report['task_count']}")
    for status, count in report["counts_by_status"].items():
        lines.append(f"    {status:<10} {count}")
    lines.append("")

    orphans = report["orphans"]
    if orphans:
        lines.append(f"  ✗ Orphaned 'running' tasks ({len(orphans)}) — no live session owns these:")
        for orphan in orphans:
            lines.append(
                f"      {orphan['task_id']}  ({orphan['reason']}, last updated "
                f"{orphan.get('updated_at') or 'never'})"
            )
    else:
        lines.append("  ✓ No orphaned 'running' tasks")

    unverifiable = report["unverifiable_running"]
    if unverifiable:
        lines.append(
            f"  • {len(unverifiable)} 'running' task(s) could not be verified either way "
            "(left untouched):"
        )
        for row in unverifiable:
            lines.append(f"      {row['task_id']}  ({row['reason']})")

    duplicates = report["duplicates"]
    if duplicates:
        lines.append(f"  ✗ Duplicates ({len(duplicates)}):")
        for dup in duplicates:
            lines.append(f"      {dup['task_id']}: {dup['detail']}")
    else:
        lines.append("  ✓ No duplicate ids")

    other = [v for v in report["violations"] if not v["kind"].startswith("duplicate_")]
    if other:
        lines.append(f"  ✗ Invariant violations ({len(other)}):")
        for violation in other:
            lines.append(f"      {violation['task_id']}: {violation['detail']}")
    else:
        lines.append("  ✓ No schema or invariant violations")

    supabase = report["supabase"]
    if not supabase.get("checked"):
        lines.append(f"  • Supabase divergence not checked ({supabase.get('reason')})")
    elif supabase["divergences"]:
        lines.append(f"  ✗ Supabase divergence ({len(supabase['divergences'])}):")
        for div in supabase["divergences"]:
            lines.append(f"      [{div['kind']}] {div['task_id']}: {div['detail']}")
    else:
        lines.append(
            f"  ✓ Local queue matches mission_tasks for {len(supabase['missions'])} mission(s)"
        )

    lines.append("")
    if report["healthy"]:
        lines.append("  Queue is healthy.")
    else:
        lines.append("  Run `python main.py doctor --fix` to repair what can be repaired")
        lines.append("  automatically. Stop the loop first so nothing is repaired out from")
        lines.append("  under a live run.")
    return "\n".join(lines)


def format_repairs(repairs: list) -> str:
    """Render what ``--fix`` actually changed, grouped by repair kind."""
    if not repairs:
        return "  Nothing to repair."
    lines = [f"  Applied {len(repairs)} repair(s):"]
    for kind in sorted({r["kind"] for r in repairs}):
        matching = [r for r in repairs if r["kind"] == kind]
        lines.append(f"    {kind} ({len(matching)}):")
        for repair in matching:
            lines.append(f"      {repair.get('task_id')}: {repair.get('detail')}")
    return "\n".join(lines)


def run_doctor(*, fix: bool = False, check_supabase: bool = True) -> dict:
    """Load the queue as it really is, report on it, and optionally repair it.

    Reads with ``repair=False`` so the report describes the file on disk rather
    than a queue that load-time repair has already quietly fixed. Returns
    ``{"report", "repairs", "text"}``.
    """
    from tools.task_tools import (
        _log,
        _now,
        _persist_queue,
        live_task_ids,
        load_tasks,
        _pid_alive,
    )

    tasks = load_tasks(repair=False)
    if not isinstance(tasks, list):
        tasks = []

    host = socket.gethostname()
    live_ids = live_task_ids()
    supabase = _fetch_mission_divergence(tasks) if check_supabase else None
    report = build_report(
        tasks,
        live_task_ids=live_ids,
        host=host,
        pid_alive=_pid_alive,
        supabase=supabase,
    )

    repairs: list = []
    if fix:
        now_iso = _now()
        repaired, repairs = repair_tasks(
            tasks,
            live_task_ids=live_ids,
            host=host,
            pid_alive=_pid_alive,
            now_iso=now_iso,
        )
        repaired, defaults = apply_field_defaults(repaired, now_iso=now_iso)
        repairs = repairs + defaults
        if repairs:
            for repair in repairs:
                _log("task_queue_repaired", {**repair, "source": "doctor_fix"}, repair.get("task_id"))
            _persist_queue(repaired)
        report = build_report(
            repaired,
            live_task_ids=live_ids,
            host=host,
            pid_alive=_pid_alive,
            supabase=supabase,
        )

    text = format_report(report)
    if fix:
        text = f"{text}\n\n{format_repairs(repairs)}"
    return {"report": report, "repairs": repairs, "text": text}
