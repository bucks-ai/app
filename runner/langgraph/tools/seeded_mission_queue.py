"""Seeded Mission Queue Executor: polls Supabase for queued missions and seeds the local task queue.

When the local task queue is empty and ``SEEDED_MISSION_QUEUE=true``, this
module fetches the first ``queued`` mission from the Supabase ``missions``
table, converts its ``mission_tasks`` rows into runner task dicts, and adds
them to the local queue via ``task_tools.add_task``.

The mission is marked ``running`` in Supabase immediately after seeding so
that concurrent runner instances do not pick up the same mission.

Each seeded task carries two extra fields that are opaque to the main graph
nodes but are read by ``update_logs_and_state`` to sync completion status back
to Supabase:

  seeded_mission_id — Supabase ``missions.id`` UUID
  seeded_task_id    — Supabase ``mission_tasks.id`` UUID

All Supabase calls degrade gracefully when the client is unavailable — the
caller checks ``cfg.has_supabase`` before invoking any function here, but each
function also returns a safe no-op dict on error so callers do not need to
handle exceptions.
"""
from datetime import datetime, timezone
from typing import Optional

from tools.mission_compiler import _slug
from tools.log_tools import log_event


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_client():
    """Return a Supabase client using the service-role key."""
    from config import get_config
    from supabase import create_client
    cfg = get_config()
    return create_client(cfg.supabase_url, cfg.supabase_service_role_key)


# ---------------------------------------------------------------------------
# Read helpers
# ---------------------------------------------------------------------------

