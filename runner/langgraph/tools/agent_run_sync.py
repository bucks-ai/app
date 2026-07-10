"""Agent Runs sync: stream seeded-mission task lifecycle into Supabase ``agent_runs``.

The app's Operating Team UI (src/lib/agents/{registry,runs,status}.ts) reads the
``agent_runs`` table keyed by the 21 MVP business agents (blueprint, repository,
scaffold, ...). Runner-driven mission tasks are not performed by any of those
business agents — they are the runner's own "operating team" work, modelled on
the 11-brain taxonomy from BUCKS_AI_MASTER_ANALYSIS.md (Command Center,
Product, Engineering, Ops, ...). ``TASK_TYPE_AGENT_MAP`` maps a mission task's
``type`` to the closest brain so a run row can still be written; ``agent_id`` is
a plain TEXT column with no FK/CHECK constraint, so this does not require any
change to the app-side AGENT_REGISTRY.

All functions degrade silently (return ``None`` / ``{"success": False}``)
when Supabase is not configured, the task is missing business/user ids, or
the request fails — callers do not need to check ``cfg.has_supabase`` first.
"""
from datetime import datetime, timezone
from typing import Optional

from tools.log_tools import log_event


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _get_client():
    """Return a Supabase client using the service-role key."""
    from config import get_config
    from supabase import create_client
    cfg = get_config()
    return create_client(cfg.supabase_url, cfg.supabase_service_role_key)


def _has_supabase() -> bool:
    from config import get_config
    return get_config().has_supabase


# ---------------------------------------------------------------------------
# Task type -> agent identity mapping
# ---------------------------------------------------------------------------
# node_id uses the existing "orchestration" AgentNodeId (types/agents.ts) —
# the closest fit for runner-monitored execution — until the brain taxonomy
# gets its own node grouping in the app.

_ORCHESTRATION_NODE = "orchestration"

DEFAULT_AGENT_ID = "command_center_brain"

TASK_TYPE_AGENT_MAP: dict[str, str] = {
    "backend": "engineering_brain",
    "infra": "engineering_brain",
    "test": "engineering_brain",
    "frontend": "product_brain",
    "ui": "product_brain",
    "design": "product_brain",
    "polish": "product_brain",
    "docs": "ops_brain",
    "general": DEFAULT_AGENT_ID,
}


def resolve_agent_identity(task_type: Optional[str]) -> tuple[str, str]:
    """Map a mission task ``type`` to an ``(agent_id, node_id)`` pair.

    Pure function — no I/O. Unknown/missing types fall back to
    ``DEFAULT_AGENT_ID`` under the orchestration node.
    """
    agent_id = TASK_TYPE_AGENT_MAP.get((task_type or "").lower(), DEFAULT_AGENT_ID)
    return agent_id, _ORCHESTRATION_NODE


# ---------------------------------------------------------------------------
# Write helpers
# ---------------------------------------------------------------------------

def start_agent_run(task: dict) -> Optional[str]:
    """Insert a ``running`` agent_runs row for a seeded-mission task.

    Returns the new row's ``id`` on success, or ``None`` when Supabase is not
    configured, the task lacks ``business_id``/``user_id``, or the insert
    fails for any reason — never raises.
    """
    if not _has_supabase():
        return None

    business_id = task.get("business_id")
    user_id = task.get("user_id")
    if not business_id or not user_id:
        return None

    agent_id, node_id = resolve_agent_identity(task.get("type"))

    try:
        client = _get_client()
        result = (
            client.table("agent_runs")
            .insert({
                "business_id": business_id,
                "user_id": user_id,
                "agent_id": agent_id,
                "node_id": node_id,
                "title": task.get("title") or task.get("id") or "Runner task",
                "status": "running",
                "source": "workflow",
                "input": {
                    "task_id": task.get("id"),
                    "task_type": task.get("type"),
                    "branch": task.get("branch"),
                    "mission": task.get("mission"),
                    "seeded_mission_id": task.get("seeded_mission_id"),
                    "seeded_task_id": task.get("seeded_task_id"),
                },
                "started_at": _now_iso(),
            })
            .execute()
        )
        rows = result.data or []
        return str(rows[0]["id"]) if rows else None
    except Exception as e:
        log_event("agent_run_sync_error", {
            "op": "start_agent_run",
            "task_id": task.get("id"),
            "error": str(e),
        })
        return None


def _finish_agent_run(
    run_id: Optional[str],
    *,
    status: str,
    summary: str,
    error: Optional[dict] = None,
    output: Optional[dict] = None,
    cost_usd: Optional[float] = None,
    duration_seconds: Optional[float] = None,
) -> dict:
    if not run_id or not _has_supabase():
        return {"success": False}

    update: dict = {
        "status": status,
        "summary": summary,
        "completed_at": _now_iso(),
    }
    if output is not None:
        update["output"] = output
    if error is not None:
        update["error"] = error
    if cost_usd is not None:
        update["cost_usd"] = cost_usd
    if duration_seconds is not None:
        update["duration_seconds"] = duration_seconds

    try:
        client = _get_client()
        client.table("agent_runs").update(update).eq("id", run_id).execute()
        return {"success": True}
    except Exception as e:
        log_event("agent_run_sync_error", {
            "op": f"_finish_agent_run:{status}",
            "run_id": run_id,
            "error": str(e),
        })
        return {"success": False, "error": str(e)}


def complete_agent_run(
    run_id: Optional[str],
    summary: str,
    output: Optional[dict] = None,
    cost_usd: Optional[float] = None,
    duration_seconds: Optional[float] = None,
) -> dict:
    """Mark an agent_runs row ``completed`` with the worker summary digest."""
    return _finish_agent_run(
        run_id,
        status="completed",
        summary=summary,
        output=output,
        cost_usd=cost_usd,
        duration_seconds=duration_seconds,
    )


def fail_agent_run(
    run_id: Optional[str],
    error_message: str,
    output: Optional[dict] = None,
    cost_usd: Optional[float] = None,
    duration_seconds: Optional[float] = None,
) -> dict:
    """Mark an agent_runs row ``failed`` with a structured error payload."""
    return _finish_agent_run(
        run_id,
        status="failed",
        summary=error_message,
        error={"code": "worker_failed", "message": error_message},
        output=output,
        cost_usd=cost_usd,
        duration_seconds=duration_seconds,
    )
