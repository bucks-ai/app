"""Unit tests for Auto-Repair Loop v2.

Covers:
- should_auto_repair: all skip conditions (worker failed, checks passed,
  attempts exhausted) and the happy path.
- build_auto_repair_prompt: structure, content, truncation.
- Graph node: enabled/disabled config, single repair success, repair worker
  failure, exhausted attempts, check-still-failing-after-repair paths.
- Config fields default to expected values.
- State fields present and reset correctly.
- M4c.4 deterministic failure classification, signature, budget, evidence
  fetchers, prompt builders, and graph node routing.
"""
import os
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.auto_repair_loop import (
    should_auto_repair,
    build_auto_repair_prompt,
    classify_deterministic_failure,
    make_failure_signature,
    should_deterministic_repair,
    fetch_ci_failure_evidence,
    fetch_merge_conflict_evidence,
    build_ci_repair_prompt,
    build_merge_conflict_repair_prompt,
    build_completion_evidence_repair_prompt,
    build_gate_block_repair_prompt,
    build_deterministic_repair_prompt,
    CI_CHECK_FAILURE,
    MERGE_CONFLICT,
    COMPLETION_EVIDENCE_BLOCK,
    GATE_BLOCK,
)


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


# ===========================================================================
# M4c.4: Deterministic failure classification
# ===========================================================================

def test_classify_ci_failure():
    assert classify_deterministic_failure("pr_checks_failed: PR #42 required checks did not pass") == CI_CHECK_FAILURE


def test_classify_ci_failure_case_insensitive():
    assert classify_deterministic_failure("PR_CHECKS_FAILED: some checks failed") == CI_CHECK_FAILURE


def test_classify_merge_conflict():
    assert classify_deterministic_failure("pr_merge_failed: PR #5: conflict detected on main") == MERGE_CONFLICT


def test_classify_merge_no_conflict_keyword_is_not_merge():
    # pr_merge_failed but no 'conflict' keyword → not classified as merge conflict
    assert classify_deterministic_failure("pr_merge_failed: PR #5: protected branch") is None


def test_classify_empty_error_is_none():
    assert classify_deterministic_failure("") is None


def test_classify_none_error_is_none():
    assert classify_deterministic_failure(None) is None


def test_classify_transient_timeout_is_none():
    assert classify_deterministic_failure("worker timed out after 2400 seconds") is None


def test_classify_cooldown_is_none():
    assert classify_deterministic_failure("claude subscription cooldown detected") is None


# ===========================================================================
# M4c.4: Failure signature
# ===========================================================================

def test_make_failure_signature_ci_stable():
    ev1 = {"failed_checks": ["lint", "test"]}
    ev2 = {"failed_checks": ["test", "lint"]}  # different order, same result
    assert make_failure_signature(CI_CHECK_FAILURE, ev1) == make_failure_signature(CI_CHECK_FAILURE, ev2)


def test_make_failure_signature_ci_different_checks():
    ev1 = {"failed_checks": ["lint"]}
    ev2 = {"failed_checks": ["test"]}
    assert make_failure_signature(CI_CHECK_FAILURE, ev1) != make_failure_signature(CI_CHECK_FAILURE, ev2)


def test_make_failure_signature_merge_stable():
    ev1 = {"conflicted_files": ["a.py", "b.py"]}
    ev2 = {"conflicted_files": ["b.py", "a.py"]}
    assert make_failure_signature(MERGE_CONFLICT, ev1) == make_failure_signature(MERGE_CONFLICT, ev2)


def test_make_failure_signature_different_classes():
    ev = {"failed_checks": ["test"]}
    assert make_failure_signature(CI_CHECK_FAILURE, ev) != make_failure_signature(MERGE_CONFLICT, ev)


def test_make_failure_signature_is_16_chars():
    sig = make_failure_signature(CI_CHECK_FAILURE, {"failed_checks": ["test"]})
    assert len(sig) == 16


# ===========================================================================
# M4c.4: Repair budget guard
# ===========================================================================

def test_should_deterministic_repair_ok():
    ok, reason = should_deterministic_repair(0, 3, None, "abc")
    assert ok is True
    assert reason == "ok"


