"""Mission compiler: parses an inbox YAML mission file and expands it into runner tasks.

A mission file is a YAML document placed in ``inbox/`` that describes a
strategic goal and a set of sub-tasks to accomplish it.  The compiler converts
this high-level specification into concrete runner tasks (task dicts) that are
added to the queue.

Mission file format (``inbox/<name>.yml``):

    name: "Feature: User Authentication"
    goal: "Optional free-text goal description"
    tasks:
      - title: "Add login page"
        type: "frontend"
        branch: "feature/auth/login-page"     # optional; auto-generated if omitted
        preferred_worker: "codex"             # optional
      - title: "Add auth API endpoints"
        type: "backend"

After compilation the source file is renamed to ``<name>.yml.processed`` so
the compiler does not re-expand the same mission on subsequent runner restarts.

These helpers are pure (no I/O, no state mutation) — the graph node in
``graph.compile_mission_if_needed`` handles file I/O and state mutation.
"""
import re
from datetime import datetime
from pathlib import Path

import yaml

_VALID_TASK_TYPES = frozenset({
    "backend",
    "design",
    "docs",
    "frontend",
    "general",
    "infra",
    "polish",
    "test",
    "ui",
})


def _slug(text: str, max_len: int = 40) -> str:
    """Convert text to a URL-safe kebab-case slug."""
    slug = re.sub(r"[^\w\s-]", "", text.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    return slug[:max_len].strip("-")


def parse_mission_file(path: str | Path) -> dict:
    """Parse a YAML mission file and return the mission dict.

    Raises:
        FileNotFoundError: if *path* does not exist.
        ValueError:        if the file is not a YAML mapping.
        yaml.YAMLError:    if the YAML is malformed.
    """
    text = Path(path).read_text()
    data = yaml.safe_load(text)
    if not isinstance(data, dict):
        raise ValueError(f"Mission file must be a YAML mapping, got {type(data).__name__}")
    return data


def validate_mission(mission: dict) -> list[str]:
    """Validate a mission dict. Returns a list of human-readable error strings.

    An empty list means the mission is valid and ready to compile.
    """
    errors: list[str] = []
    if not mission.get("name"):
        errors.append("mission must have a 'name' field")
    tasks = mission.get("tasks")
    if not tasks:
        errors.append("mission must have at least one task in 'tasks'")
    elif not isinstance(tasks, list):
        errors.append("'tasks' must be a list")
    else:
        for i, t in enumerate(tasks):
            if not isinstance(t, dict):
                errors.append(f"task[{i}] must be a dict, got {type(t).__name__}")
            elif not t.get("title"):
                errors.append(f"task[{i}] must have a 'title' field")
    return errors


def compile_mission(mission: dict) -> list[dict]:
    """Compile a mission dict into an ordered list of runner task dicts.

    Returns task dicts ready for ``add_task()``.  Unknown task types fall back
    to ``general``.  Branch names and task IDs are auto-generated from the
    mission name and task title when not explicitly provided.
    """
    mission_name: str = mission.get("name", "mission")
    mission_slug = _slug(mission_name, max_len=30)
    now = datetime.utcnow().isoformat()
    compiled: list[dict] = []

    for i, spec in enumerate(mission.get("tasks", []), 1):
        title: str = spec.get("title", f"Task {i}")
        task_type: str = spec.get("type", "general")
        if task_type not in _VALID_TASK_TYPES:
            task_type = "general"

        title_slug = _slug(title, max_len=30)
        branch: str = spec.get("branch") or f"feature/{mission_slug}/{title_slug}"
        task_id: str = spec.get("id") or f"{mission_slug}-{i}"

        task: dict = {
            "id": task_id,
            "title": title,
            "type": task_type,
            "branch": branch,
            "status": "queued",
            "source": "mission",
            "mission": mission_name,
            "created_at": now,
        }
        preferred_worker = spec.get("preferred_worker")
        if preferred_worker:
            task["preferred_worker"] = preferred_worker

        compiled.append(task)

    return compiled


def format_mission_summary(mission: dict, tasks: list[dict]) -> str:
    """Build a human-readable mission compilation summary written to ``outbox/``."""
    name = mission.get("name", "unknown")
    goal = mission.get("goal", "")
    lines = [
        f"# Mission Compiled: {name}",
        "",
    ]
    if goal:
        lines += [f"Goal: {goal}", ""]
    lines += [
        f"Tasks queued: {len(tasks)}",
        "",
        "## Tasks",
        "",
    ]
    for i, t in enumerate(tasks, 1):
        lines.append(f"  {i}. [{t.get('type', 'general')}] {t['title']}")
        lines.append(f"     branch: {t.get('branch', 'n/a')}")
        if t.get("preferred_worker"):
            lines.append(f"     worker: {t['preferred_worker']}")
    lines += [
        "",
        "The runner will execute these tasks in order.",
        "",
    ]
    return "\n".join(lines)
