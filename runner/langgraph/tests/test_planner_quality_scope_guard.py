"""Unit tests for Planner Quality Gate v2 and hard scope guard.

Runs standalone (no pytest dependency):

    python tests/test_planner_quality_scope_guard.py

Covers:
- validate_planner_task: required fields, title length (v1 and v2), type
  allowlist, branch pattern, worker allowlist, duplicate ID detection.
- evaluate_scope_guard: each category of forbidden pattern.
- guard_planner_task: integration across both checks, config flag behaviour.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.task_quality_guard import (
    validate_planner_task,
    evaluate_scope_guard,
    guard_planner_task,
    _KNOWN_TASK_TYPES,
    _TITLE_MIN_CHARS,
    _TITLE_MAX_CHARS,
)

# Silence log_event so no disk writes happen.
import tools.task_quality_guard as _tqg
_tqg.log_event = lambda *a, **k: None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task(**kwargs) -> dict:
    base = {"id": "task-001", "title": "Add new feature to the API", "type": "backend"}
    base.update(kwargs)
    return base


def _assert_ok(task, **kw):
    ok, issues = validate_planner_task(task, **kw)
    assert ok, f"expected ok but got issues: {issues}"
    assert issues == []


def _assert_issue(task, fragment: str, **kw):
    ok, issues = validate_planner_task(task, **kw)
    assert not ok, f"expected rejection but got ok for task: {task}"
    combined = " | ".join(issues)
    assert fragment.lower() in combined.lower(), (
        f"expected fragment '{fragment}' in issues: {issues}"
    )


# ---------------------------------------------------------------------------
# validate_planner_task — required fields
# ---------------------------------------------------------------------------

def test_valid_task_passes():
    _assert_ok(_task())


def test_missing_id_rejected():
    _assert_issue(_task(id=""), "missing required field: 'id'")


def test_missing_title_rejected():
    _assert_issue(_task(title=""), "missing required field: 'title'")


def test_missing_type_rejected():
    _assert_issue(_task(type=""), "missing required field: 'type'")


# ---------------------------------------------------------------------------
# validate_planner_task — title length
# ---------------------------------------------------------------------------

def test_v1_title_min_5_passes():
    # v1 allows >=5 chars
    _assert_ok(_task(title="Hello"), v2=False)


def test_v1_title_4_chars_rejected():
    _assert_issue(_task(title="Hi!!"), "title too short", v2=False)


def test_v2_title_min_10_passes():
    _assert_ok(_task(title="A" * _TITLE_MIN_CHARS))


def test_v2_title_9_chars_rejected():
    _assert_issue(_task(title="A" * (_TITLE_MIN_CHARS - 1)), "title too short")


def test_v2_title_max_200_passes():
    _assert_ok(_task(title="A" * _TITLE_MAX_CHARS))


def test_v2_title_201_chars_rejected():
    _assert_issue(_task(title="A" * (_TITLE_MAX_CHARS + 1)), "title too long")


# ---------------------------------------------------------------------------
# validate_planner_task — task type allowlist (v2 only)
# ---------------------------------------------------------------------------

def test_known_type_passes():
    for t in ("backend", "frontend", "general", "bugfix", "refactor"):
        _assert_ok(_task(type=t))


def test_unknown_type_rejected_v2():
    _assert_issue(_task(type="mystery"), "unknown task type")


def test_unknown_type_allowed_v1():
    # v1 does not enforce the allowlist
    _assert_ok(_task(type="mystery"), v2=False)


def test_known_types_set_is_non_empty():
    assert len(_KNOWN_TASK_TYPES) >= 10, "allowlist should have at least 10 types"


# ---------------------------------------------------------------------------
# validate_planner_task — branch validation
# ---------------------------------------------------------------------------

def test_no_branch_passes():
    _assert_ok(_task())  # branch field absent


def test_safe_branch_passes():
    _assert_ok(_task(branch="feature/add-new-api-endpoint"))


def test_protected_branch_rejected():
    for b in ("main", "master", "develop", "production", "release"):
        _assert_issue(_task(branch=b), "protected branch")


def test_branch_with_space_rejected():
    _assert_issue(_task(branch="feature/my task"), "contains spaces")


def test_branch_with_dotdot_rejected_v2():
    _assert_issue(_task(branch="feature/../etc"), "contains '..'")


def test_branch_unsafe_chars_rejected_v2():
    _assert_issue(_task(branch="feature/my$task!"), "unsafe characters")


def test_branch_dotdot_allowed_v1():
    # v1 does not check for '..' in branch names
    ok, issues = validate_planner_task(_task(branch="feature/../etc"), v2=False)
    assert ok or not any("'..'".lower() in i.lower() for i in issues)


# ---------------------------------------------------------------------------
# validate_planner_task — preferred_worker
# ---------------------------------------------------------------------------

def test_known_worker_passes():
    for w in ("claude", "codex", "chatgpt"):
        _assert_ok(_task(preferred_worker=w))


def test_unknown_worker_rejected():
    _assert_issue(_task(preferred_worker="gpt5"), "unknown preferred_worker")


def test_no_worker_passes():
    _assert_ok(_task())  # preferred_worker absent


# ---------------------------------------------------------------------------
# validate_planner_task — duplicate ID detection
# ---------------------------------------------------------------------------

def test_duplicate_id_rejected():
    # Patch load_tasks on the task_quality_guard module (which holds the
    # reference captured at import time via `from tools.task_tools import ...`).
    _tqg.load_tasks = lambda: [{"id": "task-001"}]
    try:
        _assert_issue(_task(), "duplicate task id")
    finally:
        _tqg.load_tasks = lambda: []


def test_fresh_id_passes():
    _tqg.load_tasks = lambda: [{"id": "other-task"}]
    try:
        _assert_ok(_task())
    finally:
        _tqg.load_tasks = lambda: []


# ---------------------------------------------------------------------------
# evaluate_scope_guard — forbidden pattern categories
# ---------------------------------------------------------------------------

def _scope_ok(task):
    clean, violations = evaluate_scope_guard(task)
    assert clean, f"expected clean but got violations: {violations}"


def _scope_blocked(task, label_fragment: str):
    clean, violations = evaluate_scope_guard(task)
    assert not clean, f"expected violation for task: {task}"
    combined = " | ".join(violations)
    assert label_fragment.lower() in combined.lower(), (
        f"expected '{label_fragment}' in violations: {violations}"
    )


def test_scope_clean_task_passes():
    _scope_ok(_task())


def test_scope_force_push_title():
    _scope_blocked(_task(title="Force push the changes to remote"), "force-push")


def test_scope_force_push_hyphen():
    _scope_blocked(_task(title="force-push to origin main"), "force-push")


def test_scope_push_force_flag():
    _scope_blocked(_task(title="push all branches --force to upstream"), "force-push")


def test_scope_git_reset_hard():
    _scope_blocked(_task(title="Run git reset --hard HEAD~1"), "hard git reset")


def test_scope_drop_table():
    _scope_blocked(_task(title="Drop table users from production DB"), "destructive database drop")


def test_scope_drop_database():
    _scope_blocked(_task(title="drop database staging"), "destructive database drop")


def test_scope_truncate_table():
    _scope_blocked(_task(title="Truncate table events for reset"), "table truncation")


def test_scope_delete_all_records():
    _scope_blocked(_task(title="Delete all records from the cache table"), "bulk record deletion")


def test_scope_bypass_gate():
    _scope_blocked(_task(title="Bypass the safety gate for this task"), "bypassing a safety gate")


def test_scope_skip_check():
    _scope_blocked(_task(title="Skip the check for now"), "bypassing a safety gate")


def test_scope_disable_guard():
    _scope_blocked(_task(title="Disable the failure guard temporarily"), "bypassing a safety gate")


def test_scope_no_verify():
    _scope_blocked(_task(title="Commit with --no-verify to skip hooks"), "--no-verify")


def test_scope_gpg_sign_false():
    _scope_blocked(
        _task(description="Set commit.gpgsign=false in git config"),
        "gpg signing",
    )


def test_scope_merge_directly_to_main():
    _scope_blocked(_task(title="Merge directly into main without PR"), "direct merge")


def test_scope_push_directly_to_production():
    _scope_blocked(_task(title="Push directly to production branch"), "direct push")


def test_scope_deploy_directly_to_staging():
    _scope_blocked(_task(title="Deploy directly to staging environment"), "direct deploy")


def test_scope_directory_traversal():
    _scope_blocked(_task(title="Read ../../../etc/passwd"), "directory traversal")


def test_scope_description_field_scanned():
    # Scope guard must also scan description, not just title.
    task = _task(title="Refactor authentication module", description="force push all branches")
    _scope_blocked(task, "force-push")


def test_scope_prompt_field_scanned():
    task = _task(title="Update API routes", prompt="drop table sessions")
    _scope_blocked(task, "destructive database drop")


def test_scope_case_insensitive():
    _scope_blocked(_task(title="FORCE PUSH to remote"), "force-push")


# ---------------------------------------------------------------------------
# guard_planner_task — integration
# ---------------------------------------------------------------------------

def test_guard_returns_task_when_valid():
    result = guard_planner_task(_task(), context="test")
    assert result is not None
    assert result["id"] == "task-001"


def test_guard_returns_none_on_quality_failure():
    result = guard_planner_task(_task(title="Hi"), context="test")
    assert result is None


def test_guard_returns_none_on_scope_violation():
    result = guard_planner_task(_task(title="Force push all branches now"), context="test")
    assert result is None


def test_guard_scope_disabled_allows_forbidden_task():
    result = guard_planner_task(
        _task(title="Force push all branches now"),
        context="test",
        scope_guard=False,
    )
    assert result is not None, "scope guard disabled should allow the task"


def test_guard_v2_disabled_allows_short_title():
    # With v2 off, a 7-char title (>= v1 min of 5) must pass.
    result = guard_planner_task(_task(title="Add API"), v2=False, scope_guard=False)
    assert result is not None, "v2 disabled should use v1 title min of 5 chars"


def test_guard_v2_disabled_allows_unknown_type():
    result = guard_planner_task(_task(type="mystery"), v2=False, scope_guard=False)
    assert result is not None


def test_guard_both_disabled_allows_borderline_task():
    # A task that fails both v2 quality AND scope guard passes when both are off.
    t = _task(title="Hi", type="mystery", description="force push")
    result = guard_planner_task(t, v2=False, scope_guard=False)
    # Still fails the v1 title check (< 5 chars "Hi" = 2).
    assert result is None


def test_guard_passes_valid_task_with_all_optional_fields():
    t = _task(
        branch="feature/add-oauth-support",
        preferred_worker="claude",
        description="Implement OAuth2 login flow.",
    )
    result = guard_planner_task(t)
    assert result is not None


# ---------------------------------------------------------------------------
# Wiring: ensure guard_planner_task is imported and used in graph.py
# ---------------------------------------------------------------------------

def test_guard_is_imported_in_graph():
    import importlib, ast, pathlib
    src = pathlib.Path(__file__).parent.parent / "graph.py"
    tree = ast.parse(src.read_text())
    imports = [
        alias.name
        for node in ast.walk(tree)
        if isinstance(node, (ast.Import, ast.ImportFrom))
        for alias in (node.names if hasattr(node, "names") else [])
    ]
    # Also check ImportFrom names
    from_imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            for alias in node.names:
                from_imports.append(alias.name)
    assert "guard_planner_task" in from_imports, (
        "guard_planner_task must be imported in graph.py"
    )


def test_config_has_quality_gate_v2_field():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "planner_quality_gate_v2_enabled")
    assert cfg.planner_quality_gate_v2_enabled is True  # default on


def test_config_has_scope_guard_field():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "planner_scope_guard_enabled")
    assert cfg.planner_scope_guard_enabled is True  # default on


def test_config_v2_can_be_disabled_via_env(monkeypatch=None):
    import os
    os.environ["PLANNER_QUALITY_GATE_V2"] = "false"
    try:
        # Force re-creation of RunnerConfig to pick up env var.
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.planner_quality_gate_v2_enabled is False
    finally:
        del os.environ["PLANNER_QUALITY_GATE_V2"]


def test_config_scope_guard_can_be_disabled_via_env(monkeypatch=None):
    import os
    os.environ["PLANNER_SCOPE_GUARD"] = "false"
    try:
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.planner_scope_guard_enabled is False
    finally:
        del os.environ["PLANNER_SCOPE_GUARD"]


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_valid_task_passes,
        test_missing_id_rejected,
        test_missing_title_rejected,
        test_missing_type_rejected,
        test_v1_title_min_5_passes,
        test_v1_title_4_chars_rejected,
        test_v2_title_min_10_passes,
        test_v2_title_9_chars_rejected,
        test_v2_title_max_200_passes,
        test_v2_title_201_chars_rejected,
        test_known_type_passes,
        test_unknown_type_rejected_v2,
        test_unknown_type_allowed_v1,
        test_known_types_set_is_non_empty,
        test_no_branch_passes,
        test_safe_branch_passes,
        test_protected_branch_rejected,
        test_branch_with_space_rejected,
        test_branch_with_dotdot_rejected_v2,
        test_branch_unsafe_chars_rejected_v2,
        test_branch_dotdot_allowed_v1,
        test_known_worker_passes,
        test_unknown_worker_rejected,
        test_no_worker_passes,
        test_duplicate_id_rejected,
        test_fresh_id_passes,
        test_scope_clean_task_passes,
        test_scope_force_push_title,
        test_scope_force_push_hyphen,
        test_scope_push_force_flag,
        test_scope_git_reset_hard,
        test_scope_drop_table,
        test_scope_drop_database,
        test_scope_truncate_table,
        test_scope_delete_all_records,
        test_scope_bypass_gate,
        test_scope_skip_check,
        test_scope_disable_guard,
        test_scope_no_verify,
        test_scope_gpg_sign_false,
        test_scope_merge_directly_to_main,
        test_scope_push_directly_to_production,
        test_scope_deploy_directly_to_staging,
        test_scope_directory_traversal,
        test_scope_description_field_scanned,
        test_scope_prompt_field_scanned,
        test_scope_case_insensitive,
        test_guard_returns_task_when_valid,
        test_guard_returns_none_on_quality_failure,
        test_guard_returns_none_on_scope_violation,
        test_guard_scope_disabled_allows_forbidden_task,
        test_guard_v2_disabled_allows_short_title,
        test_guard_v2_disabled_allows_unknown_type,
        test_guard_both_disabled_allows_borderline_task,
        test_guard_passes_valid_task_with_all_optional_fields,
        test_guard_is_imported_in_graph,
        test_config_has_quality_gate_v2_field,
        test_config_has_scope_guard_field,
        test_config_v2_can_be_disabled_via_env,
        test_config_scope_guard_can_be_disabled_via_env,
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
