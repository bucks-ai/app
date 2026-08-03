"""Unit tests for Codex-to-Claude repair escalation.

Covers:
- should_escalate: all skip conditions (wrong worker, success, usage-limit error).
- build_repair_prompt: structure, content, truncation.
- Graph node: enabled/disabled config, escalation success/failure paths.
- Config field and state field present.
"""
import os
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.codex_to_claude_escalation import should_escalate, build_repair_prompt

# Silence log_event during tests.
import tools.codex_to_claude_escalation as _esc_module
# The module doesn't call log_event itself; log_event is called in graph.py nodes.


# ---------------------------------------------------------------------------
# should_escalate
# ---------------------------------------------------------------------------

def test_escalate_codex_failure():
    result = {"success": False, "worker": "codex", "error": "codex crashed"}
    assert should_escalate(result, "codex") is True


def test_no_escalate_wrong_worker():
    result = {"success": False, "worker": "claude", "error": "error"}
    assert should_escalate(result, "claude") is False


def test_no_escalate_on_success():
    result = {"success": True, "worker": "codex"}
    assert should_escalate(result, "codex") is False


def test_no_escalate_usage_limit_429():
    result = {"success": False, "worker": "codex", "error": "HTTP 429 rate limit exceeded"}
    assert should_escalate(result, "codex") is False


def test_no_escalate_usage_limit_quota():
    result = {"success": False, "worker": "codex", "error": "insufficient_quota error from OpenAI"}
    assert should_escalate(result, "codex") is False


def test_no_escalate_usage_limit_monthly():
    result = {"success": False, "worker": "codex", "error": "monthly limit reached"}
    assert should_escalate(result, "codex") is False


def test_no_escalate_empty_worker():
    result = {"success": False, "error": "error"}
    assert should_escalate(result, "") is False


def test_escalate_codex_no_output():
    result = {"success": False, "worker": "codex", "error": None, "output": None}
    assert should_escalate(result, "codex") is True


# ---------------------------------------------------------------------------
# build_repair_prompt
# ---------------------------------------------------------------------------

def test_repair_prompt_contains_original():
    original = "Build a login page with React."
    codex_result = {"error": "codex timed out", "output": ""}
    prompt = build_repair_prompt(original, codex_result, {"id": "t-001"})
    assert "Build a login page with React." in prompt


def test_repair_prompt_contains_error():
    original = "Some task."
    codex_result = {"error": "segfault in codex", "output": ""}
    prompt = build_repair_prompt(original, codex_result, {})
    assert "segfault in codex" in prompt


def test_repair_prompt_contains_partial_output():
    original = "Some task."
    codex_result = {"error": "", "output": "partial result here"}
    prompt = build_repair_prompt(original, codex_result, {})
    assert "partial result here" in prompt


def test_repair_prompt_truncates_long_output():
    original = "Task."
    long_output = "x" * 5000
    codex_result = {"error": "", "output": long_output}
    prompt = build_repair_prompt(original, codex_result, {})
    assert len(prompt) < len(long_output) + 500  # truncated
    assert "truncated" in prompt


def test_repair_prompt_no_output_section():
    original = "Task."
    codex_result = {"error": "crash", "output": ""}
    prompt = build_repair_prompt(original, codex_result, {})
    assert "partial output" not in prompt


def test_repair_prompt_no_error_fallback():
    original = "Task."
    codex_result = {"error": None, "output": None}
    prompt = build_repair_prompt(original, codex_result, {})
    assert "Codex returned no output." in prompt


# ---------------------------------------------------------------------------
# Config field
# ---------------------------------------------------------------------------

def test_config_field_defaults_true():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert cfg.codex_to_claude_escalation_enabled is True


def test_config_field_env_override(monkeypatch=None):
    import importlib
    original = os.environ.get("CODEX_TO_CLAUDE_ESCALATION_ENABLED")
    try:
        os.environ["CODEX_TO_CLAUDE_ESCALATION_ENABLED"] = "false"
        import config as _cfg_module
        _cfg_module._config = None  # reset singleton
        cfg = _cfg_module.get_config()
        assert cfg.codex_to_claude_escalation_enabled is False
    finally:
        if original is None:
            os.environ.pop("CODEX_TO_CLAUDE_ESCALATION_ENABLED", None)
        else:
            os.environ["CODEX_TO_CLAUDE_ESCALATION_ENABLED"] = original
        import config as _cfg_module
        _cfg_module._config = None  # reset singleton