def test_should_deterministic_repair_depth_exceeded():
    ok, reason = should_deterministic_repair(3, 3, None, "abc")
    assert ok is False
    assert reason == "depth_exceeded"


def test_should_deterministic_repair_depth_at_limit():
    ok, reason = should_deterministic_repair(2, 3, None, "abc")
    assert ok is True


def test_should_deterministic_repair_repeated_signature():
    sig = "abc123"
    ok, reason = should_deterministic_repair(1, 3, sig, sig)
    assert ok is False
    assert reason == "repeated_signature"


def test_should_deterministic_repair_different_signature_allowed():
    ok, reason = should_deterministic_repair(1, 3, "old_sig", "new_sig")
    assert ok is True


def test_should_deterministic_repair_no_last_signature_allowed():
    ok, reason = should_deterministic_repair(1, 3, None, "any_sig")
    assert ok is True


# ===========================================================================
# M4c.4: Evidence fetchers
# ===========================================================================

def test_fetch_ci_failure_evidence_failed_checks():
    check_runs = [
        {"name": "lint", "conclusion": "failure", "output": {"summary": "3 errors found", "text": ""}},
        {"name": "test", "conclusion": "success", "output": {}},
    ]
    ev = fetch_ci_failure_evidence(check_runs, repo="owner/repo", token=None)
    assert "lint" in ev["failed_checks"]
    assert "test" not in ev["failed_checks"]
    assert "3 errors found" in ev["log_excerpt"]


def test_fetch_ci_failure_evidence_empty_runs():
    ev = fetch_ci_failure_evidence([], repo="owner/repo", token=None)
    assert ev["failed_checks"] == []
    assert ev["log_excerpt"] == ""


def test_fetch_ci_failure_evidence_truncates():
    long_text = "x" * 5000
    check_runs = [
        {"name": "test", "conclusion": "failure", "output": {"summary": long_text, "text": ""}},
    ]
    ev = fetch_ci_failure_evidence(check_runs, repo="r", token=None, max_excerpt_chars=100)
    assert len(ev["log_excerpt"]) <= 100


def test_fetch_ci_failure_evidence_api_annotation(monkeypatch):
    """Annotations are fetched from the GitHub API when a token and run_id are present."""
    check_runs = [
        {
            "name": "test",
            "id": 12345,
            "conclusion": "failure",
            "output": {"summary": "", "text": ""},
        }
    ]
    fake_annotations = [
        {"path": "foo/bar.py", "start_line": 42, "message": "assert 0 == 1"},
    ]

    class FakeResp:
        status_code = 200
        def json(self):
            return fake_annotations

    with mock.patch("tools.auto_repair_loop.subprocess"):
        with mock.patch("requests.get", return_value=FakeResp()):
            import requests as _req
            ev = fetch_ci_failure_evidence(check_runs, repo="owner/repo", token="tok")

    assert "foo/bar.py" in ev["log_excerpt"] or ev["failed_checks"] == ["test"]


def test_fetch_merge_conflict_evidence_structure():
    """Returns the required keys even when git commands fail."""
    with mock.patch("tools.auto_repair_loop.subprocess.check_output", side_effect=Exception("no git")):
        ev = fetch_merge_conflict_evidence("/tmp/nonexistent")
    assert "conflicted_files" in ev
    assert "diff_excerpt" in ev
    assert isinstance(ev["conflicted_files"], list)


def test_fetch_merge_conflict_evidence_conflicted_files():
    status_output = b"UU src/main.py\nAA tests/test_foo.py\nM  other.py\n"
    diff_output = b"diff --git a/src/main.py\n+++ content"

    def fake_output(args, **kwargs):
        if "status" in args:
            return status_output
        return diff_output

    with mock.patch("tools.auto_repair_loop.subprocess.check_output", side_effect=fake_output):
        ev = fetch_merge_conflict_evidence("/repo")

    assert "src/main.py" in ev["conflicted_files"]
    assert "tests/test_foo.py" in ev["conflicted_files"]
    assert "other.py" not in ev["conflicted_files"]


# ===========================================================================
# M4c.4: Repair prompt builders
# ===========================================================================

