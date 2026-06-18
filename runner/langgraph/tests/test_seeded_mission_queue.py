"""Unit tests for the Seeded Mission Queue Executor.

Runs standalone (no pytest dependency):

    python tests/test_seeded_mission_queue.py

Covers:
  - ``seed_tasks_from_mission`` pure conversion helper
  - ``check_mission_completion`` Supabase polling helper (stubbed client)
  - Graph node ``seed_mission_queue_if_needed`` (Supabase stubbed via monkeypatching)
  - Routing: ``_route_after_compile_mission`` and ``_route_after_seed_mission_queue``
  - Graph wiring: node present in compiled graph
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.seeded_mission_queue import (
    seed_tasks_from_mission,
    check_mission_completion,
)
import graph
from state import RunnerState

# Silence flight recorder and disk persistence during all tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None


# ---------------------------------------------------------------------------
# Pure helper: seed_tasks_from_mission
# ---------------------------------------------------------------------------

_MISSION = {
    "id": "mission-uuid-1",
    "name": "Auth Feature",
    "goal": "Add user authentication",
    "status": "queued",
}

_TASKS = [
    {
        "id": "task-uuid-1",
        "mission_id": "mission-uuid-1",
        "task_id": "",
        "title": "Add login page",
        "type": "frontend",
        "branch": "feature/auth/login",
        "preferred_worker": "codex",
        "position": 1,
        "status": "queued",
    },
    {
        "id": "task-uuid-2",
        "mission_id": "mission-uuid-1",
        "task_id": "",
        "title": "Add auth API",
        "type": "backend",
        "branch": "",
        "preferred_worker": None,
        "position": 2,
        "status": "queued",
    },
]


def test_seed_tasks_count():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    assert len(tasks) == 2


def test_seed_tasks_titles():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    assert tasks[0]["title"] == "Add login page"
    assert tasks[1]["title"] == "Add auth API"


def test_seed_tasks_types():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    assert tasks[0]["type"] == "frontend"
    assert tasks[1]["type"] == "backend"


def test_seed_tasks_status_queued():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    for t in tasks:
        assert t["status"] == "queued"


def test_seed_tasks_source():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    for t in tasks:
        assert t["source"] == "seeded_mission"


def test_seed_tasks_mission_name():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    for t in tasks:
        assert t["mission"] == "Auth Feature"


def test_seed_tasks_seeded_mission_id():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    for t in tasks:
        assert t["seeded_mission_id"] == "mission-uuid-1"


def test_seed_tasks_seeded_task_id():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    assert tasks[0]["seeded_task_id"] == "task-uuid-1"
    assert tasks[1]["seeded_task_id"] == "task-uuid-2"


def test_seed_tasks_custom_branch_preserved():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    assert tasks[0]["branch"] == "feature/auth/login"


def test_seed_tasks_auto_branch_when_empty():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    branch = tasks[1]["branch"]
    assert branch.startswith("feature/auth-feature/")
    assert "add-auth-api" in branch


def test_seed_tasks_preferred_worker_included():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    assert tasks[0].get("preferred_worker") == "codex"


def test_seed_tasks_no_preferred_worker_excluded():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    assert "preferred_worker" not in tasks[1] or tasks[1].get("preferred_worker") is None
    # The field must not be set when None to avoid confusing the worker chooser
    # (seed_tasks_from_mission only adds it when truthy)
    assert not tasks[1].get("preferred_worker")


def test_seed_tasks_uses_db_task_id():
    tasks_with_id = [dict(_TASKS[0], task_id="my-custom-id")]
    tasks = seed_tasks_from_mission(_MISSION, tasks_with_id)
    assert tasks[0]["id"] == "my-custom-id"


def test_seed_tasks_generates_task_id_when_empty():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    # No task_id set in _TASKS → generated from mission slug + position
    assert tasks[0]["id"] == "auth-feature-1"
    assert tasks[1]["id"] == "auth-feature-2"


def test_seed_tasks_empty_list():
    tasks = seed_tasks_from_mission(_MISSION, [])
    assert tasks == []


# ---------------------------------------------------------------------------
# check_mission_completion (Supabase stubbed)
# ---------------------------------------------------------------------------

def _stub_client(rows):
    """Return a fake Supabase client that returns *rows* for table queries."""
    class FakeResult:
        data = rows

    class FakeQuery:
        def select(self, *a): return self
        def eq(self, *a): return self
        def order(self, *a): return self
        def limit(self, *a): return self
        def execute(self): return FakeResult()

    class FakeTable:
        def table(self, name): return FakeQuery()

    return FakeTable()


def _with_stub_client(rows, fn):
    """Run fn() with _get_client stubbed to return a fake client."""
    import tools.seeded_mission_queue as smq
    original = smq._get_client
    smq._get_client = lambda: _stub_client(rows)
    try:
        return fn()
    finally:
        smq._get_client = original


def test_check_completion_all_complete():
    rows = [{"status": "complete"}, {"status": "complete"}]
    result = _with_stub_client(rows, lambda: check_mission_completion("uuid-1"))
    assert result["status"] == "completed"


def test_check_completion_one_failed():
    rows = [{"status": "complete"}, {"status": "failed"}]
    result = _with_stub_client(rows, lambda: check_mission_completion("uuid-1"))
    assert result["status"] == "failed"


def test_check_completion_still_running():
    rows = [{"status": "complete"}, {"status": "running"}]
    result = _with_stub_client(rows, lambda: check_mission_completion("uuid-1"))
    assert result["status"] == "in_progress"


def test_check_completion_queued_still_running():
    rows = [{"status": "queued"}]
    result = _with_stub_client(rows, lambda: check_mission_completion("uuid-1"))
    assert result["status"] == "in_progress"


def test_check_completion_no_rows():
    result = _with_stub_client([], lambda: check_mission_completion("uuid-1"))
    assert result["status"] == "unknown"


def test_check_completion_blocked_counts_as_terminal():
    rows = [{"status": "complete"}, {"status": "blocked"}]
    result = _with_stub_client(rows, lambda: check_mission_completion("uuid-1"))
    # blocked is terminal but not complete → failed status
    assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# Graph node: seed_mission_queue_if_needed
# ---------------------------------------------------------------------------

def _make_state(**kwargs) -> RunnerState:
    return RunnerState(**kwargs)


def _stub_graph_seeded(mission=None, task_rows=None, captured_tasks=None):
    """Patch graph module globals to stub Supabase and task_tools."""
    if captured_tasks is None:
        captured_tasks = []

    graph.fetch_next_queued_mission = lambda: mission
    graph.fetch_mission_tasks = lambda mid: task_rows or []
    graph.seed_tasks_from_mission = lambda m, t: [
        {
            "id": f"task-{i+1}",
            "title": row["title"],
            "type": row.get("type", "general"),
            "branch": row.get("branch", f"feature/task-{i+1}"),
            "status": "queued",
            "source": "seeded_mission",
            "mission": m.get("name", ""),
            "seeded_mission_id": str(m.get("id", "")),
            "seeded_task_id": str(row.get("id", "")),
        }
        for i, row in enumerate(t)
    ]
    graph.mark_mission_running = lambda mid: {"success": True}
    graph.add_task = lambda t: captured_tasks.append(dict(t))

    _first = [None]
    def _get_next():
        return captured_tasks[0] if captured_tasks else None
    graph.get_next_queued_task = _get_next
    graph.update_task_branch = lambda *a, **k: None

    return captured_tasks


def _restore_graph_seeded():
    from tools import task_tools
    from tools.seeded_mission_queue import (
        fetch_next_queued_mission,
        fetch_mission_tasks,
        seed_tasks_from_mission,
        mark_mission_running,
    )
    graph.fetch_next_queued_mission = fetch_next_queued_mission
    graph.fetch_mission_tasks = fetch_mission_tasks
    graph.seed_tasks_from_mission = seed_tasks_from_mission
    graph.mark_mission_running = mark_mission_running
    graph.add_task = task_tools.add_task
    graph.get_next_queued_task = task_tools.get_next_queued_task
    graph.update_task_branch = task_tools.update_task_branch


_SAMPLE_MISSION = {"id": "m-uuid", "name": "Test Mission", "status": "queued"}
_SAMPLE_TASK_ROWS = [
    {"id": "t-uuid-1", "title": "Task One", "type": "backend", "branch": "feature/t1", "position": 1},
    {"id": "t-uuid-2", "title": "Task Two", "type": "frontend", "branch": "feature/t2", "position": 2},
]


def test_node_disabled_by_config():
    captured = _stub_graph_seeded(mission=_SAMPLE_MISSION, task_rows=_SAMPLE_TASK_ROWS)
    try:
        graph.cfg.seeded_mission_queue_enabled = False
        out = graph.seed_mission_queue_if_needed(_make_state())
        assert out.current_task is None
        assert captured == []
    finally:
        graph.cfg.seeded_mission_queue_enabled = True
        _restore_graph_seeded()


def test_node_no_supabase():
    captured = _stub_graph_seeded(mission=_SAMPLE_MISSION, task_rows=_SAMPLE_TASK_ROWS)
    original_has_supabase = type(graph.cfg).has_supabase.fget
    try:
        graph.cfg.seeded_mission_queue_enabled = True
        # Patch has_supabase property to return False
        type(graph.cfg).has_supabase = property(lambda self: False)
        out = graph.seed_mission_queue_if_needed(_make_state())
        assert out.current_task is None
        assert captured == []
    finally:
        graph.cfg.seeded_mission_queue_enabled = True
        type(graph.cfg).has_supabase = property(original_has_supabase)
        _restore_graph_seeded()


def test_node_no_queued_mission():
    captured = _stub_graph_seeded(mission=None, task_rows=[])
    try:
        graph.cfg.seeded_mission_queue_enabled = True
        type(graph.cfg).has_supabase = property(lambda self: True)
        out = graph.seed_mission_queue_if_needed(_make_state())
        assert out.current_task is None
        assert captured == []
    finally:
        original_has_supabase = property(lambda self: bool(graph.cfg.supabase_url and graph.cfg.supabase_service_role_key))
        type(graph.cfg).has_supabase = original_has_supabase
        _restore_graph_seeded()


def test_node_seeds_tasks_and_loads_first():
    captured = _stub_graph_seeded(mission=_SAMPLE_MISSION, task_rows=_SAMPLE_TASK_ROWS)
    try:
        graph.cfg.seeded_mission_queue_enabled = True
        type(graph.cfg).has_supabase = property(lambda self: True)
        out = graph.seed_mission_queue_if_needed(_make_state(stop_reason="no_queued_tasks"))
        assert len(captured) == 2
        assert out.current_task is not None
        assert out.current_task["title"] == "Task One"
        assert out.current_task_id == out.current_task["id"]
        assert out.stop_reason is None
    finally:
        original_has_supabase = property(lambda self: bool(graph.cfg.supabase_url and graph.cfg.supabase_service_role_key))
        type(graph.cfg).has_supabase = original_has_supabase
        _restore_graph_seeded()


def test_node_skips_when_task_already_loaded():
    captured = _stub_graph_seeded(mission=_SAMPLE_MISSION, task_rows=_SAMPLE_TASK_ROWS)
    try:
        graph.cfg.seeded_mission_queue_enabled = True
        type(graph.cfg).has_supabase = property(lambda self: True)
        state = _make_state(current_task={"id": "existing", "title": "Already there"})
        out = graph.seed_mission_queue_if_needed(state)
        assert out.current_task["id"] == "existing"
        assert captured == []
    finally:
        original_has_supabase = property(lambda self: bool(graph.cfg.supabase_url and graph.cfg.supabase_service_role_key))
        type(graph.cfg).has_supabase = original_has_supabase
        _restore_graph_seeded()


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def test_route_compile_no_task_to_seed_queue():
    s = RunnerState(current_task=None)
    assert graph._route_after_compile_mission(s) == "seed_mission_queue_if_needed"


def test_route_compile_with_task_to_choose_worker():
    s = RunnerState(current_task={"id": "t1", "title": "T"})
    assert graph._route_after_compile_mission(s) == "choose_worker"


def test_route_seed_queue_no_task_to_chatgpt():
    s = RunnerState(current_task=None)
    assert graph._route_after_seed_mission_queue(s) == "ask_chatgpt_for_task_if_needed"


def test_route_seed_queue_with_task_to_choose_worker():
    s = RunnerState(current_task={"id": "t1", "title": "T"})
    assert graph._route_after_seed_mission_queue(s) == "choose_worker"


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------

def test_node_is_wired_into_graph():
    nodes = list(graph.build_graph().get_graph().nodes)
    assert "seed_mission_queue_if_needed" in nodes, nodes


def test_compile_still_routes_to_chatgpt_via_seed_node():
    """compile_mission_if_needed → seed_mission_queue_if_needed → ask_chatgpt_for_task_if_needed."""
    g = graph.build_graph().get_graph()
    # Check that there is an edge from compile to seed
    edges = [(e.source, e.target) for e in g.edges]
    sources_from_compile = [t for s, t in edges if s == "compile_mission_if_needed"]
    assert "seed_mission_queue_if_needed" in sources_from_compile, sources_from_compile


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_seed_tasks_count,
        test_seed_tasks_titles,
        test_seed_tasks_types,
        test_seed_tasks_status_queued,
        test_seed_tasks_source,
        test_seed_tasks_mission_name,
        test_seed_tasks_seeded_mission_id,
        test_seed_tasks_seeded_task_id,
        test_seed_tasks_custom_branch_preserved,
        test_seed_tasks_auto_branch_when_empty,
        test_seed_tasks_preferred_worker_included,
        test_seed_tasks_no_preferred_worker_excluded,
        test_seed_tasks_uses_db_task_id,
        test_seed_tasks_generates_task_id_when_empty,
        test_seed_tasks_empty_list,
        test_check_completion_all_complete,
        test_check_completion_one_failed,
        test_check_completion_still_running,
        test_check_completion_queued_still_running,
        test_check_completion_no_rows,
        test_check_completion_blocked_counts_as_terminal,
        test_node_disabled_by_config,
        test_node_no_supabase,
        test_node_no_queued_mission,
        test_node_seeds_tasks_and_loads_first,
        test_node_skips_when_task_already_loaded,
        test_route_compile_no_task_to_seed_queue,
        test_route_compile_with_task_to_choose_worker,
        test_route_seed_queue_no_task_to_chatgpt,
        test_route_seed_queue_with_task_to_choose_worker,
        test_node_is_wired_into_graph,
        test_compile_still_routes_to_chatgpt_via_seed_node,
    ]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
