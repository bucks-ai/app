"""Mission Planner: cheap pre-execution planning pass for conflict and duplicate detection.

Runs once per mission after seeding but before any task is dispatched. For each
unplanned task, a cheap LLM call produces a structured plan predicting:
  (a) files it expects to create or modify
  (b) a two-or-three sentence approach
  (c) whether the deliverable already exists in the codebase, with the path if so
  (d) any task it depends on landing first

Plans are persisted to .runtime/plans/<task_id>.json for two purposes:
  1. Conflict detection: tasks sharing expected files are ordered sequentially and
     the queue is rewritten so each starts from the merged predecessor.
  2. Scope enforcement: M4c.5 compares the expected-file list against the actual
     diff to detect scope creep.

DEGRADATION: if planning fails or is disabled (MISSION_PLANNING=false), execution
proceeds exactly as it does today. No plan ≠ blocked task.

Config flags (three-place rule: config.py + README + tests):
  MISSION_PLANNING         — master toggle; default true
  MISSION_PLANNING_MAX_FILES — oversized threshold; default 10
  MISSION_PLANNING_MODEL   — cheap Anthropic model; default claude-haiku-4-5-20251001
"""
import json
import os
from collections import deque
from pathlib import Path
from typing import Optional

from tools.log_tools import log_event

_PLANS_DIR = Path(__file__).parent.parent / ".runtime" / "plans"

_MAX_PLAN_TOKENS = 512
_MAX_EXPECTED_FILES = 20  # hard cap per plan before right-sizing flag

_PLANNING_PROMPT = """\
You are a senior software engineer doing a quick pre-task planning pass.
{strategy_context}
Task ID: {task_id}
Title: {title}
Type: {task_type}
Branch: {branch}
Description: {description}

Peer task IDs in this mission: {peer_task_ids}

Return ONLY a JSON object — no explanation, no markdown fences:
{{
  "expected_files": ["path/to/file1.py", "path/to/file2.py"],
  "approach": "Two or three sentences on how you would implement this.",
  "deliverable_exists": false,
  "deliverable_path": null,
  "depends_on": []
}}

Field rules:
- expected_files: file paths relative to repo root that this task will CREATE or MODIFY; max {max_files}; do not list directories
- approach: 2–3 sentences only; ensure the approach is consistent with bucks.ai strategy doctrine (convenience, minimal interruption, ownership)
- deliverable_exists: true if the main thing being built already exists in the codebase
- deliverable_path: relative path to existing deliverable, or null
- depends_on: list of peer task IDs that must land before this task starts; empty list if none

JSON only:\
"""

_STRATEGY_CONTEXT_TEMPLATE = """\

## bucks.ai Strategy Doctrine (read before planning)
The following is an excerpt from STRATEGY.md. Plans must be doctrine-shaped.

{strategy_text}

"""


# ── Plan persistence ──────────────────────────────────────────────────────────

def _plan_path(task_id: str) -> Path:
    return _PLANS_DIR / f"{task_id}.json"


def save_plan(task_id: str, plan: dict) -> None:
    """Persist *plan* to .runtime/plans/<task_id>.json (atomic write)."""
    _PLANS_DIR.mkdir(parents=True, exist_ok=True)
    path = _plan_path(task_id)
    tmp = path.with_suffix(".json.tmp")
    try:
        tmp.write_text(json.dumps(plan, indent=2))
        tmp.replace(path)
    finally:
        if tmp.exists():
            tmp.unlink(missing_ok=True)


def load_plan(task_id: str) -> Optional[dict]:
    """Load a persisted plan, or None if absent or unreadable."""
    path = _plan_path(task_id)
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text())
    except Exception:
        return None


def load_all_plans(task_ids: list) -> dict:
    """Load plans for all *task_ids*; missing plans are omitted."""
    return {tid: p for tid in task_ids if (p := load_plan(tid)) is not None}


# ── Pure analysis functions (no I/O, testable without mocks) ─────────────────