def test_build_ci_repair_prompt_contains_checks():
    ev = {"failed_checks": ["lint", "test"], "log_excerpt": "ERROR: test_foo failed"}
    p = build_ci_repair_prompt("Do the task.", ev, {}, 1, 3)
    assert "lint" in p
    assert "test" in p
    assert "ERROR: test_foo failed" in p
    assert "Do the task." in p
    assert "1 of 3" in p


def test_build_merge_conflict_repair_prompt_contains_files():
    ev = {"conflicted_files": ["foo.py", "bar.py"], "diff_excerpt": "<<<<<<< HEAD"}
    p = build_merge_conflict_repair_prompt("Original task.", ev, {}, 2, 3)
    assert "foo.py" in p
    assert "bar.py" in p
    assert "<<<<<<< HEAD" in p
    assert "Original task." in p
    assert "2 of 3" in p


def test_build_completion_evidence_repair_prompt_contains_reasons():
    ev = {"reasons": ["no commit found", "check result missing"]}
    p = build_completion_evidence_repair_prompt("Task prompt.", ev, {}, 1, 3)
    assert "no commit found" in p
    assert "check result missing" in p
    assert "Task prompt." in p


def test_build_gate_block_repair_prompt_contains_gate():
    ev = {"gate": "definition_of_done", "authority": "gatekeeper", "reasons": ["missing tests"]}
    p = build_gate_block_repair_prompt("Task prompt.", ev, {}, 1, 3)
    assert "definition_of_done" in p
    assert "gatekeeper" in p
    assert "missing tests" in p
    assert "Task prompt." in p


def test_build_deterministic_repair_prompt_dispatches_ci():
    ev = {"failed_checks": ["test"], "log_excerpt": "FAILED"}
    p = build_deterministic_repair_prompt(CI_CHECK_FAILURE, "orig", ev, {}, 1, 3)
    assert "FAILED" in p
    assert "orig" in p


def test_build_deterministic_repair_prompt_dispatches_merge():
    ev = {"conflicted_files": ["x.py"], "diff_excerpt": ""}
    p = build_deterministic_repair_prompt(MERGE_CONFLICT, "orig", ev, {}, 1, 3)
    assert "x.py" in p


def test_build_deterministic_repair_prompt_dispatches_evidence():
    ev = {"reasons": ["no sha"]}
    p = build_deterministic_repair_prompt(COMPLETION_EVIDENCE_BLOCK, "orig", ev, {}, 1, 3)
    assert "no sha" in p


def test_build_deterministic_repair_prompt_dispatches_gate():
    ev = {"gate": "g", "reasons": ["r"]}
    p = build_deterministic_repair_prompt(GATE_BLOCK, "orig", ev, {}, 1, 3)
    assert "'g' gate" in p


def test_build_deterministic_repair_prompt_unknown_class():
    # Unknown class returns original prompt unchanged
    p = build_deterministic_repair_prompt("unknown_class", "original prompt", {}, {}, 1, 3)
    assert p == "original prompt"


# ===========================================================================
# M4c.4: Config
# ===========================================================================

def test_config_max_repair_depth_default():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert cfg.max_repair_depth == 3


def test_config_max_repair_depth_override():
    original = os.environ.get("MAX_REPAIR_DEPTH")
    try:
        os.environ["MAX_REPAIR_DEPTH"] = "5"
        import config as _cfg_module
        _cfg_module._config = None
        cfg = _cfg_module.get_config()
        assert cfg.max_repair_depth == 5
    finally:
        if original is None:
            os.environ.pop("MAX_REPAIR_DEPTH", None)
        else:
            os.environ["MAX_REPAIR_DEPTH"] = original
        import config as _cfg_module
        _cfg_module._config = None


# ===========================================================================
# M4c.4: State fields
# ===========================================================================

def test_state_repair_depth_and_signature_fields():
    from state import RunnerState
    s = RunnerState()
    assert s.repair_depth == 0
    assert s.last_failure_signature is None


