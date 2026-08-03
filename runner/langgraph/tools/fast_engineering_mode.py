"""Fast Engineering Mode — workspace snapshot injection for reliable LangGraph development.

When FAST_ENGINEERING_MODE=true, the runner pre-builds a compact snapshot of the
current runner workspace (graph nodes, tools, tests) and injects it into the worker
prompt.  This gives Claude immediate architecture awareness without exploratory reads,
making each dispatch faster and more reliably aligned with existing patterns.

All functions are pure side-effect-free helpers (no graph state, no log_event calls).
The snapshot builder reads the filesystem via the runner_dir argument.
"""

from __future__ import annotations
from pathlib import Path


# Keywords that indicate a task is runner/LangGraph engineering work.
_RUNNER_KEYWORDS = [
    "runner", "langgraph", "graph", "node", "subagent", "tool", "worker",
    "guard", "gate", "loop", "dispatch", "agent", "state", "config",
    "engineering", "mode", "fast_engineering",
]

# Task types that suggest runner/agent engineering work.
_RUNNER_TASK_TYPES = frozenset({
    "agent", "runner", "langgraph", "orchestration", "workflow", "backend",
})


def is_fast_engineering_task(task: dict) -> bool:
    """Return True when the task is likely runner or LangGraph engineering work.

    Checks task type against known runner task types and keyword-scans the
    title and description.  Used for auto-detection when the caller wants to
    inject engineering context only for relevant tasks.
    """
    task_type = (task.get("type") or "").strip().lower()
    if task_type in _RUNNER_TASK_TYPES:
        return True

    haystack = " ".join([
        task.get("title") or "",
        task.get("description") or "",
        task_type,
    ]).lower()

    return any(kw in haystack for kw in _RUNNER_KEYWORDS)


def build_engineering_context(runner_dir: str) -> dict:
    """Scan the runner directory and return a compact architecture snapshot.

    Reads the filesystem to collect:
    - Graph nodes — parsed from ``add_node`` calls in graph.py.
    - Tool names — ``*.py`` stems (excluding ``__init__``) from ``tools/``.
    - Test files — ``test_*.py`` stems from ``tests/``.

    Returns a dict with keys: runner_dir, nodes, tools, tests.
    """
    base = Path(runner_dir)

    # Collect tool names.
    tools_dir = base / "tools"
    tools: list[str] = []
    if tools_dir.is_dir():
        tools = sorted(
            p.stem for p in tools_dir.glob("*.py")
            if not p.stem.startswith("__")
        )

    # Collect test file stems.
    tests_dir = base / "tests"
    tests: list[str] = []
    if tests_dir.is_dir():
        tests = sorted(p.stem for p in tests_dir.glob("test_*.py"))

    # Parse graph node names from add_node() calls in graph.py.
    graph_path = base / "graph.py"
    nodes: list[str] = []
    if graph_path.is_file():
        for line in graph_path.read_text().splitlines():
            stripped = line.strip()
            if stripped.startswith('builder.add_node("'):
                start = stripped.index('"') + 1
                end = stripped.index('"', start)
                nodes.append(stripped[start:end])

    return {
        "runner_dir": str(base),
        "nodes": nodes,
        "tools": tools,
        "tests": tests,
    }


def format_engineering_injection(context: dict) -> str:
    """Format the engineering snapshot as a prompt prefix block.

    The block is structured for quick scanning — the worker can orient itself
    in the architecture without re-reading multiple files.  An empty string is
    returned when the context contains no useful information.
    """
    nodes = context.get("nodes") or []
    tools = context.get("tools") or []
    tests = context.get("tests") or []

    if not nodes and not tools and not tests:
        return ""

    lines = [
        "[Fast Engineering Mode — runner workspace snapshot]",
        "",
        "## LangGraph nodes (graph.py add_node calls)",
        ", ".join(nodes) if nodes else "(none found)",
        "",
        "## Tools (tools/)",
        ", ".join(tools) if tools else "(none found)",
        "",
        "## Tests (tests/)",
        ", ".join(tests) if tests else "(none found)",
        "",
        "## Architecture invariants",
        "- Every node signature: (state: RunnerState) -> RunnerState",
        "- Always end every node with: return _persist(state, '<node_name>')",
        "- Log operational events via log_event(event_type, payload) — never print()",
        "- New tools go in tools/<name>.py with a matching tests/test_<name>.py",
        "- New config vars: update config.py, the README.md env table, and at least one test",
        "- New graph nodes: add to build_graph() with both add_node and the appropriate edge",
        "",
    ]

    return "\n".join(lines)
