"""Unit tests for Auto-Repair Loop v2.

Covers:
- should_auto_repair: all skip conditions (worker failed, checks passed,
  attempts exhausted) and the happy path.
- build_auto_repair_prompt: structure, content, truncation.
- Graph node: enabled/disabled config, single repair success, repair worker
  failure, exhausted attempts, check-still-failing-after-repair paths.
- Config fields default to expected values.
- State fields present and reset correctly.
"""
import os
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.auto_repair_loop import should_auto_repair, build_auto_repair_prompt


# ---------------------------------------------------------------------------
# should_auto_repair
# ---------------------------------------------------------------------------

def test_should_repair_when_check_failed():
    result = {"success": True}
    assert should_auto_repair(result, False, 0, 2) is True


def test_no_repair_when_worker_failed():
    result = {"success": False, "error": "crash"}
    assert should_auto_repair(result, False, 0, 2) is False


def test_no_repair_when_check_passed():
    result = {"success": True}
    assert should_auto_repair(result, True, 0, 2) is False


def test_no_repair_when_check_passed_none():
    # check_passed=None means checks haven't run (e.g. worker failed); no repair
    result = {"success": False}
    assert should_auto_repair(result, None, 0, 2) is False


def test_no_repair_when_attempts_exhausted():
    result = {"success": True}
    assert should_auto_repair(result, False, 2, 2) is False


def test_no_repair_when_attempts_exceed_max():
    result = {"success": True}
    assert should_auto_repair(result, False, 3, 2) is False


def test_repair_allowed_at_first_attempt():
    result = {"success": True}
    assert should_auto_repair(result, False, 0, 1) is True


def test_no_repair_at_max_with_max_one():
    result = {"success": True}
    assert should_auto_repair(result, False, 1, 1) is False


# ---------------------------------------------------------------------------
# build_auto_repair_prompt
# ---------------------------------------------------------------------------

def test_prompt_contains_original():
    original = "Build a REST endpoint."
    prompt = build_auto_repair_prompt(original, "FAILED: test_foo", {}, 1, 2)
    assert "Build a REST endpoint." in prompt


def test_prompt_contains_check_output():
    prompt = build_auto_repair_prompt("task", "AssertionError: test_bar failed", {}, 1, 2)
    assert "AssertionError: test_bar failed" in prompt


def test_prompt_contains_attempt_count():
    prompt = build_auto_repair_prompt("task", "error", {}, 1, 2)
    assert "1 of 2" in prompt


def test_prompt_truncates_long_output():
    long_output = "x" * 5000
    prompt = build_auto_repair_prompt("task", long_output, {}, 1, 2)
    assert len(prompt) < len(long_output) + 500
    assert "truncated" in prompt


def test_prompt_no_truncation_for_short_output():
    short_output = "short error"
    prompt = build_auto_repair_prompt("task", short_output, {}, 1, 2)
    assert "truncated" not in prompt
    assert "short error" in prompt


# ---------------------------------------------------------------------------
# Config fields
# ---------------------------------------------------------------------------

def test_config_auto_repair_enabled_default():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert cfg.auto_repair_loop_enabled is True


def test_config_max_auto_repair_attempts_default():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert cfg.max_auto_repair_attempts == 2


def test_config_env_override_disabled():
    original = os.environ.get("AUTO_REPAIR_LOOP_ENABLED")
    try:
        os.environ["AUTO_REPAIR_LOOP_ENABLED"] = "false"
        import config as _cfg_module
        _cfg_module._config = None
        cfg = _cfg_module.get_config()
        assert cfg.auto_repair_loop_enabled is False
    finally:
        if original is None:
            os.environ.pop("AUTO_REPAIR_LOOP_ENABLED", None)
        else:
            os.environ["AUTO_REPAIR_LOOP_ENABLED"] = original
        import config as _cfg_module
        _cfg_module._config = None


def test_config_env_override_max_attempts():
    original = os.environ.get("MAX_AUTO_REPAIR_ATTEMPTS")
    try:
        os.environ["MAX_AUTO_REPAIR_ATTEMPTS"] = "5"
        import config as _cfg_module
        _cfg_module._config = None
        cfg = _cfg_module.get_config()
        assert cfg.max_auto_repair_attempts == 5
    finally:
        if original is None:
            os.environ.pop("MAX_AUTO_REPAIR_ATTEMPTS", None)
        else:
            os.environ["MAX_AUTO_REPAIR_ATTEMPTS"] = original
        import config as _cfg_module
        _cfg_module._config = None


# ---------------------------------------------------------------------------
# State fields
# ---------------------------------------------------------------------------