def fetch_next_queued_mission() -> Optional[dict]:
    """Return the first queued, self-targeted mission row from Supabase, or None.

    CRITICAL SAFETY: filters on ``runner_target = "self"``. Until M4b lands
    per-business sandboxing, the runner must never claim a mission created
    for a customer business (``runner_target = "business"``, e.g. via the
    app's Execute button) — those must sit visibly queued and untouched.

    Ordered by ``created_at`` ascending so the oldest mission runs first.
    Returns None on any error so the caller can fall through gracefully.
    """
    try:
        client = _get_client()
        result = (
            client.table("missions")
            .select("*")
            .eq("status", "queued")
            .eq("runner_target", "self")
            .order("created_at")
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None
    except Exception as e:
        log_event("seeded_mission_queue_error", {
            "op": "fetch_next_queued_mission",
            "error": str(e),
        })
        return None


def fetch_mission_tasks(mission_id: str) -> list[dict]:
    """Return mission_tasks rows for *mission_id*, ordered by position."""
    try:
        client = _get_client()
        result = (
            client.table("mission_tasks")
            .select("*")
            .eq("mission_id", mission_id)
            .order("position")
            .execute()
        )
        return result.data or []
    except Exception as e:
        log_event("seeded_mission_queue_error", {
            "op": "fetch_mission_tasks",
            "mission_id": mission_id,
            "error": str(e),
        })
        return []


def check_mission_completion(mission_id: str) -> dict:
    """Return ``{"status": "completed"|"failed"|"in_progress"|"unknown"}``.

    Fetches all mission_tasks for *mission_id* and derives the mission status:
      - all rows complete                 → "completed"
      - all rows terminal, ≥1 failed      → "failed"
      - any row still queued/running      → "in_progress"
      - no rows found / error             → "unknown"
    """
    try:
        client = _get_client()
        result = (
            client.table("mission_tasks")
            .select("status")
            .eq("mission_id", mission_id)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return {"status": "unknown"}
        terminal = frozenset({"complete", "failed", "blocked"})
        statuses = [r.get("status", "") for r in rows]
        if any(s not in terminal for s in statuses):
            return {"status": "in_progress"}
        if all(s == "complete" for s in statuses):
            return {"status": "completed"}
        return {"status": "failed"}
    except Exception as e:
        log_event("seeded_mission_queue_error", {
            "op": "check_mission_completion",
            "mission_id": mission_id,
            "error": str(e),
        })
        return {"status": "unknown"}


# ---------------------------------------------------------------------------
# Pure conversion helper
# ---------------------------------------------------------------------------

def seed_tasks_from_mission(mission: dict, mission_tasks: list[dict]) -> list[dict]:
    """Convert Supabase mission + mission_tasks rows into runner task dicts.

    Pure function — no I/O.  The returned dicts are ready for ``add_task()``.
    Each task carries ``seeded_mission_id`` and ``seeded_task_id`` for later
    sync-back to Supabase.
    """
    mission_id = str(mission.get("id", ""))
    mission_name = mission.get("name", "mission")
    mission_slug = _slug(mission_name, max_len=30)
    business_id = mission.get("business_id")
    user_id = mission.get("user_id")
    now = _now_iso()
    tasks: list[dict] = []

    for row in mission_tasks:
        position = row.get("position", len(tasks) + 1)
        title: str = row.get("title") or f"Task {position}"
        title_slug = _slug(title, max_len=30)
        task_type: str = row.get("type") or "general"
        branch: str = row.get("branch") or f"feature/{mission_slug}/{title_slug}"

        # Use the task_id stored in the DB if set, otherwise generate one.
        local_id: str = row.get("task_id") or f"{mission_slug}-{position}"

        task: dict = {
            "id": local_id,
            "title": title,
            "type": task_type,
            "branch": branch,
            "status": "queued",
            "source": "seeded_mission",
            "mission": mission_name,
            "seeded_mission_id": mission_id,
            "seeded_task_id": str(row.get("id", "")),
            "business_id": business_id,
            "user_id": user_id,
            "created_at": now,
        }
        if row.get("preferred_worker"):
            task["preferred_worker"] = row["preferred_worker"]
        if row.get("description"):
            task["description"] = row["description"]

        tasks.append(task)

    return tasks


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------

def mark_mission_running(mission_id: str) -> dict:
    """Set missions.status = 'running' and record started_at."""
    try:
        client = _get_client()
        client.table("missions").update({
            "status": "running",
            "started_at": _now_iso(),
        }).eq("id", mission_id).execute()
        return {"success": True}
    except Exception as e:
        log_event("seeded_mission_queue_error", {
            "op": "mark_mission_running",
            "mission_id": mission_id,
            "error": str(e),
        })
        return {"success": False, "error": str(e)}


def mark_mission_task_complete(seeded_task_id: str, summary: str) -> dict:
    """Set mission_tasks.status = 'complete' and store the summary."""
    try:
        client = _get_client()
        client.table("mission_tasks").update({
            "status": "complete",
            "summary": summary,
            "completed_at": _now_iso(),
        }).eq("id", seeded_task_id).execute()
        return {"success": True}
    except Exception as e:
        log_event("seeded_mission_queue_error", {
            "op": "mark_mission_task_complete",
            "seeded_task_id": seeded_task_id,
            "error": str(e),
        })
        return {"success": False, "error": str(e)}


def mark_mission_task_failed(seeded_task_id: str, error: str) -> dict:
    """Set mission_tasks.status = 'failed' and store the error message."""
    try:
        client = _get_client()
        client.table("mission_tasks").update({
            "status": "failed",
            "error": error,
        }).eq("id", seeded_task_id).execute()
        return {"success": True}
    except Exception as e:
        log_event("seeded_mission_queue_error", {
            "op": "mark_mission_task_failed",
            "seeded_task_id": seeded_task_id,
            "error": str(e),
        })
        return {"success": False, "error": str(e)}


def mark_mission_completed(mission_id: str) -> dict:
    """Set missions.status = 'completed' and record completed_at."""
    try:
        client = _get_client()
        client.table("missions").update({
            "status": "completed",
            "completed_at": _now_iso(),
        }).eq("id", mission_id).execute()
        return {"success": True}
    except Exception as e:
        log_event("seeded_mission_queue_error", {
            "op": "mark_mission_completed",
            "mission_id": mission_id,
            "error": str(e),
        })
        return {"success": False, "error": str(e)}


def mark_mission_failed(mission_id: str) -> dict:
    """Set missions.status = 'failed'."""
    try:
        client = _get_client()
        client.table("missions").update({
            "status": "failed",
        }).eq("id", mission_id).execute()
        return {"success": True}
    except Exception as e:
        log_event("seeded_mission_queue_error", {
            "op": "mark_mission_failed",
            "mission_id": mission_id,
            "error": str(e),
        })
        return {"success": False, "error": str(e)}
