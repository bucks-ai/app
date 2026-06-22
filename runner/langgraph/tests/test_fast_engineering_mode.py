"""Tests for tools/fast_engineering_mode.py."""
import sys
import os
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))
from tools.fast_engineering_mode import (
    is_fast_engineering_task,
    build_engineering_context,
    format_engineering_injection,
)


# ---------------------------------------------------------------------------
# is_fast_engineering_task
# ---------------------------------------------------------------------------

class TestIsFastEngineeringTask:
    def test_agent_type_matches(self):
        assert is_fast_engineering_task({"type": "agent", "title": "something"})

    def test_runner_type_matches(self):
        assert is_fast_engineering_task({"type": "runner", "title": "something"})

    def test_backend_type_matches(self):
        assert is_fast_engineering_task({"type": "backend", "title": "something"})

    def test_langgraph_keyword_in_title(self):
        assert is_fast_engineering_task({"type": "general", "title": "Add LangGraph node"})

    def test_guard_keyword_in_title(self):
        assert is_fast_engineering_task({"type": "general", "title": "Fix the guard"})

    def test_runner_keyword_in_description(self):
        task = {"type": "general", "title": "Fix bug", "description": "Update runner loop"}
        assert is_fast_engineering_task(task)

    def test_ui_type_does_not_match(self):
        assert not is_fast_engineering_task({"type": "ui", "title": "Button polish"})

    def test_empty_task_does_not_match(self):
        assert not is_fast_engineering_task({})

    def test_design_task_does_not_match(self):
        assert not is_fast_engineering_task({"type": "design", "title": "Layout update"})

    def test_engineering_keyword_in_title(self):
        assert is_fast_engineering_task({"type": "general", "title": "Fast engineering mode"})

    def test_node_keyword_in_title(self):
        assert is_fast_engineering_task({"type": "general", "title": "Add new graph node"})


# ---------------------------------------------------------------------------
# build_engineering_context
# ---------------------------------------------------------------------------

class TestBuildEngineeringContext:
    def test_returns_required_keys(self, tmp_path):
        ctx = build_engineering_context(str(tmp_path))
        assert "runner_dir" in ctx
        assert "nodes" in ctx
        assert "tools" in ctx
        assert "tests" in ctx

    def test_empty_dir_returns_empty_lists(self, tmp_path):
        ctx = build_engineering_context(str(tmp_path))
        assert ctx["nodes"] == []
        assert ctx["tools"] == []
        assert ctx["tests"] == []

    def test_tools_dir_scanned(self, tmp_path):
        tools = tmp_path / "tools"
        tools.mkdir()
        (tools / "my_tool.py").write_text("# tool")
        (tools / "__init__.py").write_text("")
        ctx = build_engineering_context(str(tmp_path))
        assert "my_tool" in ctx["tools"]
        assert "__init__" not in ctx["tools"]

    def test_tests_dir_scanned(self, tmp_path):
        tests = tmp_path / "tests"
        tests.mkdir()
        (tests / "test_my_tool.py").write_text("# test")
        (tests / "conftest.py").write_text("")
        ctx = build_engineering_context(str(tmp_path))
        assert "test_my_tool" in ctx["tests"]
        assert "conftest" not in ctx["tests"]

    def test_graph_nodes_parsed(self, tmp_path):
        graph_text = '''
builder.add_node("load_next_task", load_next_task)
builder.add_node("dispatch_worker", dispatch_worker)
some_other_line = True
'''
        (tmp_path / "graph.py").write_text(graph_text)
        ctx = build_engineering_context(str(tmp_path))
        assert "load_next_task" in ctx["nodes"]
        assert "dispatch_worker" in ctx["nodes"]

    def test_tools_sorted(self, tmp_path):
        tools = tmp_path / "tools"
        tools.mkdir()
        for name in ["zebra.py", "alpha.py", "middle.py"]:
            (tools / name).write_text("")
        ctx = build_engineering_context(str(tmp_path))
        assert ctx["tools"] == sorted(ctx["tools"])

    def test_runner_dir_field_matches(self, tmp_path):
        ctx = build_engineering_context(str(tmp_path))
        assert ctx["runner_dir"] == str(tmp_path)

    def test_real_runner_dir_has_tools_and_tests(self):
        runner_dir = str(Path(__file__).parent.parent)
        ctx = build_engineering_context(runner_dir)
        assert len(ctx["tools"]) > 0
        assert len(ctx["tests"]) > 0
        assert len(ctx["nodes"]) > 0

    def test_real_runner_dir_includes_known_tool(self):
        runner_dir = str(Path(__file__).parent.parent)
        ctx = build_engineering_context(runner_dir)
        assert "fast_engineering_mode" in ctx["tools"]

    def test_real_runner_dir_includes_this_test(self):
        runner_dir = str(Path(__file__).parent.parent)
        ctx = build_engineering_context(runner_dir)
        assert "test_fast_engineering_mode" in ctx["tests"]


# ---------------------------------------------------------------------------
# format_engineering_injection
# ---------------------------------------------------------------------------

class TestFormatEngineeringInjection:
    def test_returns_string(self):
        ctx = {"nodes": ["n1"], "tools": ["t1"], "tests": ["test_t1"]}
        result = format_engineering_injection(ctx)
        assert isinstance(result, str)

    def test_empty_context_returns_empty_string(self):
        ctx = {"nodes": [], "tools": [], "tests": []}
        assert format_engineering_injection(ctx) == ""

    def test_missing_keys_returns_empty_string(self):
        assert format_engineering_injection({}) == ""

    def test_contains_nodes(self):
        ctx = {"nodes": ["load_next_task", "dispatch_worker"], "tools": [], "tests": []}
        result = format_engineering_injection(ctx)
        assert "load_next_task" in result
        assert "dispatch_worker" in result

    def test_contains_tools(self):
        ctx = {"nodes": [], "tools": ["git_tools", "log_tools"], "tests": []}
        result = format_engineering_injection(ctx)
        assert "git_tools" in result
        assert "log_tools" in result

    def test_contains_tests(self):
        ctx = {"nodes": [], "tools": [], "tests": ["test_git_tools"]}
        result = format_engineering_injection(ctx)
        assert "test_git_tools" in result

    def test_contains_architecture_invariants(self):
        ctx = {"nodes": ["n"], "tools": ["t"], "tests": ["test_t"]}
        result = format_engineering_injection(ctx)
        assert "_persist" in result
        assert "log_event" in result
        assert "RunnerState" in result

    def test_header_present(self):
        ctx = {"nodes": ["n"], "tools": ["t"], "tests": ["test_t"]}
        result = format_engineering_injection(ctx)
        assert "Fast Engineering Mode" in result

    def test_ends_with_newline(self):
        ctx = {"nodes": ["n"], "tools": ["t"], "tests": ["test_t"]}
        result = format_engineering_injection(ctx)
        assert result.endswith("\n")

    def test_partial_context_nodes_only(self):
        ctx = {"nodes": ["my_node"], "tools": [], "tests": []}
        result = format_engineering_injection(ctx)
        assert "my_node" in result
