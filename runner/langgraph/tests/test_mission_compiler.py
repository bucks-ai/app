"""Unit tests for the mission compiler.

Runs standalone (no pytest dependency):

    python tests/test_mission_compiler.py

Covers the pure helpers in tools/mission_compiler.py and the graph node
compile_mission_if_needed.  The node is exercised against a temporary
inbox/outbox; add_task, get_next_queued_task, update_task_branch, log_event,
and update_state are stubbed so no real disk state is touched.
"""
import os
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.mission_compiler import (
    _slug,
    parse_mission_file,
    validate_mission,
    compile_mission,
    format_mission_summary,
)
import graph
from state import RunnerState

# Silence flight recorder and disk persistence during all tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None


# ---------------------------------------------------------------------------
# Helper: pure slug
# ---------------------------------------------------------------------------

def test_slug_basic():
    assert _slug("Hello World") == "hello-world"


def test_slug_strips_special_chars():
    assert _slug("Feature: Auth!") == "feature-auth"


def test_slug_respects_max_len():
    long_text = "a" * 100
    result = _slug(long_text, max_len=10)
    assert len(result) <= 10


def test_slug_collapses_spaces():
    assert _slug("add   user  auth") == "add-user-auth"


def test_slug_handles_underscores():
    assert _slug("my_feature_name") == "my-feature-name"


# ---------------------------------------------------------------------------
# Helper: parse_mission_file
# ---------------------------------------------------------------------------

def _write_yaml(content: str, suffix: str = ".yml") -> Path:
    f = tempfile.NamedTemporaryFile(
        mode="w", suffix=suffix, delete=False, encoding="utf-8"
    )
    f.write(content)
    f.close()
    return Path(f.name)


def test_parse_mission_file_valid():
    p = _write_yaml("name: Test\ntasks:\n  - title: Do it\n")
    try:
        data = parse_mission_file(p)
        assert data["name"] == "Test"
        assert len(data["tasks"]) == 1
    finally:
        p.unlink(missing_ok=True)


def test_parse_mission_file_not_mapping():
    p = _write_yaml("- item1\n- item2\n")
    try:
        raised = False
        try:
            parse_mission_file(p)
        except ValueError as e:
            assert "mapping" in str(e)
            raised = True
        assert raised, "expected ValueError for list YAML"
    finally:
        p.unlink(missing_ok=True)


def test_parse_mission_file_missing_raises():
    raised = False
    try:
        parse_mission_file("/nonexistent/path/mission.yml")
    except FileNotFoundError:
        raised = True
    assert raised, "expected FileNotFoundError for missing file"


# ---------------------------------------------------------------------------
# Helper: validate_mission
# ---------------------------------------------------------------------------

def test_validate_mission_valid():
    mission = {"name": "My Mission", "tasks": [{"title": "Do something"}]}
    assert validate_mission(mission) == []


def test_validate_mission_no_name():
    mission = {"tasks": [{"title": "Do something"}]}
    errors = validate_mission(mission)
    assert any("name" in e for e in errors)


def test_validate_mission_empty_name():
    mission = {"name": "", "tasks": [{"title": "Do something"}]}
    errors = validate_mission(mission)
    assert any("name" in e for e in errors)


def test_validate_mission_no_tasks():
    mission = {"name": "My Mission"}
    errors = validate_mission(mission)
    assert any("task" in e for e in errors)


def test_validate_mission_empty_tasks():
    mission = {"name": "My Mission", "tasks": []}
    errors = validate_mission(mission)
    assert any("task" in e for e in errors)


def test_validate_mission_task_no_title():
    mission = {"name": "My Mission", "tasks": [{"type": "backend"}]}
    errors = validate_mission(mission)
    assert any("title" in e for e in errors)


def test_validate_mission_non_list_tasks():
    mission = {"name": "My Mission", "tasks": "not a list"}
    errors = validate_mission(mission)
    assert any("list" in e for e in errors)


# ---------------------------------------------------------------------------
# Helper: compile_mission
# ---------------------------------------------------------------------------

