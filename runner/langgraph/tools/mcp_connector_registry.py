"""MCP Connector Registry — catalog and select MCP servers for Claude worker dispatch.

Maintains a registry of known MCP server configurations and selects the
appropriate servers for a given task based on task type and keyword hints.

Provides:
  - MCP_CONNECTOR_REGISTRY: dict of built-in connector configs.
  - is_connector_available(connector, env): check whether required env vars are set.
  - select_connectors(task, env): pick available connectors for a task.
  - build_mcp_server_config(connectors, env): produce list of server config dicts.
  - format_connector_report(selected, all_connectors): human-readable report string.
  - list_connectors(): return all connector names + descriptions.

All functions are pure — no I/O, no graph state.
"""
from __future__ import annotations

import os
from typing import Optional

# ---------------------------------------------------------------------------
# Registry
# ---------------------------------------------------------------------------

MCP_CONNECTOR_REGISTRY: dict[str, dict] = {
    "supabase": {
        "name": "supabase",
        "description": (
            "Supabase MCP server for database queries, schema inspection, "
            "and auth operations."
        ),
        "task_types": [
            "backend", "database", "schema", "migration", "api",
        ],
        "keyword_hints": [
            "supabase", "database", "sql", "migration", "schema",
            "rpc", "auth", "postgres", "row level security", "rls",
        ],
        "command": "npx",
        "args": ["-y", "@supabase/mcp-server-supabase@latest"],
        "required_env": ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"],
        "env_passthrough": ["SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"],
    },
    "github": {
        "name": "github",
        "description": (
            "GitHub MCP server for repository operations, issue tracking, "
            "and pull request management."
        ),
        "task_types": [
            "backend", "agent", "infra", "general",
        ],
        "keyword_hints": [
            "github", "issue", "pr", "pull request", "branch",
            "commit", "repo", "repository", "merge",
        ],
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-github"],
        "required_env": ["GITHUB_TOKEN"],
        "env_passthrough": ["GITHUB_TOKEN"],
    },
    "filesystem": {
        "name": "filesystem",
        "description": (
            "Filesystem MCP server for reading and writing project files "
            "within the repo root."
        ),
        "task_types": [
            "backend", "frontend", "agent", "general", "review",
        ],
        "keyword_hints": [
            "file", "files", "read", "write", "directory",
        ],
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-filesystem", "."],
        "required_env": [],
        "env_passthrough": [],
    },
    "slack": {
        "name": "slack",
        "description": (
            "Slack MCP server for posting messages and interacting with "
            "Slack workspaces."
        ),
        "task_types": [
            "backend", "agent", "infra",
        ],
        "keyword_hints": [
            "slack", "notification", "notify", "channel", "message",
            "webhook",
        ],
        "command": "npx",
        "args": ["-y", "@modelcontextprotocol/server-slack"],
        "required_env": ["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"],
        "env_passthrough": ["SLACK_BOT_TOKEN", "SLACK_TEAM_ID"],
    },
}

# Selection order — priority when multiple connectors match.
_MATCH_ORDER = ["supabase", "github", "slack", "filesystem"]


# ---------------------------------------------------------------------------
# Availability check
# ---------------------------------------------------------------------------

def is_connector_available(connector: dict, env: Optional[dict] = None) -> bool:
    """Return True when all required env vars for *connector* are set and non-empty.

    Uses os.environ when *env* is None.
    """
    if env is None:
        env = dict(os.environ)
    return all(bool(env.get(k)) for k in connector.get("required_env", []))


# ---------------------------------------------------------------------------
# Selection
# ---------------------------------------------------------------------------

def select_connectors(task: dict, env: Optional[dict] = None) -> list[dict]:
    """Return available connectors appropriate for *task*, ordered by match priority.

    Selection logic (first winning rule per connector):
    1. ``task["type"]`` in ``connector["task_types"]``
    2. Keyword scan of title + description against ``connector["keyword_hints"]``

    Only connectors that pass :func:`is_connector_available` are included.
    """
    if env is None:
        env = dict(os.environ)

    task_type = (task.get("type") or "").strip().lower()
    haystack = " ".join([
        task.get("title") or "",
        task.get("description") or "",
        task_type,
    ]).lower()

    selected: list[dict] = []
    seen: set[str] = set()

    for name in _MATCH_ORDER:
        connector = MCP_CONNECTOR_REGISTRY[name]
        if name in seen:
            continue

        matched = (
            (task_type and task_type in connector.get("task_types", []))
            or any(kw in haystack for kw in connector.get("keyword_hints", []))
        )
        if not matched:
            continue

        if not is_connector_available(connector, env):
            continue

        selected.append(connector)
        seen.add(name)

    return selected


# ---------------------------------------------------------------------------
# Config building
# ---------------------------------------------------------------------------

def build_mcp_server_config(
    connectors: list[dict],
    env: Optional[dict] = None,
) -> list[dict]:
    """Return a list of MCP server config dicts for the given connectors.

    Each dict contains: name, command, args, env (only vars that are set).
    """
    if env is None:
        env = dict(os.environ)

    result: list[dict] = []
    for connector in connectors:
        server_env = {
            k: env[k]
            for k in connector.get("env_passthrough", [])
            if env.get(k)
        }
        result.append({
            "name": connector["name"],
            "command": connector["command"],
            "args": list(connector.get("args", [])),
            "env": server_env,
        })
    return result


# ---------------------------------------------------------------------------
# Reporting
# ---------------------------------------------------------------------------

def format_connector_report(
    selected: list[dict],
    all_connectors: Optional[list[dict]] = None,
) -> str:
    """Return a human-readable MCP connector report string.

    Shows selected connectors and, optionally, all configured connectors.
    """
    if all_connectors is None:
        all_connectors = list(MCP_CONNECTOR_REGISTRY.values())

    selected_names = {c["name"] for c in selected}
    lines: list[str] = [
        "MCP Connector Registry",
        f"Selected connectors: {len(selected)} / {len(all_connectors)}",
        "",
    ]
    for connector in all_connectors:
        name = connector["name"]
        if name in selected_names:
            icon = "+"
            status = "selected"
        elif connector.get("required_env"):
            icon = "-"
            status = f"unavailable (missing: {', '.join(connector['required_env'])})"
        else:
            icon = "~"
            status = "available (no credentials required)"
        lines.append(f"  [{icon}] {name:<12}  {status}  — {connector['description']}")

    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Introspection
# ---------------------------------------------------------------------------

def list_connectors() -> list[dict]:
    """Return all connector configs (name + description), sorted by name."""
    return sorted(
        [
            {"name": v["name"], "description": v["description"]}
            for v in MCP_CONNECTOR_REGISTRY.values()
        ],
        key=lambda d: d["name"],
    )