def test_state_auto_repair_fields_present():
    from state import RunnerState
    s = RunnerState()
    assert s.auto_repair_attempt == 0
    assert s.auto_repair_status is None
    assert s.check_output is None


# ---------------------------------------------------------------------------
# Graph node helpers
# ---------------------------------------------------------------------------

def _make_state(**kwargs):
    from state import RunnerState
    defaults = {
        "current_worker": "claude",
        "current_task_id": "t-001",
        "current_task": {"id": "t-001", "title": "Test task", "type": "backend"},
        "worker_result": {
            "success": True,
            "worker": "claude",
            "error": None,
            "output": "- Check Result: fail",
            "mode": "cli",
            "prompt_written": False,
            "prompt_path": None,
            "response_path": None,
            "api_cost": None,
            "tokens_used": None,
        },
        "check_passed": False,
        "check_output": "FAILED tests/test_foo.py::test_bar",
        "messages": [{"role": "user", "content": "Original task prompt."}],
        "resolved_model": None,
        "auto_repair_attempt": 0,
        "auto_repair_status": None,
    }
    defaults.update(kwargs)
    return RunnerState(**defaults)


# ---------------------------------------------------------------------------
# Graph node: auto_repair_if_needed
# ---------------------------------------------------------------------------

def test_node_skipped_when_disabled():
    import graph as g
    state = _make_state()
    with mock.patch.object(g.cfg, "auto_repair_loop_enabled", False):
        result = g.auto_repair_if_needed(state)
    assert result.auto_repair_status is None
    assert result.auto_repair_attempt == 0


def test_node_skipped_when_check_passed():
    import graph as g
    state = _make_state(check_passed=True)
    with mock.patch.object(g.cfg, "auto_repair_loop_enabled", True), \
         mock.patch("graph._persist", side_effect=lambda s, _: s):
        result = g.auto_repair_if_needed(state)
    assert result.auto_repair_status is None
    assert result.auto_repair_attempt == 0


def test_node_skipped_when_worker_failed():
    import graph as g
    state = _make_state(worker_result={
        "success": False, "worker": "claude", "error": "crash", "output": None,
        "mode": "cli", "prompt_written": False, "prompt_path": None,
        "response_path": None, "api_cost": None, "tokens_used": None,
    }, check_passed=None)
    with mock.patch.object(g.cfg, "auto_repair_loop_enabled", True), \
         mock.patch("graph._persist", side_effect=lambda s, _: s):
        result = g.auto_repair_if_needed(state)
    assert result.auto_repair_status is None
    assert result.auto_repair_attempt == 0


def test_node_repair_succeeds_on_first_attempt():
    import graph as g
    from state import WorkerResult
    state = _make_state()

    repaired = WorkerResult(
        worker="claude", mode="cli", success=True,
        output="- Check Result: pass",
    )

    with mock.patch.object(g.cfg, "auto_repair_loop_enabled", True), \
         mock.patch.object(g.cfg, "max_auto_repair_attempts", 2), \
         mock.patch("graph.ClaudeWorker") as MockClaude, \
         mock.patch("graph.run_check", return_value={"success": True, "output": "OK"}), \
         mock.patch("graph._persist", side_effect=lambda s, _: s), \
         mock.patch("graph.log_event"):
        MockClaude.return_value.run_worker_prompt.return_value = repaired
        result = g.auto_repair_if_needed(state)

    assert result.auto_repair_status == "succeeded"
    assert result.auto_repair_attempt == 1
    assert result.check_passed is True
    assert result.worker_result["success"] is True


def test_node_repair_worker_fails():
    import graph as g
    from state import WorkerResult
    state = _make_state()

    failed = WorkerResult(
        worker="claude", mode="cli", success=False, error="repair crash",
    )

    with mock.patch.object(g.cfg, "auto_repair_loop_enabled", True), \
         mock.patch.object(g.cfg, "max_auto_repair_attempts", 2), \
         mock.patch("graph.ClaudeWorker") as MockClaude, \
         mock.patch("graph._persist", side_effect=lambda s, _: s), \
         mock.patch("graph.log_event"):
        MockClaude.return_value.run_worker_prompt.return_value = failed
        result = g.auto_repair_if_needed(state)

    assert result.auto_repair_status == "failed"
    assert result.auto_repair_attempt == 1
    assert result.check_passed is False