def test_compile_mission_basic():
    mission = {
        "name": "Auth Feature",
        "tasks": [{"title": "Add login page", "type": "frontend"}],
    }
    tasks = compile_mission(mission)
    assert len(tasks) == 1
    t = tasks[0]
    assert t["title"] == "Add login page"
    assert t["type"] == "frontend"
    assert t["status"] == "queued"
    assert t["source"] == "mission"
    assert t["mission"] == "Auth Feature"


def test_compile_mission_auto_branch():
    mission = {
        "name": "Auth Feature",
        "tasks": [{"title": "Add login page"}],
    }
    tasks = compile_mission(mission)
    branch = tasks[0]["branch"]
    assert branch.startswith("feature/auth-feature/")
    assert "add-login-page" in branch


def test_compile_mission_custom_branch():
    mission = {
        "name": "Auth",
        "tasks": [{"title": "Add login page", "branch": "feature/my-branch"}],
    }
    tasks = compile_mission(mission)
    assert tasks[0]["branch"] == "feature/my-branch"


def test_compile_mission_auto_task_id():
    mission = {
        "name": "Auth Feature",
        "tasks": [{"title": "Task One"}, {"title": "Task Two"}],
    }
    tasks = compile_mission(mission)
    assert tasks[0]["id"] == "auth-feature-1"
    assert tasks[1]["id"] == "auth-feature-2"


def test_compile_mission_custom_task_id():
    mission = {
        "name": "Auth",
        "tasks": [{"title": "Something", "id": "custom-id-123"}],
    }
    tasks = compile_mission(mission)
    assert tasks[0]["id"] == "custom-id-123"


def test_compile_mission_unknown_type_defaults_to_general():
    mission = {
        "name": "Test",
        "tasks": [{"title": "Weird task", "type": "unknowntype"}],
    }
    tasks = compile_mission(mission)
    assert tasks[0]["type"] == "general"


def test_compile_mission_preferred_worker_included():
    mission = {
        "name": "UI Mission",
        "tasks": [{"title": "Build UI", "type": "ui", "preferred_worker": "codex"}],
    }
    tasks = compile_mission(mission)
    assert tasks[0]["preferred_worker"] == "codex"


def test_compile_mission_no_preferred_worker_excluded():
    mission = {
        "name": "Test",
        "tasks": [{"title": "Task"}],
    }
    tasks = compile_mission(mission)
    assert "preferred_worker" not in tasks[0]


def test_compile_mission_multiple_tasks():
    mission = {
        "name": "Big Feature",
        "tasks": [
            {"title": "Step One"},
            {"title": "Step Two"},
            {"title": "Step Three"},
        ],
    }
    tasks = compile_mission(mission)
    assert len(tasks) == 3
    assert tasks[2]["id"] == "big-feature-3"


def test_compile_mission_valid_types_preserved():
    for t_type in ("backend", "frontend", "ui", "general", "design", "infra", "test", "docs"):
        mission = {"name": "T", "tasks": [{"title": "x", "type": t_type}]}
        tasks = compile_mission(mission)
        assert tasks[0]["type"] == t_type


# ---------------------------------------------------------------------------
# Helper: format_mission_summary
# ---------------------------------------------------------------------------

def test_format_mission_summary_includes_name():
    mission = {"name": "My Mission", "tasks": []}
    tasks = [{"title": "Task 1", "type": "backend", "branch": "feature/t1"}]
    text = format_mission_summary(mission, tasks)
    assert "My Mission" in text


def test_format_mission_summary_with_goal():
    mission = {"name": "M", "goal": "Make it work", "tasks": []}
    tasks = [{"title": "T", "type": "general", "branch": "feature/t"}]
    text = format_mission_summary(mission, tasks)
    assert "Make it work" in text


def test_format_mission_summary_no_goal_section():
    mission = {"name": "M", "tasks": []}
    tasks = [{"title": "T", "type": "general", "branch": "feature/t"}]
    text = format_mission_summary(mission, tasks)
    assert "Goal:" not in text


def test_format_mission_summary_task_count():
    mission = {"name": "M", "tasks": []}
    tasks = [
        {"title": "A", "type": "backend", "branch": "feature/a"},
        {"title": "B", "type": "frontend", "branch": "feature/b"},
    ]
    text = format_mission_summary(mission, tasks)
    assert "Tasks queued: 2" in text