def detect_conflicts(tasks: list, plans: dict) -> list:
    """Return conflict records for tasks whose expected-file sets intersect.

    Each record: {"task_ids": [id_a, id_b], "shared_files": [...]}.
    Only considers tasks that have a plan with at least one expected file.
    Pairs are reported with the task that appears earlier in *tasks* listed first.
    """
    task_file_sets = []
    for task in tasks:
        tid = task.get("id", "")
        files = set(plans.get(tid, {}).get("expected_files") or [])
        if files:
            task_file_sets.append((tid, files))

    conflicts = []
    seen: set = set()
    for i, (id_a, files_a) in enumerate(task_file_sets):
        for id_b, files_b in task_file_sets[i + 1:]:
            key = (id_a, id_b)
            if key in seen:
                continue
            seen.add(key)
            shared = sorted(files_a & files_b)
            if shared:
                conflicts.append({"task_ids": [id_a, id_b], "shared_files": shared})
    return conflicts


def detect_duplicates(tasks: list, plans: dict, repo_path: str) -> list:
    """Return duplicate records for tasks whose deliverable already exists.

    Two signal sources:
    1. The plan's "deliverable_exists" field (LLM-reported).
    2. A cheap ``Path.exists()`` check on "deliverable_path" relative to repo_path.
    """
    duplicates = []
    for task in tasks:
        tid = task.get("id", "")
        plan = plans.get(tid, {})

        if plan.get("deliverable_exists"):
            duplicates.append({
                "task_id": tid,
                "task_title": task.get("title", ""),
                "deliverable_path": plan.get("deliverable_path"),
                "evidence": "plan_reported",
            })
            continue

        dpath = plan.get("deliverable_path")
        if dpath and (Path(repo_path) / dpath).exists():
            duplicates.append({
                "task_id": tid,
                "task_title": task.get("title", ""),
                "deliverable_path": dpath,
                "evidence": "filesystem_check",
            })
    return duplicates


def detect_oversized(plans: dict, max_files: int) -> list:
    """Return oversized records for plans listing more than *max_files* files."""
    result = []
    for task_id, plan in plans.items():
        files = plan.get("expected_files") or []
        if len(files) > max_files:
            result.append({
                "task_id": task_id,
                "file_count": len(files),
                "max_files": max_files,
                "files": files,
            })
    return result


def compute_sequential_order(tasks: list, plans: dict) -> list:
    """Reorder *tasks* so that tasks sharing expected files run sequentially.

    Algorithm:
    - The first task to claim a file "owns" it; later tasks that claim the same
      file depend on the owner.
    - Dependencies form a DAG; Kahn's topological sort produces the order.
    - Ties (tasks with no dependency on each other) preserve original order.

    Pure function — no I/O, no LLM calls.
    """
    if not tasks:
        return list(tasks)

    task_ids = [t.get("id", "") for t in tasks]
    id_to_task = {t.get("id", ""): t for t in tasks}

    # file → first task_id that claims it (preserves original order)
    file_owner: dict = {}
    # task_id → set of task_ids it must wait for
    deps: dict = {tid: set() for tid in task_ids}

    for tid in task_ids:
        for f in plans.get(tid, {}).get("expected_files") or []:
            if f in file_owner:
                deps[tid].add(file_owner[f])
            else:
                file_owner[f] = tid

    # Kahn's topological sort; tie-break preserves original order
    in_degree = {tid: len(deps[tid]) for tid in task_ids}
    ready = deque(tid for tid in task_ids if in_degree[tid] == 0)

    order = []
    while ready:
        tid = ready.popleft()
        order.append(tid)
        for other in task_ids:
            if tid in deps[other]:
                deps[other].discard(tid)
                in_degree[other] -= 1
                if in_degree[other] == 0:
                    ready.append(other)

    # If a cycle exists (shouldn't in practice), append remaining tasks
    remaining = [tid for tid in task_ids if tid not in order]
    order.extend(remaining)

    return [id_to_task[tid] for tid in order if tid in id_to_task]


# ── Prompt, response parsing, and LLM call ───────────────────────────────────

def build_planning_prompt(task: dict, peer_task_ids: list, strategy_context: str = "") -> str:
    """Build the planning prompt for a single task.

    *strategy_context* is the STRATEGY.md excerpt (or ``""``).  When provided
    it is injected into the prompt so plans are doctrine-shaped by construction.
    """
    formatted_strategy = ""
    if strategy_context:
        formatted_strategy = _STRATEGY_CONTEXT_TEMPLATE.format(strategy_text=strategy_context)
    return _PLANNING_PROMPT.format(
        strategy_context=formatted_strategy,
        task_id=task.get("id", ""),
        title=task.get("title", "(untitled)"),
        task_type=task.get("type", "general"),
        branch=task.get("branch", ""),
        description=(task.get("description") or "")[:500],
        peer_task_ids=", ".join(peer_task_ids) if peer_task_ids else "none",
        max_files=_MAX_EXPECTED_FILES,
    )


