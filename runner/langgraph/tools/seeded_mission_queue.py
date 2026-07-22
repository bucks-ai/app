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

CRITICAL SAFETY — the M4b business-mission claim gate (``fetch_next_queued_mission``):
a ``runner_target: "business"`` mission (created via the app's Execute button)
may only be claimed when ALL of the following hold:

  1. ``BUSINESS_EXECUTION_ENABLED=true`` (``cfg.business_execution_enabled``).
  2. The mission's business has a fully "configured" sandbox — its
     ``businesses.sandbox_config`` carries all four keys (``repo_full_name``,
     ``github_token_secret_name``, ``vercel_project_id``,
     ``vercel_token_secret_name``), mirroring ``src/lib/sandbox.ts::computeSandboxStatus``.
  3. Both named secrets actually resolve in this runner process's environment.

Any failing condition leaves the mission queued (never claimed, never marked
running) and logs a ``business_mission_blocked`` event naming the failing
condition and, where relevant, which secret name failed to resolve — never a
secret value.
"""
from datetime import datetime, timezone
from typing import Optional

from tools.mission_compiler import _slug
from tools.log_tools import log_event
from tools.foreign_repo_workspace import fetch_business_by_id, resolve_scoped_github_token
from tools.vercel_tools import resolve_scoped_vercel_token

_REQUIRED_SANDBOX_FIELDS = (
    "repo_full_name",
    "github_token_secret_name",
    "vercel_project_id",
    "vercel_token_secret_name",
)


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

def evaluate_business_mission_claim(mission: dict) -> dict:
    """Gate a ``runner_target: "business"`` mission for claiming (M4b).

    Returns ``{"allowed": True}`` or ``{"allowed": False, "reason": ..., ...}``
    where ``reason`` is one of:

      - ``business_execution_disabled`` — ``BUSINESS_EXECUTION_ENABLED`` is not set.
      - ``missing_business_id`` — the mission row carries no ``business_id``.
      - ``business_not_found`` — the business row could not be fetched.
      - ``sandbox_not_configured`` — one or more of the four required
        ``sandbox_config`` fields is missing; ``missing_fields`` names which.
      - ``secret_unresolved`` — a named secret is not set in the runner env;
        ``secret_name`` names which (never the value).

    Never returns or logs a secret value — only field/secret *names*.
    """
    from config import get_config
    cfg = get_config()

    if not cfg.business_execution_enabled:
        return {"allowed": False, "reason": "business_execution_disabled"}

    business_id = mission.get("business_id")
    if not business_id:
        return {"allowed": False, "reason": "missing_business_id"}

    business = fetch_business_by_id(str(business_id))
    if business is None:
        return {"allowed": False, "reason": "business_not_found"}

    sandbox_config = business.get("sandbox_config") or {}
    missing_fields = [
        field for field in _REQUIRED_SANDBOX_FIELDS
        if not str(sandbox_config.get(field) or "").strip()
    ]
    if missing_fields:
        return {"allowed": False, "reason": "sandbox_not_configured", "missing_fields": missing_fields}

    github_secret_name = str(sandbox_config["github_token_secret_name"]).strip()
    github_result = resolve_scoped_github_token(github_secret_name)
    if not github_result["success"]:
        return {"allowed": False, "reason": "secret_unresolved", "secret_name": github_secret_name}

    vercel_secret_name = str(sandbox_config["vercel_token_secret_name"]).strip()
    vercel_result = resolve_scoped_vercel_token(vercel_secret_name)
    if not vercel_result["success"]:
        return {"allowed": False, "reason": "secret_unresolved", "secret_name": vercel_secret_name}

    return {"allowed": True}


def fetch_next_queued_mission() -> Optional[dict]:
    """Return the first claimable queued mission row from Supabase, or None.

    Fetches queued missions ordered by ``created_at`` ascending (oldest
    first) and returns the first one this runner may claim:

      - ``runner_target: "self"`` (or absent/legacy) missions are always
        claimable.
      - ``runner_target: "business"`` missions are claimable only when
        ``evaluate_business_mission_claim`` allows it — see that function's
        docstring for the full M4b gate. A blocked business mission is
        skipped (left queued, untouched) and a ``business_mission_blocked``
        event is logged naming the failing condition; the scan continues to
        the next candidate mission.

    Returns None on any error, or when no candidate is claimable, so the
    caller can fall through gracefully.
    """
    try:
        client = _get_client()
        result = (
            client.table("missions")
            .select("*")
            .eq("status", "queued")
            .order("created_at")
            .limit(20)
            .execute()
        )
        rows = result.data or []
    except Exception as e:
        log_event("seeded_mission_queue_error", {
            "op": "fetch_next_queued_mission",
            "error": str(e),
        })
        return None

    for row in rows:
        target = row.get("runner_target") or "self"
        if target == "self":
            return row
        if target != "business":
            continue

        gate = evaluate_business_mission_claim(row)
        if gate["allowed"]:
            return row

        log_event("business_mission_blocked", {
            "mission_id": row.get("id"),
            "business_id": row.get("business_id"),
            "reason": gate["reason"],
            **({"missing_fields": gate["missing_fields"]} if "missing_fields" in gate else {}),
            **({"secret_name": gate["secret_name"]} if "secret_name" in gate else {}),
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
            "runner_target": mission.get("runner_target", "self"),
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
