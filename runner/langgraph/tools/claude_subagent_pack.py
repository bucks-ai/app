"""Claude Code subagent pack — specialised dispatch configurations for ClaudeWorker.

A "subagent" is a named role configuration that injects focused system context
into the worker prompt before dispatch.  The pack provides:

  - ``SUBAGENT_REGISTRY``: all built-in role definitions.
  - ``select_subagent(task)``: pick the best role for a task dict.
  - ``build_subagent_prompt_prefix(subagent)``: format the context block to
    prepend to the worker prompt.
  - ``list_subagents()``: return all role configs (for logging/tooling).

All functions are pure — no I/O, no graph state.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

SUBAGENT_REGISTRY: dict[str, dict] = {
    "backend": {
        "name": "backend",
        "description": (
            "Handles server-side, API, database, schema, and infrastructure tasks."
        ),
        "task_types": ["backend", "api", "schema", "database", "infra", "migration"],
        "keyword_hints": [
            "api", "endpoint", "route", "database", "schema", "migration",
            "supabase", "server", "backend", "infra", "infrastructure", "sql",
            "rpc", "auth", "middleware",
        ],
        "system_context": (
            "You are specialised in backend development: REST and GraphQL APIs, "
            "database schema design, SQL migrations, server-side logic, and "
            "infrastructure configuration.  Prefer minimal, well-tested changes "
            "and always run the project's check script before declaring success."
        ),
    },
    "agent": {
        "name": "agent",
        "description": (
            "Builds and extends autonomous agent systems: LangGraph, runners, "
            "orchestration, and multi-agent tooling."
        ),
        "task_types": ["agent", "runner", "langgraph", "orchestration", "workflow"],
        "keyword_hints": [
            "agent", "runner", "langgraph", "graph", "node", "subagent",
            "orchestration", "workflow", "loop", "dispatch", "worker",
            "mission", "planner", "gate", "guard",
        ],
        "system_context": (
            "You are specialised in autonomous agent systems: LangGraph state graphs, "
            "multi-agent orchestration, runner loop design, guard/gate patterns, and "
            "worker dispatch.  Keep RunnerState field names stable, always return "
            "_persist(state, ...) at the end of every node, and ship tests alongside "
            "every new tool."
        ),
    },
    "testing": {
        "name": "testing",
        "description": "Writes, repairs, and improves test suites.",
        "task_types": ["testing", "test", "qa", "coverage"],
        "keyword_hints": [
            "test", "tests", "testing", "pytest", "coverage", "unit", "integration",
            "fixture", "mock", "assert", "spec", "qa",
        ],
        "system_context": (
            "You are specialised in software testing: writing pytest unit and "
            "integration tests, improving coverage, fixing flaky tests, and ensuring "
            "mocks faithfully represent production behaviour.  Every test must be "
            "deterministic and runnable with `python -m pytest tests/ -x -q`."
        ),
    },
    "review": {
        "name": "review",
        "description": "Reviews code for correctness, security, and design quality.",
        "task_types": ["review", "audit", "security", "refactor"],
        "keyword_hints": [
            "review", "audit", "refactor", "security", "vulnerability", "bug",
            "cleanup", "quality", "lint", "type", "typing",
        ],
        "system_context": (
            "You are specialised in code review and refactoring: identifying "
            "correctness bugs, security vulnerabilities (OWASP Top 10), design "
            "problems, and opportunities for simplification.  Report findings "
            "concisely and apply only high-confidence fixes."
        ),
    },
    "frontend": {
        "name": "frontend",
        "description": "Handles UI, React/Next.js, and frontend tooling tasks.",
        "task_types": ["ui", "frontend", "polish", "design", "css", "component"],
        "keyword_hints": [
            "ui", "ux", "react", "next", "component", "page", "css", "style",
            "tailwind", "frontend", "design", "layout", "modal", "form", "button",
        ],
        "system_context": (
            "You are specialised in frontend development: React, Next.js, Tailwind CSS, "
            "accessible component design, and UI polish.  Read the Next.js guide in "
            "node_modules/next/dist/docs/ before writing any framework code and heed "
            "deprecation notices."
        ),
    },
    "general": {
        "name": "general",
        "description": "Default fallback for uncategorised tasks.",
        "task_types": [],
        "keyword_hints": [],
        "system_context": "",
    },
}

# Ordered priority for keyword matching.
# "testing" before "backend" so that explicit test-language keywords ("unit",
# "pytest", "coverage") win over domain words like "auth" that also appear in
# backend keyword hints.
_MATCH_ORDER = ["agent", "testing", "backend", "review", "frontend"]


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def select_subagent(task: dict) -> dict:
    """Return the subagent config that best fits *task*.

    Selection order (first match wins):
    1. ``task["preferred_subagent"]`` — explicit caller override.
    2. ``task["type"]`` — match against each role's ``task_types`` list.
    3. Keyword scan of ``task["title"]`` + ``task.get("description", "")``
       against each role's ``keyword_hints``.
    4. Fallback: ``"general"``.
    """
    # 1. Explicit override.
    preferred = (task.get("preferred_subagent") or "").strip().lower()
    if preferred and preferred in SUBAGENT_REGISTRY:
        return SUBAGENT_REGISTRY[preferred]

    task_type = (task.get("type") or "").strip().lower()

    # 2. Task-type match.
    for role_name in _MATCH_ORDER:
        role = SUBAGENT_REGISTRY[role_name]
        if task_type in role["task_types"]:
            return role

    # 3. Keyword scan.
    haystack = " ".join([
        task.get("title") or "",
        task.get("description") or "",
        task_type,
    ]).lower()

    for role_name in _MATCH_ORDER:
        role = SUBAGENT_REGISTRY[role_name]
        if any(kw in haystack for kw in role["keyword_hints"]):
            return role

    return SUBAGENT_REGISTRY["general"]


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------

def build_subagent_prompt_prefix(subagent: dict) -> str:
    """Return the context block to prepend to the worker prompt.

    Returns an empty string for the ``"general"`` subagent (no added context).
    """
    ctx = (subagent.get("system_context") or "").strip()
    if not ctx:
        return ""
    name = subagent.get("name", "unknown")
    return f"[Subagent: {name}]\n{ctx}\n\n"


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------

def list_subagents() -> list[dict]:
    """Return all subagent configs (name + description), sorted by name."""
    return sorted(
        [
            {"name": v["name"], "description": v["description"]}
            for v in SUBAGENT_REGISTRY.values()
        ],
        key=lambda d: d["name"],
    )