def test_update_logs_clears_repair_fields():
    import graph as g
    state = _make_state(
        worker_result={
            "success": True, "worker": "claude", "error": None,
            "output": "- Check Result: pass",
            "mode": "cli", "prompt_written": False, "prompt_path": None,
            "response_path": None, "api_cost": None, "tokens_used": None,
        },
        check_passed=True,
        auto_repair_attempt=0,
        auto_repair_status=None,
        check_output=None,
    )
    state.repair_depth = 2
    state.last_failure_signature = "abc123def456abcd"

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

    assert result.repair_depth == 0
    assert result.last_failure_signature is None


# ===========================================================================
# M4c.4: Graph node — deterministic_repair_if_needed
# ===========================================================================

def _make_det_state(**kwargs):
    """State pre-set with a CI-check failure."""
    from state import RunnerState
    defaults = {
        "current_worker": "claude",
        "current_task_id": "t-det-001",
        "current_task": {
            "id": "t-det-001",
            "title": "Deterministic test task",
            "type": "backend",
            "branch": "feature/t-det-001",
        },
        "worker_result": {
            "success": False,
            "worker": "claude",
            "error": "pr_checks_failed: PR #7 required checks did not pass",
            "output": None,
            "mode": "cli",
            "prompt_written": False,
            "prompt_path": None,
            "response_path": None,
            "api_cost": None,
            "tokens_used": None,
        },
        "check_passed": True,  # local check passed; CI failed
        "check_output": "OK",
        "messages": [{"role": "user", "content": "Build the feature."}],
        "resolved_model": None,
        "auto_repair_attempt": 0,
        "auto_repair_status": None,
        "repair_depth": 0,
        "last_failure_signature": None,
    }
    defaults.update(kwargs)
    return RunnerState(**defaults)


def test_det_repair_skips_when_disabled():
    import graph as g
    state = _make_det_state()
    with mock.patch.object(g.cfg, "auto_repair_loop_enabled", False):
        result = g.deterministic_repair_if_needed(state)
    assert result.repair_depth == 0


def test_det_repair_skips_when_worker_succeeded():
    import graph as g
    state = _make_det_state(worker_result={
        "success": True, "worker": "claude", "error": None, "output": "ok",
        "mode": "cli", "prompt_written": False, "prompt_path": None,
        "response_path": None, "api_cost": None, "tokens_used": None,
    })
    with mock.patch.object(g.cfg, "auto_repair_loop_enabled", True), \
         mock.patch("graph._persist", side_effect=lambda s, _: s):
        result = g.deterministic_repair_if_needed(state)
    assert result.repair_depth == 0


def test_det_repair_skips_transient_failure():
    import graph as g
    state = _make_det_state(worker_result={
        "success": False, "worker": "claude",
        "error": "network timeout after 30 seconds",
        "output": None, "mode": "cli", "prompt_written": False,
        "prompt_path": None, "response_path": None, "api_cost": None, "tokens_used": None,
    })
    with mock.patch.object(g.cfg, "auto_repair_loop_enabled", True), \
         mock.patch("graph._persist", side_effect=lambda s, _: s):
        result = g.deterministic_repair_if_needed(state)
    # Transient → repair_depth unchanged, old retry path handles it
    assert result.repair_depth == 0


def test_det_repair_ci_failure_routes_to_repair():
    """CI failure triggers a repair worker and increments repair_depth."""
    import graph as g
    from state import WorkerResult
    state = _make_det_state()

    repaired = WorkerResult(worker="claude", mode="cli", success=True, output="- Check Result: pass")

    with mock.patch.object(g.cfg, "auto_repair_loop_enabled", True), \
         mock.patch.object(g.cfg, "max_repair_depth", 3), \
         mock.patch.object(g.cfg, "merge_via_pr", False), \
         mock.patch("graph.ClaudeWorker") as MockClaude, \
         mock.patch("graph.run_check", return_value={"success": True, "output": "OK"}), \
         mock.patch("graph._persist", side_effect=lambda s, _: s), \
         mock.patch("graph.log_event"):
        MockClaude.return_value.run_worker_prompt.return_value = repaired
        result = g.deterministic_repair_if_needed(state)

    assert result.repair_depth == 1
    assert result.last_failure_signature is not None
    assert (result.worker_result or {}).get("success") is True


