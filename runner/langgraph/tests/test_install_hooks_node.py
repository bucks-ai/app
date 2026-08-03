"""Tests for the graph.install_hooks startup node."""
import json
import os
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import graph
from state import RunnerState

# Silence flight recorder and disk persistence during tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None


def _state(**kwargs) -> RunnerState:
    return RunnerState(**kwargs)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _settings_path(tmp_path: str) -> Path:
    return Path(tmp_path) / ".claude" / "settings.json"


def _run_node(tmp_path: str, *, enabled: bool = True, auto_install: bool = True) -> RunnerState:
    original_enabled = graph.cfg.claude_hooks_safety_pack_enabled
    original_auto = graph.cfg.claude_hooks_safety_pack_auto_install
    original_repo = graph.cfg.repo_path
    try:
        graph.cfg.claude_hooks_safety_pack_enabled = enabled
        graph.cfg.claude_hooks_safety_pack_auto_install = auto_install
        graph.cfg.repo_path = tmp_path
        return graph.install_hooks(_state())
    finally:
        graph.cfg.claude_hooks_safety_pack_enabled = original_enabled
        graph.cfg.claude_hooks_safety_pack_auto_install = original_auto
        graph.cfg.repo_path = original_repo


# ---------------------------------------------------------------------------
# Node writes hooks when enabled
# ---------------------------------------------------------------------------

def test_install_hooks_writes_settings_file():
    with tempfile.TemporaryDirectory() as tmp:
        _run_node(tmp)
        assert _settings_path(tmp).exists()


def test_install_hooks_creates_valid_json():
    with tempfile.TemporaryDirectory() as tmp:
        _run_node(tmp)
        data = json.loads(_settings_path(tmp).read_text())
        assert "hooks" in data
        assert "PreToolUse" in data["hooks"]


def test_install_hooks_installs_bash_write_edit_matchers():
    with tempfile.TemporaryDirectory() as tmp:
        _run_node(tmp)
        data = json.loads(_settings_path(tmp).read_text())
        matchers = {e.get("matcher") for e in data["hooks"]["PreToolUse"]}
        assert "Bash" in matchers
        assert "Write" in matchers
        assert "Edit" in matchers


def test_install_hooks_sets_last_completed_step():
    with tempfile.TemporaryDirectory() as tmp:
        state = _run_node(tmp)
        assert state.last_completed_step == "install_hooks"


# ---------------------------------------------------------------------------
# Node is a no-op when disabled
# ---------------------------------------------------------------------------

def test_install_hooks_skips_when_pack_disabled():
    with tempfile.TemporaryDirectory() as tmp:
        state = _run_node(tmp, enabled=False)
        assert not _settings_path(tmp).exists()
        assert state.last_completed_step is None


def test_install_hooks_skips_when_auto_install_off():
    with tempfile.TemporaryDirectory() as tmp:
        state = _run_node(tmp, auto_install=False)
        assert not _settings_path(tmp).exists()
        assert state.last_completed_step is None


# ---------------------------------------------------------------------------
# Idempotency
# ---------------------------------------------------------------------------

def test_install_hooks_is_idempotent():
    with tempfile.TemporaryDirectory() as tmp:
        _run_node(tmp)
        _run_node(tmp)
        data = json.loads(_settings_path(tmp).read_text())
        pre_tool = data["hooks"]["PreToolUse"]
        matchers = [e.get("matcher") for e in pre_tool]
        assert matchers.count("Bash") == 1
        assert matchers.count("Write") == 1
        assert matchers.count("Edit") == 1


# ---------------------------------------------------------------------------
# Graph structure
# ---------------------------------------------------------------------------

def test_install_hooks_node_present_in_graph():
    assert "install_hooks" in graph.graph.nodes


def test_install_hooks_node_is_entry_point():
    # Verify __start__ → install_hooks → check_launch_readiness_if_needed via the drawable graph edges
    edges = [(e.source, e.target) for e in graph.graph.get_graph().edges]
    assert ("__start__", "install_hooks") in edges
    assert ("install_hooks", "check_launch_readiness_if_needed") in edges


if __name__ == "__main__":
    import traceback
    tests = [
        test_install_hooks_writes_settings_file,
        test_install_hooks_creates_valid_json,
        test_install_hooks_installs_bash_write_edit_matchers,
        test_install_hooks_sets_last_completed_step,
        test_install_hooks_skips_when_pack_disabled,
        test_install_hooks_skips_when_auto_install_off,
        test_install_hooks_is_idempotent,
        test_install_hooks_node_present_in_graph,
        test_install_hooks_node_is_entry_point,
    ]
    passed = failed = 0
    for fn in tests:
        try:
            fn()
            print(f"  PASS  {fn.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {fn.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