def test_format_mission_summary_lists_tasks():
    mission = {"name": "M", "tasks": []}
    tasks = [{"title": "Build login", "type": "frontend", "branch": "feature/login"}]
    text = format_mission_summary(mission, tasks)
    assert "Build login" in text
    assert "frontend" in text
    assert "feature/login" in text


def test_format_mission_summary_shows_preferred_worker():
    mission = {"name": "M", "tasks": []}
    tasks = [{"title": "UI", "type": "ui", "branch": "b", "preferred_worker": "codex"}]
    text = format_mission_summary(mission, tasks)
    assert "codex" in text


# ---------------------------------------------------------------------------
# Graph node tests — exercised against a temp inbox/outbox
# ---------------------------------------------------------------------------

def _make_state(**kwargs) -> RunnerState:
    return RunnerState(**kwargs)


def _with_temp_runner_dir(fn):
    """Run fn(outbox, inbox) with graph._RUNNER_DIR pointed at a temp dir."""
    original = graph._RUNNER_DIR
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "outbox").mkdir()
        (root / "inbox").mkdir()
        graph._RUNNER_DIR = root
        try:
            return fn(root / "outbox", root / "inbox")
        finally:
            graph._RUNNER_DIR = original


_MISSION_YAML = """\
name: "Test Mission"
goal: "Run the tests"
tasks:
  - title: "Write tests"
    type: "test"
  - title: "Fix linting"
    type: "backend"
"""


def test_node_disabled_by_config():
    def body(outbox, inbox):
        (inbox / "mission.yml").write_text(_MISSION_YAML)
        graph.cfg.mission_compiler_enabled = False
        _captured = []
        graph.add_task = lambda t: _captured.append(t)
        out = graph.compile_mission_if_needed(_make_state())
        assert out.mission_compiled is None, "should not compile when disabled"
        assert _captured == [], "add_task should not be called"
    _with_temp_runner_dir(body)


def test_node_no_mission_file():
    def body(outbox, inbox):
        graph.cfg.mission_compiler_enabled = True
        _captured = []
        graph.add_task = lambda t: _captured.append(t)
        out = graph.compile_mission_if_needed(_make_state())
        assert out.mission_compiled is None, "no mission file → nothing compiled"
        assert _captured == []
    _with_temp_runner_dir(body)


def test_node_compiles_and_queues_tasks():
    def body(outbox, inbox):
        (inbox / "mission.yml").write_text(_MISSION_YAML)
        graph.cfg.mission_compiler_enabled = True
        _captured = []
        graph.add_task = lambda t: _captured.append(dict(t))
        graph.get_next_queued_task = lambda: _captured[0] if _captured else None
        graph.update_task_branch = lambda *a, **k: None
        try:
            out = graph.compile_mission_if_needed(_make_state())
            assert out.mission_compiled is True
            assert out.mission_name == "Test Mission"
            assert len(_captured) == 2
            assert _captured[0]["title"] == "Write tests"
            assert _captured[0]["source"] == "mission"
            assert _captured[1]["title"] == "Fix linting"
        finally:
            from tools import task_tools
            graph.get_next_queued_task = task_tools.get_next_queued_task
            graph.update_task_branch = task_tools.update_task_branch
    _with_temp_runner_dir(body)


def test_node_renames_processed_file():
    def body(outbox, inbox):
        mission_path = inbox / "mission.yml"
        mission_path.write_text(_MISSION_YAML)
        graph.cfg.mission_compiler_enabled = True
        _captured = []
        graph.add_task = lambda t: _captured.append(dict(t))
        graph.get_next_queued_task = lambda: _captured[0] if _captured else None
        graph.update_task_branch = lambda *a, **k: None
        try:
            graph.compile_mission_if_needed(_make_state())
            assert not mission_path.exists(), "original file should be renamed"
            assert (inbox / "mission.yml.processed").exists(), "processed file should exist"
        finally:
            from tools import task_tools
            graph.get_next_queued_task = task_tools.get_next_queued_task
            graph.update_task_branch = task_tools.update_task_branch
    _with_temp_runner_dir(body)