def test_node_repair_check_still_fails_exhausts_attempts():
    import graph as g
    from state import WorkerResult
    state = _make_state()

    repaired = WorkerResult(
        worker="claude", mode="cli", success=True,
        output="- Check Result: fail",
    )

    with mock.patch.object(g.cfg, "auto_repair_loop_enabled", True), \
         mock.patch.object(g.cfg, "max_auto_repair_attempts", 2), \
         mock.patch("graph.ClaudeWorker") as MockClaude, \
         mock.patch("graph.run_check", return_value={"success": False, "output": "STILL FAILING"}), \
         mock.patch("graph._persist", side_effect=lambda s, _: s), \
         mock.patch("graph.log_event"):
        MockClaude.return_value.run_worker_prompt.return_value = repaired
        result = g.auto_repair_if_needed(state)

    # Both attempts used, check still failing → failed
    assert result.auto_repair_status == "failed"
    assert result.auto_repair_attempt == 2
    assert result.check_passed is False


def test_node_repair_succeeds_on_second_attempt():
    import graph as g
    from state import WorkerResult
    state = _make_state()

    repaired = WorkerResult(
        worker="claude", mode="cli", success=True,
        output="- Check Result: pass",
    )

    check_calls = [
        {"success": False, "output": "STILL FAILING"},
        {"success": True, "output": "OK"},
    ]

    with mock.patch.object(g.cfg, "auto_repair_loop_enabled", True), \
         mock.patch.object(g.cfg, "max_auto_repair_attempts", 2), \
         mock.patch("graph.ClaudeWorker") as MockClaude, \
         mock.patch("graph.run_check", side_effect=check_calls), \
         mock.patch("graph._persist", side_effect=lambda s, _: s), \
         mock.patch("graph.log_event"):
        MockClaude.return_value.run_worker_prompt.return_value = repaired
        result = g.auto_repair_if_needed(state)

    assert result.auto_repair_status == "succeeded"
    assert result.auto_repair_attempt == 2
    assert result.check_passed is True


def test_node_uses_codex_worker_when_current_worker_is_codex():
    import graph as g
    from state import WorkerResult
    state = _make_state(current_worker="codex", worker_result={
        "success": True, "worker": "codex", "error": None,
        "output": "- Check Result: fail",
        "mode": "cli", "prompt_written": False, "prompt_path": None,
        "response_path": None, "api_cost": None, "tokens_used": None,
    })

    repaired = WorkerResult(worker="codex", mode="cli", success=False, error="codex repair fail")

    with mock.patch.object(g.cfg, "auto_repair_loop_enabled", True), \
         mock.patch.object(g.cfg, "max_auto_repair_attempts", 1), \
         mock.patch("graph.CodexWorker") as MockCodex, \
         mock.patch("graph._persist", side_effect=lambda s, _: s), \
         mock.patch("graph.log_event"):
        MockCodex.return_value.run_worker_prompt.return_value = repaired
        result = g.auto_repair_if_needed(state)

    MockCodex.assert_called_once()
    assert result.auto_repair_status == "failed"


# ---------------------------------------------------------------------------
# update_logs_and_state clears repair fields
# ---------------------------------------------------------------------------

def test_update_logs_clears_auto_repair_fields():
    import graph as g
    state = _make_state(
        worker_result={
            "success": True, "worker": "claude", "error": None,
            "output": "- Check Result: pass",
            "mode": "cli", "prompt_written": False, "prompt_path": None,
            "response_path": None, "api_cost": None, "tokens_used": None,
        },
        check_passed=True,
        auto_repair_attempt=1,
        auto_repair_status="succeeded",
        check_output="check output was here",
    )

    with mock.patch("graph.mark_task_complete"), \
         mock.patch("graph.log_event"), \
         mock.patch("graph._persist", side_effect=lambda s, _: s), \
         mock.patch("graph.evaluate_failure", return_value={
             "action": "pass", "consecutive_failures": 0,
             "circuit_open": False, "retry_count": 0,
         }), \
         mock.patch("graph.evaluate_error_repetition", return_value={
             "blocked": False, "match_count": 0, "stop_reason": None,
         }), \
         mock.patch("graph.evaluate_task_repetition", return_value={
             "blocked": False, "attempt_count": 1, "stop_reason": None,
         }), \
         mock.patch("graph.evaluate_cost_budget", return_value={
             "blocked": False, "session_cost": 0.0, "task_cost": 0.0,
             "task_exceeded": False, "session_exceeded": False, "stop_reason": None,
         }), \
         mock.patch("graph.build_run_summary_digest", return_value="digest"):
        result = g.update_logs_and_state(state)

    assert result.auto_repair_attempt == 0
    assert result.auto_repair_status is None
    assert result.check_output is None


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------

def test_graph_has_auto_repair_node():
    import graph
    assert hasattr(graph, "auto_repair_if_needed")
    assert hasattr(graph, "should_auto_repair")
    assert hasattr(graph, "build_auto_repair_prompt")