def parse_planning_response(response_text: str) -> dict:
    """Parse LLM response into a plan dict; returns {} on any parse failure."""
    if not response_text:
        return {}
    text = response_text.strip()
    # Strip markdown fences
    if text.startswith("```"):
        lines = text.splitlines()
        inner = lines[1:]
        if inner and inner[-1].strip() == "```":
            inner = inner[:-1]
        text = "\n".join(inner)
    try:
        data = json.loads(text)
        if not isinstance(data, dict):
            return {}
        # Sanitize expected_files
        raw_files = data.get("expected_files") or []
        data["expected_files"] = [
            str(f).strip() for f in raw_files
            if str(f).strip()
        ][:_MAX_EXPECTED_FILES]
        # Sanitize depends_on
        raw_deps = data.get("depends_on") or []
        data["depends_on"] = [str(d).strip() for d in raw_deps if str(d).strip()]
        return data
    except (json.JSONDecodeError, TypeError):
        return {}


def call_planning_model(prompt: str, model: str, api_key: Optional[str]) -> dict:
    """Call the Anthropic API with a bounded planning prompt.

    Returns ``{"plan": dict, "error": None}`` on success,
    or ``{"plan": {}, "error": str}`` on failure.
    """
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        message = client.messages.create(
            model=model,
            max_tokens=_MAX_PLAN_TOKENS,
            messages=[{"role": "user", "content": prompt}],
        )
        text = message.content[0].text if message.content else ""
        plan = parse_planning_response(text)
        return {"plan": plan, "error": None}
    except Exception as exc:
        return {"plan": {}, "error": str(exc)}


# ── Main pass ─────────────────────────────────────────────────────────────────

def run_mission_planning_pass(
    tasks: list,
    repo_path: str,
    model: str,
    api_key: Optional[str],
    strategy_context: str = "",
) -> dict:
    """Run a cheap planning pass over all tasks that don't have plans yet.

    Returns::

        {
          "plans":              dict[task_id → plan],
          "conflicts":          list[{"task_ids": [...], "shared_files": [...]}],
          "duplicates":         list[{"task_id": ..., ...}],
          "oversized":          list[{"task_id": ..., "file_count": ..., ...}],
          "reordered_task_ids": list[str],   # [] when no reordering is needed
        }

    Degrades gracefully: per-task errors are logged and that task's plan is
    omitted; the analysis still runs on whatever plans were collected.
    """
    from config import get_config
    cfg = get_config()
    max_files = cfg.mission_planning_max_files

    task_ids = [t.get("id", "") for t in tasks]
    existing = load_all_plans(task_ids)
    new_plans: dict = {}

    for task in tasks:
        tid = task.get("id", "")
        if tid in existing:
            continue

        peer_ids = [t.get("id", "") for t in tasks if t.get("id") != tid]
        prompt = build_planning_prompt(task, peer_ids, strategy_context=strategy_context)
        result = call_planning_model(prompt, model, api_key)

        if result["error"]:
            log_event("mission_planning_task_error", {
                "task_id": tid,
                "error": result["error"],
            })
            continue

        plan = result["plan"]
        if plan:
            plan["task_id"] = tid
            save_plan(tid, plan)
            new_plans[tid] = plan
        else:
            log_event("mission_planning_task_parse_failed", {"task_id": tid})

    all_plans = {**existing, **new_plans}

    conflicts = detect_conflicts(tasks, all_plans)
    duplicates = detect_duplicates(tasks, all_plans, repo_path)
    oversized = detect_oversized(all_plans, max_files)

    reordered_ids: list = []
    if conflicts:
        reordered = compute_sequential_order(tasks, all_plans)
        candidate_ids = [t.get("id", "") for t in reordered]
        if candidate_ids != task_ids:
            reordered_ids = candidate_ids

    return {
        "plans": all_plans,
        "conflicts": conflicts,
        "duplicates": duplicates,
        "oversized": oversized,
        "reordered_task_ids": reordered_ids,
    }