# ---------------------------------------------------------------------------
# State field
# ---------------------------------------------------------------------------

def test_state_has_codex_escalation_status():
    from state import RunnerState
    s = RunnerState()
    assert s.codex_escalation_status is None


# ---------------------------------------------------------------------------
# Graph node: escalate_to_claude_if_needed
# ---------------------------------------------------------------------------

def _make_state(**kwargs):
    from state import RunnerState
    defaults = {
        "current_worker": "codex",
        "current_task_id": "t-001",
        "current_task": {"id": "t-001", "title": "Test task", "type": "ui"},
        "worker_result": {
            "success": False,
            "worker": "codex",
            "error": "codex crashed",
            "output": None,
            "mode": "cli",
            "prompt_written": False,
            "prompt_path": None,
            "response_path": None,
            "api_cost": None,
            "tokens_used": None,
        },
        "messages": [{"role": "user", "content": "Original prompt."}],
        "resolved_model": None,
    }
    defaults.update(kwargs)
    return RunnerState(**defaults)


def test_node_skipped_when_disabled():
    import graph as g
    state = _make_state()

    with mock.patch.object(g.cfg, "codex_to_claude_escalation_enabled", False):
        result = g.escalate_to_claude_if_needed(state)

    assert result.codex_escalation_status is None
    assert result.current_worker == "codex"


def test_node_skipped_for_success():
    import graph as g
    state = _make_state(worker_result={
        "success": True, "worker": "codex", "error": None, "output": "ok",
        "mode": "cli", "prompt_written": False, "prompt_path": None,
        "response_path": None, "api_cost": None, "tokens_used": None,
    })

    with mock.patch.object(g.cfg, "codex_to_claude_escalation_enabled", True):
        result = g.escalate_to_claude_if_needed(state)

    assert result.codex_escalation_status is None


def test_node_escalation_success():
    import graph as g
    from state import WorkerResult
    state = _make_state()

    successful_repair = WorkerResult(
        worker="claude",
        mode="cli",
        success=True,
        output="Claude completed the task.\n- Check Result: pass",
    )

    with mock.patch.object(g.cfg, "codex_to_claude_escalation_enabled", True), \
         mock.patch("graph.ClaudeWorker") as MockClaude, \
         mock.patch("graph._persist", side_effect=lambda s, _: s), \
         mock.patch("graph.log_event"):
        MockClaude.return_value.run_worker_prompt.return_value = successful_repair
        result = g.escalate_to_claude_if_needed(state)

    assert result.codex_escalation_status == "succeeded"
    assert result.current_worker == "claude"
    assert result.worker_result["success"] is True
    assert result.worker_result["worker"] == "claude"


def test_node_escalation_failure():
    import graph as g
    from state import WorkerResult
    state = _make_state()

    failed_repair = WorkerResult(
        worker="claude",
        mode="cli",
        success=False,
        error="claude also failed",
    )

    with mock.patch.object(g.cfg, "codex_to_claude_escalation_enabled", True), \
         mock.patch("graph.ClaudeWorker") as MockClaude, \
         mock.patch("graph._persist", side_effect=lambda s, _: s), \
         mock.patch("graph.log_event"):
        MockClaude.return_value.run_worker_prompt.return_value = failed_repair
        result = g.escalate_to_claude_if_needed(state)

    assert result.codex_escalation_status == "failed"
    assert result.current_worker == "codex"  # unchanged
    assert result.worker_result["success"] is False  # original failure preserved


def test_node_skipped_for_usage_limit():
    import graph as g
    state = _make_state(worker_result={
        "success": False, "worker": "codex",
        "error": "429 rate limit exceeded",
        "output": None, "mode": "cli", "prompt_written": False,
        "prompt_path": None, "response_path": None, "api_cost": None, "tokens_used": None,
    })

    with mock.patch.object(g.cfg, "codex_to_claude_escalation_enabled", True), \
         mock.patch("graph.log_event"):
        result = g.escalate_to_claude_if_needed(state)

    assert result.codex_escalation_status is None
    assert result.current_worker == "codex"


# ---------------------------------------------------------------------------
# Graph wiring sanity check
# ---------------------------------------------------------------------------

def test_graph_imports_escalation():
    import graph
    assert hasattr(graph, "escalate_to_claude_if_needed")
    assert hasattr(graph, "should_escalate")
    assert hasattr(graph, "build_repair_prompt")