def test_node_writes_summary_to_outbox():
    def body(outbox, inbox):
        (inbox / "mymission.yml").write_text(_MISSION_YAML)
        graph.cfg.mission_compiler_enabled = True
        _captured = []
        graph.add_task = lambda t: _captured.append(dict(t))
        graph.get_next_queued_task = lambda: _captured[0] if _captured else None
        graph.update_task_branch = lambda *a, **k: None
        try:
            graph.compile_mission_if_needed(_make_state())
            summary_path = outbox / "mission_mymission_compiled.txt"
            assert summary_path.exists(), "summary file should be written to outbox"
            text = summary_path.read_text()
            assert "Test Mission" in text
        finally:
            from tools import task_tools
            graph.get_next_queued_task = task_tools.get_next_queued_task
            graph.update_task_branch = task_tools.update_task_branch
    _with_temp_runner_dir(body)


def test_node_clears_stop_reason_on_compile():
    def body(outbox, inbox):
        (inbox / "mission.yml").write_text(_MISSION_YAML)
        graph.cfg.mission_compiler_enabled = True
        _captured = []
        graph.add_task = lambda t: _captured.append(dict(t))
        graph.get_next_queued_task = lambda: _captured[0] if _captured else None
        graph.update_task_branch = lambda *a, **k: None
        try:
            state = _make_state(stop_reason="no_queued_tasks")
            out = graph.compile_mission_if_needed(state)
            assert out.stop_reason is None, "stop_reason should be cleared after compile"
        finally:
            from tools import task_tools
            graph.get_next_queued_task = task_tools.get_next_queued_task
            graph.update_task_branch = task_tools.update_task_branch
    _with_temp_runner_dir(body)


def test_node_sets_current_task_on_state():
    def body(outbox, inbox):
        (inbox / "mission.yml").write_text(_MISSION_YAML)
        graph.cfg.mission_compiler_enabled = True
        _captured = []
        graph.add_task = lambda t: _captured.append(dict(t))
        graph.get_next_queued_task = lambda: _captured[0] if _captured else None
        graph.update_task_branch = lambda *a, **k: None
        try:
            out = graph.compile_mission_if_needed(_make_state())
            assert out.current_task is not None
            assert out.current_task["title"] == "Write tests"
            assert out.current_task_id == out.current_task["id"]
        finally:
            from tools import task_tools
            graph.get_next_queued_task = task_tools.get_next_queued_task
            graph.update_task_branch = task_tools.update_task_branch
    _with_temp_runner_dir(body)


def test_node_summary_idempotent():
    def body(outbox, inbox):
        (inbox / "mission.yml").write_text(_MISSION_YAML)
        graph.cfg.mission_compiler_enabled = True
        # Pre-create the summary file with sentinel content.
        summary_path = outbox / "mission_mission_compiled.txt"
        summary_path.write_text("ORIGINAL")
        _captured = []
        graph.add_task = lambda t: _captured.append(dict(t))
        graph.get_next_queued_task = lambda: _captured[0] if _captured else None
        graph.update_task_branch = lambda *a, **k: None
        try:
            graph.compile_mission_if_needed(_make_state())
            assert summary_path.read_text() == "ORIGINAL", "summary file must not be overwritten"
        finally:
            from tools import task_tools
            graph.get_next_queued_task = task_tools.get_next_queued_task
            graph.update_task_branch = task_tools.update_task_branch
    _with_temp_runner_dir(body)


def test_node_handles_invalid_yaml():
    def body(outbox, inbox):
        (inbox / "bad.yml").write_text("- item1\n- item2\n")  # list, not mapping
        graph.cfg.mission_compiler_enabled = True
        _captured = []
        graph.add_task = lambda t: _captured.append(t)
        out = graph.compile_mission_if_needed(_make_state())
        assert out.mission_compiled is None, "invalid YAML should be skipped gracefully"
        assert _captured == []
    _with_temp_runner_dir(body)


