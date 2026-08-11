"""Mission Backlog: roadmap-as-data + auto-seeding and doctrine ingestion.

M4c: the founder approves the whole mission roadmap ONCE. This module:

  (a) Reads the ``mission_backlog`` Supabase table to find the next approved,
      unstarted entry and promotes it into ``missions``/``mission_tasks``.

  (b) Loads ``STRATEGY.md`` from the repo root and returns doctrine context
      for injection into planner prompts (the first of three code paths that
      make the strategy doc executable; the others are M4d and M7.5).

All Supabase calls degrade gracefully — each function returns a safe no-op
dict on error so callers do not need to handle exceptions. The strategy-doc
loader also degrades gracefully (returns ``""`` when the file is absent).
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tools.log_tools import log_event

# Maximum characters of STRATEGY.md injected into planner prompts.
# ~3 kB keeps token cost negligible while covering the doctrine core.
_STRATEGY_MAX_CHARS = 3_000

# Sections of STRATEGY.md most relevant to planning decisions.
# Anchors match the heading lines in the current doc (case-insensitive prefix
# match); when section extraction fails the full doc is truncated instead.
_STRATEGY_RELEVANT_SECTIONS = (
    "## 1. THE ONE-LINE THESIS",
    "## 2. THE CONVENIENCE DOCTRINE",
    "## 6. MARKET-SELECTION",
    "## 7. IDEAS LEDGER",
    "## 8. THE ROAD TO SUCCESS",
)


# ---------------------------------------------------------------------------
# Strategy-doc helpers (Part C — doctrine ingestion)
# ---------------------------------------------------------------------------

def load_strategy_doc(repo_path: str, max_chars: int = _STRATEGY_MAX_CHARS) -> str:
    """Load and return a doctrine excerpt from STRATEGY.md.

    Returns ``""`` if the file is absent or unreadable — the caller treats
    an empty string as "no context available" and proceeds normally.

    The excerpt is trimmed to *max_chars* characters to keep token cost
    negligible (≈750 tokens at the default 3 kB).
    """
    path = Path(repo_path) / "STRATEGY.md"
    if not path.exists():
        return ""
    try:
        text = path.read_text()
    except OSError:
        return ""

    excerpt = _extract_relevant_sections(text, max_chars)
    return excerpt


def _extract_relevant_sections(text: str, max_chars: int) -> str:
    """Extract the highest-signal sections from STRATEGY.md.

    Walks the doc and collects the paragraphs under each heading in
    _STRATEGY_RELEVANT_SECTIONS.  Falls back to a plain head-truncation
    when no sections are found (e.g. the doc format changed).
    """
    lines = text.splitlines(keepends=True)
    sections: list[str] = []

    # Build a map: heading index → section body
    current_heading: Optional[str] = None
    body_lines: list[str] = []

    def _flush():
        if current_heading is not None:
            body = "".join(body_lines).rstrip()
            if body:
                sections.append(f"{current_heading}\n{body}")

    for line in lines:
        stripped = line.rstrip()
        # Check if this line is one of our target headings
        is_target = any(
            stripped.lower().startswith(h.lower())
            for h in _STRATEGY_RELEVANT_SECTIONS
        )
        # Check if this line is ANY level-2 heading (new section boundary)
        is_section_boundary = stripped.startswith("## ")

        if is_target:
            _flush()
            body_lines = []
            current_heading = stripped
        elif is_section_boundary and current_heading is not None:
            _flush()
            current_heading = None
            body_lines = []
        elif current_heading is not None:
            body_lines.append(line)

    _flush()

    if not sections:
        # No recognised sections — return a plain head-truncation
        return text[:max_chars]

    result = "\n\n".join(sections)
    return result[:max_chars]


# ---------------------------------------------------------------------------
# Supabase client helper
# ---------------------------------------------------------------------------

def _get_client():
    from config import get_config
    from supabase import create_client
    cfg = get_config()
    return create_client(cfg.supabase_url, cfg.supabase_service_role_key)


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Read helpers (Part A — fetch from backlog)
# ---------------------------------------------------------------------------

def fetch_next_approved_backlog_entry() -> Optional[dict]:
    """Return the next approved, unstarted mission_backlog row, or None.

    Fetches the single row with the lowest ``position`` where
    ``approved = true`` and ``seeded_at IS NULL``.

    Returns ``None`` on any error or when no eligible entry exists.
    """
    try:
        client = _get_client()
        result = (
            client.table("mission_backlog")
            .select("*")
            .eq("approved", True)
            .is_("seeded_at", "null")
            .order("position")
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None
    except Exception as exc:
        log_event("mission_backlog_error", {
            "op": "fetch_next_approved_backlog_entry",
            "error": str(exc),
        })
        return None


def fetch_backlog_tasks(backlog_id: str) -> list[dict]:
    """Return mission_backlog_tasks rows for *backlog_id*, ordered by position."""
    try:
        client = _get_client()
        result = (
            client.table("mission_backlog_tasks")
            .select("*")
            .eq("backlog_id", backlog_id)
            .order("position")
            .execute()
        )
        return result.data or []
    except Exception as exc:
        log_event("mission_backlog_error", {
            "op": "fetch_backlog_tasks",
            "backlog_id": backlog_id,
            "error": str(exc),
        })
        return []


# ---------------------------------------------------------------------------
# Write helpers (Part B — seed and chain)
# ---------------------------------------------------------------------------

def seed_backlog_entry_to_missions(entry: dict, tasks: list[dict]) -> dict:
    """Create a mission row + mission_tasks rows from a backlog entry.

    Returns ``{"success": True, "mission_id": str}`` or
    ``{"success": False, "error": str}``.

    The created mission row has ``status = "queued"`` and
    ``runner_target = "self"`` so ``fetch_next_queued_mission`` picks it up
    immediately on the next seeding cycle.
    """
    if not tasks:
        return {"success": False, "error": "backlog entry has no tasks"}

    try:
        client = _get_client()
        now = _now_iso()

        # Create the missions row
        mission_row = {
            "name": entry.get("name", ""),
            "goal": entry.get("goal") or "",
            "status": "queued",
            "runner_target": "self",
            "created_at": now,
        }
        mission_result = client.table("missions").insert(mission_row).execute()
        mission_rows = mission_result.data or []
        if not mission_rows:
            return {"success": False, "error": "missions insert returned no rows"}
        mission_id = str(mission_rows[0]["id"])

        # Create mission_tasks rows
        task_rows = []
        for i, t in enumerate(tasks, 1):
            task_rows.append({
                "mission_id": mission_id,
                "position": t.get("position", i),
                "title": t.get("title", f"Task {i}"),
                "type": t.get("type", "general"),
                "branch": t.get("branch") or "",
                "preferred_worker": t.get("preferred_worker") or "",
                "description": t.get("description") or "",
                "status": "queued",
                "created_at": now,
            })
        client.table("mission_tasks").insert(task_rows).execute()

        return {"success": True, "mission_id": mission_id}

    except Exception as exc:
        log_event("mission_backlog_error", {
            "op": "seed_backlog_entry_to_missions",
            "backlog_id": str(entry.get("id", "")),
            "error": str(exc),
        })
        return {"success": False, "error": str(exc)}


def mark_backlog_entry_seeded(backlog_id: str, mission_id: str) -> dict:
    """Set mission_backlog.seeded_at = now() and record the created mission_id."""
    try:
        client = _get_client()
        client.table("mission_backlog").update({
            "seeded_at": _now_iso(),
            "mission_id": mission_id,
            "updated_at": _now_iso(),
        }).eq("id", backlog_id).execute()
        return {"success": True}
    except Exception as exc:
        log_event("mission_backlog_error", {
            "op": "mark_backlog_entry_seeded",
            "backlog_id": backlog_id,
            "mission_id": mission_id,
            "error": str(exc),
        })
        return {"success": False, "error": str(exc)}


# ---------------------------------------------------------------------------
# High-level entry point: auto-seed next backlog entry
# ---------------------------------------------------------------------------

def auto_seed_next_backlog_entry() -> dict:
    """Fetch the next approved backlog entry and seed it into missions.

    Called by the graph after a mission completes cleanly. Returns a result
    dict with keys ``seeded`` (bool), ``backlog_id``, ``mission_id``, and
    ``error`` (on failure).

    Degrades silently — any error is logged and ``{"seeded": False}`` is
    returned so the graph can continue without a stop.
    """
    entry = fetch_next_approved_backlog_entry()
    if not entry:
        return {"seeded": False}

    backlog_id = str(entry.get("id", ""))
    tasks = fetch_backlog_tasks(backlog_id)

    seed_result = seed_backlog_entry_to_missions(entry, tasks)
    if not seed_result.get("success"):
        log_event("mission_backlog_seed_failed", {
            "backlog_id": backlog_id,
            "error": seed_result.get("error", "unknown"),
        })
        return {"seeded": False, "backlog_id": backlog_id, "error": seed_result.get("error")}

    mission_id = seed_result["mission_id"]
    mark_backlog_entry_seeded(backlog_id, mission_id)

    log_event("mission_backlog_auto_seeded", {
        "backlog_id": backlog_id,
        "backlog_name": entry.get("name", ""),
        "backlog_position": entry.get("position"),
        "mission_id": mission_id,
        "task_count": len(tasks),
    })

    return {
        "seeded": True,
        "backlog_id": backlog_id,
        "mission_id": mission_id,
        "name": entry.get("name", ""),
    }