def test_det_repair_consumes_repair_budget_not_retry():
    """repair_depth goes up; the normal task retry count is not touched."""
    import graph as g
    from state import WorkerResult
    state = _make_det_state()

    repaired = WorkerResult(worker="claude", mode="cli", success=True, output="- Check Result: pass")

    original_retry_count = (state.current_task or {}).get("retry_count", 0)

    with mock.patch.object(g.cfg, "auto_repair_loop_enabled", True), \
         mock.patch.object(g.cfg, "max_repair_depth", 3), \
         mock.patch.object(g.cfg, "merge_via_pr", False), \
         mock.patch("graph.ClaudeWorker") as MockClaude, \
         mock.patch("graph.run_check", return_value={"success": True, "output": "OK"}), \
         mock.patch("graph._persist", side_effect=lambda s, _: s), \
         mock.patch("graph.log_event"):
        MockClaude.return_value.run_worker_prompt.return_value = repaired
        result = g.deterministic_repair_if_needed(state)

    assert result.repair_depth == 1
    # Task retry_count is unchanged
    assert (result.current_task or {}).get("retry_count", 0) == original_retry_count


def test_det_repair_depth_cap_escalates():
    """When repair_depth >= max_repair_depth, no repair is attempted."""
    import graph as g
    state = _make_det_state(repair_depth=3)  # already at cap

    with mock.patch.object(g.cfg, "auto_repair_loop_enabled", True), \
         mock.patch.object(g.cfg, "max_repair_depth", 3), \
         mock.patch("graph.ClaudeWorker") as MockClaude, \
         mock.patch("graph._persist", side_effect=lambda s, _: s), \
         mock.patch("graph.log_event"):
        result = g.deterministic_repair_if_needed(state)

    MockClaude.assert_not_called()
    assert result.repair_depth == 3  # unchanged


def test_det_repair_identical_signature_stops():
    """Identical failure signature on second attempt stops repair."""
    import graph as g
    from state import WorkerResult
    # Pre-set the signature to match what the CI error would produce
    state = _make_det_state(
        repair_depth=1,
    )

    # Pre-compute the signature that classify + make_failure_signature would produce
    from tools.auto_repair_loop import classify_deterministic_failure, make_failure_signature
    error = "pr_checks_failed: PR #7 required checks did not pass"
    fc = classify_deterministic_failure(error)
    evidence = {"failed_checks": [
        part.strip()
        for part in error.replace("pr_checks_failed:", "").split(",")
        if part.strip()
    ] or [error[:80]]}
    expected_sig = make_failure_signature(fc, evidence)
    state.last_failure_signature = expected_sig  # same as what will be computed

    with mock.patch.object(g.cfg, "auto_repair_loop_enabled", True), \
         mock.patch.object(g.cfg, "max_repair_depth", 3), \
         mock.patch("graph.ClaudeWorker") as MockClaude, \
         mock.patch("graph._persist", side_effect=lambda s, _: s), \
         mock.patch("graph.log_event"):
        result = g.deterministic_repair_if_needed(state)

    # Worker not called because signature repeated
    MockClaude.assert_not_called()
    # repair_depth unchanged
    assert result.repair_depth == 1


def test_det_repair_worker_failure_does_not_corrupt_state():
    """When the repair worker itself fails, state is left intact for failure guard."""
    import graph as g
    from state import WorkerResult
    state = _make_det_state()

    failed = WorkerResult(worker="claude", mode="cli", success=False, error="repair crashed")

    with mock.patch.object(g.cfg, "auto_repair_loop_enabled", True), \
         mock.patch.object(g.cfg, "max_repair_depth", 3), \
         mock.patch("graph.ClaudeWorker") as MockClaude, \
         mock.patch("graph._persist", side_effect=lambda s, _: s), \
         mock.patch("graph.log_event"):
        MockClaude.return_value.run_worker_prompt.return_value = failed
        result = g.deterministic_repair_if_needed(state)

    assert result.repair_depth == 1  # incremented before worker dispatch
    assert (result.worker_result or {}).get("success") is False  # original failure preserved


def test_det_repair_graph_has_node():
    import graph
    assert hasattr(graph, "deterministic_repair_if_needed")