def test_node_handles_validation_errors():
    def body(outbox, inbox):
        # Valid YAML but fails validation: no 'name'.
        (inbox / "invalid.yml").write_text("tasks:\n  - title: Something\n")
        graph.cfg.mission_compiler_enabled = True
        _captured = []
        graph.add_task = lambda t: _captured.append(t)
        out = graph.compile_mission_if_needed(_make_state())
        assert out.mission_compiled is None, "validation failure should be skipped gracefully"
        assert _captured == []
    _with_temp_runner_dir(body)


def test_node_picks_first_yaml_file():
    """When multiple .yml files are present the compiler picks the first (sorted)."""
    def body(outbox, inbox):
        (inbox / "aaa.yml").write_text(_MISSION_YAML)
        (inbox / "zzz.yml").write_text(_MISSION_YAML.replace("Test Mission", "Other Mission"))
        graph.cfg.mission_compiler_enabled = True
        _captured = []
        graph.add_task = lambda t: _captured.append(dict(t))
        graph.get_next_queued_task = lambda: _captured[0] if _captured else None
        graph.update_task_branch = lambda *a, **k: None
        try:
            out = graph.compile_mission_if_needed(_make_state())
            assert out.mission_name == "Test Mission", "should pick first (sorted) .yml file"
        finally:
            from tools import task_tools
            graph.get_next_queued_task = task_tools.get_next_queued_task
            graph.update_task_branch = task_tools.update_task_branch
    _with_temp_runner_dir(body)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def test_route_load_no_task_to_compile():
    s = RunnerState(stop_reason="no_queued_tasks")
    assert graph._route_after_load(s) == "compile_mission_if_needed"


def test_route_load_with_task_to_choose_worker():
    s = RunnerState(current_task={"id": "t1", "title": "T"}, stop_reason=None)
    assert graph._route_after_load(s) == "choose_worker"


def test_route_compile_with_task_to_choose_worker():
    s = RunnerState(current_task={"id": "t1", "title": "T"})
    assert graph._route_after_compile_mission(s) == "choose_worker"


def test_route_compile_no_task_to_chatgpt():
    s = RunnerState(current_task=None)
    assert graph._route_after_compile_mission(s) == "ask_chatgpt_for_task_if_needed"


def test_node_is_wired_into_graph():
    nodes = list(graph.build_graph().get_graph().nodes)
    assert "compile_mission_if_needed" in nodes, nodes


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_slug_basic,
        test_slug_strips_special_chars,
        test_slug_respects_max_len,
        test_slug_collapses_spaces,
        test_slug_handles_underscores,
        test_parse_mission_file_valid,
        test_parse_mission_file_not_mapping,
        test_parse_mission_file_missing_raises,
        test_validate_mission_valid,
        test_validate_mission_no_name,
        test_validate_mission_empty_name,
        test_validate_mission_no_tasks,
        test_validate_mission_empty_tasks,
        test_validate_mission_task_no_title,
        test_validate_mission_non_list_tasks,
        test_compile_mission_basic,
        test_compile_mission_auto_branch,
        test_compile_mission_custom_branch,
        test_compile_mission_auto_task_id,
        test_compile_mission_custom_task_id,
        test_compile_mission_unknown_type_defaults_to_general,
        test_compile_mission_preferred_worker_included,
        test_compile_mission_no_preferred_worker_excluded,
        test_compile_mission_multiple_tasks,
        test_compile_mission_valid_types_preserved,
        test_format_mission_summary_includes_name,
        test_format_mission_summary_with_goal,
        test_format_mission_summary_no_goal_section,
        test_format_mission_summary_task_count,
        test_format_mission_summary_lists_tasks,
        test_format_mission_summary_shows_preferred_worker,
        test_node_disabled_by_config,
        test_node_no_mission_file,
        test_node_compiles_and_queues_tasks,
        test_node_renames_processed_file,
        test_node_writes_summary_to_outbox,
        test_node_clears_stop_reason_on_compile,
        test_node_sets_current_task_on_state,
        test_node_summary_idempotent,
        test_node_handles_invalid_yaml,
        test_node_handles_validation_errors,
        test_node_picks_first_yaml_file,
        test_route_load_no_task_to_compile,
        test_route_load_with_task_to_choose_worker,
        test_route_compile_with_task_to_choose_worker,
        test_route_compile_no_task_to_chatgpt,
        test_node_is_wired_into_graph,
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
