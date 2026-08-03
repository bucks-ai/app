"""Unit tests for the Task Acceptance Criteria Gate.

Runs standalone (no pytest dependency):

    python tests/test_acceptance_criteria_gate.py

Covers:
- validate_acceptance_criteria: structured ``acceptance_criteria`` dict checks.
- validate_acceptance_criteria: description keyword-scan fallback.
- guard_acceptance_criteria: strict vs non-strict mode logging.
- Rejection cases: vague tasks, missing test expectations, missing forbidden
  scope, missing success evidence, unclear done conditions.
- Wiring: node registered in graph, config fields present.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.acceptance_criteria_gate import (
    validate_acceptance_criteria,
    guard_acceptance_criteria,
    _REQUIRED_AC_KEYS,
)

# Silence log_event to avoid disk writes during tests.
import tools.acceptance_criteria_gate as _acg
_acg.log_event = lambda *a, **k: None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task(**kwargs) -> dict:
    """Return a minimal valid task dict with overrides."""
    base = {
        "id": "task-ac-001",
        "title": "Add acceptance criteria gate to runner",
        "type": "backend",
    }
    base.update(kwargs)
    return base


def _task_with_full_ac(**overrides) -> dict:
    """Return a task with a complete structured acceptance_criteria dict."""
    ac = {
        "allowed_scope": ["tools/acceptance_criteria_gate.py", "tests/"],
        "forbidden_scope": "Do not modify app UI, routes, or production config.",
        "required_checks": "Run check.sh; all tests must pass.",
        "success_evidence": "Logs task_acceptance_criteria_passed event.",
        "rollback_behavior": "Mark task failed; do not revert other files.",
        "human_approval_required": False,
    }
    ac.update(overrides)
    return _task(acceptance_criteria=ac)


def _task_with_full_description() -> dict:
    """Return a task whose description contains all five keyword patterns."""
    desc = (
        "Expected files: tools/acceptance_criteria_gate.py. "
        "Forbidden scope: do not modify the UI or routes. "
        "Required checks: must pass check.sh and required tests. "
        "Success evidence: done condition is that the log event fires. "
        "Rollback behavior: on failure mark the task failed."
    )
    return _task(description=desc)


def _assert_ok(task):
    ok, issues = validate_acceptance_criteria(task)
    assert ok, f"expected ok but got issues: {issues}"
    assert issues == []


def _assert_rejected(task, fragment: str):
    ok, issues = validate_acceptance_criteria(task)
    assert not ok, f"expected rejection but got ok for task: {task}"
    combined = " | ".join(issues)
    assert fragment.lower() in combined.lower(), (
        f"expected '{fragment}' in issues: {issues}"
    )


# ---------------------------------------------------------------------------
# Structured acceptance_criteria dict — happy path
# ---------------------------------------------------------------------------

def test_full_ac_dict_passes():
    _assert_ok(_task_with_full_ac())


def test_ac_dict_string_values_pass():
    t = _task(acceptance_criteria={
        "allowed_scope": "tools/",
        "forbidden_scope": "Do not touch UI.",
        "required_checks": "Run check.sh.",
        "success_evidence": "Gate logs passed event.",
        "rollback_behavior": "Mark task failed on error.",
    })
    _assert_ok(t)


def test_ac_dict_optional_human_approval_ignored():
    t = _task_with_full_ac(human_approval_required=True)
    _assert_ok(t)


def test_required_ac_keys_constant():
    assert len(_REQUIRED_AC_KEYS) == 5
    assert "allowed_scope" in _REQUIRED_AC_KEYS
    assert "forbidden_scope" in _REQUIRED_AC_KEYS
    assert "required_checks" in _REQUIRED_AC_KEYS
    assert "success_evidence" in _REQUIRED_AC_KEYS
    assert "rollback_behavior" in _REQUIRED_AC_KEYS


# ---------------------------------------------------------------------------
# Structured acceptance_criteria dict — missing/empty fields
# ---------------------------------------------------------------------------

def test_missing_allowed_scope_rejected():
    t = _task_with_full_ac(allowed_scope=None)
    _assert_rejected(t, "allowed_scope")


def test_empty_string_allowed_scope_rejected():
    t = _task_with_full_ac(allowed_scope="   ")
    _assert_rejected(t, "allowed_scope")


def test_empty_list_allowed_scope_rejected():
    t = _task_with_full_ac(allowed_scope=[])
    _assert_rejected(t, "allowed_scope")


def test_missing_forbidden_scope_rejected():
    t = _task_with_full_ac(forbidden_scope=None)
    _assert_rejected(t, "forbidden_scope")


def test_missing_required_checks_rejected():
    t = _task_with_full_ac(required_checks=None)
    _assert_rejected(t, "required_checks")


def test_missing_success_evidence_rejected():
    t = _task_with_full_ac(success_evidence=None)
    _assert_rejected(t, "success_evidence")


def test_missing_rollback_behavior_rejected():
    t = _task_with_full_ac(rollback_behavior=None)
    _assert_rejected(t, "rollback_behavior")


def test_multiple_missing_keys_all_reported():
    t = _task(acceptance_criteria={
        "allowed_scope": "tools/",
    })
    ok, issues = validate_acceptance_criteria(t)
    assert not ok
    assert len(issues) >= 4, f"expected 4+ issues, got: {issues}"


# ---------------------------------------------------------------------------
# Description-based keyword detection — happy path
# ---------------------------------------------------------------------------

def test_full_description_passes():
    _assert_ok(_task_with_full_description())


def test_description_allowed_scope_variants():
    for phrase in [
        "allowed scope: tools/",
        "expected files: foo.py",
        "files created: bar.py",
    ]:
        t = _task(description=(
            phrase +
            " Forbidden scope: do not touch UI. "
            "Required checks: must pass. "
            "Success evidence: done condition met. "
            "Rollback behavior: on failure abort."
        ))
        _assert_ok(t)


def test_description_forbidden_scope_variants():
    for phrase in [
        "forbidden scope: UI",
        "must not modify the UI",
        "do not change the routes",
        "off-limits: production",
        "Forbidden:",
    ]:
        t = _task(description=(
            "allowed scope: tools/ "
            + phrase +
            " Required checks: must pass. "
            "Success evidence: done condition. "
            "Rollback behavior: on failure abort."
        ))
        _assert_ok(t)


def test_description_required_checks_variants():
    for phrase in [
        "required checks: run check.sh",
        "test expectations: all must pass",
        "must pass the test suite",
        "required tests: unit + integration",
        "check.sh must exit 0",
    ]:
        t = _task(description=(
            "allowed scope: tools/ "
            "forbidden scope: do not touch UI. "
            + phrase +
            " Success evidence: done condition. "
            "Rollback behavior: on failure abort."
        ))
        _assert_ok(t)


def test_description_success_evidence_variants():
    for phrase in [
        "success evidence: log event fires",
        "done condition: tests pass",
        "evidence of completion: check output",
        "success criteria: passes checks",
        "proven complete when tests pass",
    ]:
        t = _task(description=(
            "allowed scope: tools/ "
            "forbidden scope: do not touch UI. "
            "required checks: must pass. "
            + phrase +
            " Rollback behavior: on failure abort."
        ))
        _assert_ok(t)


def test_description_rollback_variants():
    for phrase in [
        "rollback: revert the branch",
        "failure behavior: mark task failed",
        "on failure: abort",
        "if it fails: do nothing",
    ]:
        t = _task(description=(
            "allowed scope: tools/ "
            "forbidden scope: do not touch UI. "
            "required checks: must pass. "
            "success evidence: done condition met. "
            + phrase
        ))
        _assert_ok(t)


# ---------------------------------------------------------------------------
# Rejection cases: vague tasks / missing specific criteria
# ---------------------------------------------------------------------------

def test_vague_task_no_description_no_ac_rejected():
    """Vague task with no description and no acceptance_criteria is rejected."""
    t = _task()
    ok, issues = validate_acceptance_criteria(t)
    assert not ok
    assert len(issues) == len(_REQUIRED_AC_KEYS), (
        f"expected one issue per criterion, got: {issues}"
    )


def test_missing_test_expectations_rejected():
    """Task with no required_checks criterion is rejected (missing test expectations)."""
    desc = (
        "allowed scope: tools/ "
        "forbidden scope: do not touch UI. "
        "Success evidence: done condition. "
        "Rollback behavior: on failure abort."
        # required_checks deliberately absent
    )
    _assert_rejected(_task(description=desc), "required_checks")


def test_missing_forbidden_scope_in_description_rejected():
    """Task with no forbidden_scope criterion is rejected."""
    desc = (
        "allowed scope: tools/ "
        "required checks: must pass. "
        "Success evidence: done condition. "
        "Rollback behavior: on failure abort."
        # forbidden_scope deliberately absent
    )
    _assert_rejected(_task(description=desc), "forbidden_scope")


def test_missing_success_evidence_in_description_rejected():
    """Task with unclear done condition (no success_evidence) is rejected."""
    desc = (
        "allowed scope: tools/ "
        "forbidden scope: do not touch UI. "
        "required checks: must pass. "
        "Rollback behavior: on failure abort."
        # success_evidence deliberately absent
    )
    _assert_rejected(_task(description=desc), "success_evidence")


def test_unclear_done_condition_rejected():
    """A task description that is vague about when it is 'done' is rejected."""
    desc = (
        "Just add the gate and make sure things work properly. "
        "Do not break anything. Run the tests."
        # no structured success_evidence, no rollback_behavior, no forbidden_scope
    )
    ok, issues = validate_acceptance_criteria(_task(description=desc))
    assert not ok
    issue_keys = " | ".join(issues)
    assert "success_evidence" in issue_keys or "rollback_behavior" in issue_keys or "forbidden_scope" in issue_keys


def test_empty_description_rejected():
    t = _task(description="")
    ok, issues = validate_acceptance_criteria(t)
    assert not ok
    assert len(issues) == len(_REQUIRED_AC_KEYS)


def test_whitespace_description_rejected():
    t = _task(description="   \n  ")
    ok, issues = validate_acceptance_criteria(t)
    assert not ok


# ---------------------------------------------------------------------------
# guard_acceptance_criteria — strict vs non-strict
# ---------------------------------------------------------------------------

_log_calls: list[tuple] = []


def _capture_log(*args, **kwargs):
    _log_calls.append((args, kwargs))


def test_guard_passes_full_ac_dict():
    _acg.log_event = _capture_log
    _log_calls.clear()
    try:
        result = guard_acceptance_criteria(_task_with_full_ac(), context="test")
        assert result["passed"] is True
        assert result["issues"] == []
        assert any(
            "task_acceptance_criteria_passed" in str(c)
            for c in _log_calls
        ), f"expected passed event, got: {_log_calls}"
    finally:
        _acg.log_event = lambda *a, **k: None


def test_guard_warns_in_non_strict_mode():
    _acg.log_event = _capture_log
    _log_calls.clear()
    try:
        result = guard_acceptance_criteria(_task(), context="test", strict_mode=False)
        assert result["passed"] is False
        assert any(
            "task_acceptance_criteria_warned" in str(c)
            for c in _log_calls
        ), f"expected warned event, got: {_log_calls}"
    finally:
        _acg.log_event = lambda *a, **k: None


def test_guard_rejects_in_strict_mode():
    _acg.log_event = _capture_log
    _log_calls.clear()
    try:
        result = guard_acceptance_criteria(_task(), context="test", strict_mode=True)
        assert result["passed"] is False
        assert any(
            "task_acceptance_criteria_rejected" in str(c)
            for c in _log_calls
        ), f"expected rejected event, got: {_log_calls}"
    finally:
        _acg.log_event = lambda *a, **k: None


def test_guard_returns_issues_on_failure():
    result = guard_acceptance_criteria(_task(), context="test")
    assert isinstance(result["issues"], list)
    assert len(result["issues"]) > 0


def test_guard_strict_mode_flag_mirrored():
    r1 = guard_acceptance_criteria(_task_with_full_ac(), strict_mode=False)
    assert r1["strict_mode"] is False

    r2 = guard_acceptance_criteria(_task_with_full_ac(), strict_mode=True)
    assert r2["strict_mode"] is True


# ---------------------------------------------------------------------------
# Wiring: node and config
# ---------------------------------------------------------------------------

def test_node_is_wired_into_graph():
    import ast, pathlib
    src = pathlib.Path(__file__).parent.parent / "graph.py"
    tree = ast.parse(src.read_text())
    # Check that check_acceptance_criteria is defined as a function.
    func_names = [
        node.name
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef)
    ]
    assert "check_acceptance_criteria" in func_names, (
        "check_acceptance_criteria function must be defined in graph.py"
    )


def test_guard_is_imported_in_graph():
    import ast, pathlib
    src = pathlib.Path(__file__).parent.parent / "graph.py"
    tree = ast.parse(src.read_text())
    from_imports = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        for alias in node.names
    ]
    assert "guard_acceptance_criteria" in from_imports, (
        "guard_acceptance_criteria must be imported in graph.py"
    )


def test_config_has_gate_enabled_field():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "acceptance_criteria_gate_enabled")
    assert cfg.acceptance_criteria_gate_enabled is True  # default on


def test_config_has_strict_mode_field():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "acceptance_criteria_strict_mode")
    assert cfg.acceptance_criteria_strict_mode is False  # default off


def test_config_gate_can_be_disabled_via_env():
    os.environ["ACCEPTANCE_CRITERIA_GATE_ENABLED"] = "false"
    try:
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.acceptance_criteria_gate_enabled is False
    finally:
        del os.environ["ACCEPTANCE_CRITERIA_GATE_ENABLED"]


def test_config_strict_mode_can_be_enabled_via_env():
    os.environ["ACCEPTANCE_CRITERIA_STRICT_MODE"] = "true"
    try:
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.acceptance_criteria_strict_mode is True
    finally:
        del os.environ["ACCEPTANCE_CRITERIA_STRICT_MODE"]


def test_state_has_acceptance_criteria_status_field():
    from state import RunnerState
    s = RunnerState()
    assert hasattr(s, "acceptance_criteria_status")
    assert s.acceptance_criteria_status is None


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_full_ac_dict_passes,
        test_ac_dict_string_values_pass,
        test_ac_dict_optional_human_approval_ignored,
        test_required_ac_keys_constant,
        test_missing_allowed_scope_rejected,
        test_empty_string_allowed_scope_rejected,
        test_empty_list_allowed_scope_rejected,
        test_missing_forbidden_scope_rejected,
        test_missing_required_checks_rejected,
        test_missing_success_evidence_rejected,
        test_missing_rollback_behavior_rejected,
        test_multiple_missing_keys_all_reported,
        test_full_description_passes,
        test_description_allowed_scope_variants,
        test_description_forbidden_scope_variants,
        test_description_required_checks_variants,
        test_description_success_evidence_variants,
        test_description_rollback_variants,
        test_vague_task_no_description_no_ac_rejected,
        test_missing_test_expectations_rejected,
        test_missing_forbidden_scope_in_description_rejected,
        test_missing_success_evidence_in_description_rejected,
        test_unclear_done_condition_rejected,
        test_empty_description_rejected,
        test_whitespace_description_rejected,
        test_guard_passes_full_ac_dict,
        test_guard_warns_in_non_strict_mode,
        test_guard_rejects_in_strict_mode,
        test_guard_returns_issues_on_failure,
        test_guard_strict_mode_flag_mirrored,
        test_node_is_wired_into_graph,
        test_guard_is_imported_in_graph,
        test_config_has_gate_enabled_field,
        test_config_has_strict_mode_field,
        test_config_gate_can_be_disabled_via_env,
        test_config_strict_mode_can_be_enabled_via_env,
        test_state_has_acceptance_criteria_status_field,
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
