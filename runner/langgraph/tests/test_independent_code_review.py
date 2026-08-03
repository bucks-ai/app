"""Unit tests for the Independent Code Review Gate.

Covers:
- validate_code_review: env-file check, forbidden scope, secret patterns,
  allowed scope.
- guard_code_review: strict vs non-strict mode, event names.
- Config fields: gate enabled/disabled, strict mode flag.
- Graph wiring: guard_code_review imported in graph module.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.independent_code_review import (
    validate_code_review,
    guard_code_review,
    _check_env_files,
    _check_forbidden_scope,
    _check_secret_patterns,
    _check_allowed_scope,
    _extract_changed_files,
)

import tools.independent_code_review as _icr
_icr.log_event = lambda *a, **k: None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task(**kwargs) -> dict:
    base = {"id": "t-001", "title": "Test task"}
    base.update(kwargs)
    return base


def _summary(**kwargs) -> dict:
    base = {
        "files_created": ["runner/langgraph/tools/foo.py"],
        "files_modified": [],
    }
    base.update(kwargs)
    return base


_CLEAN_DIFF = """+++ b/runner/langgraph/tools/foo.py\n--- a/runner/langgraph/tools/foo.py\n+def hello():\n+    return 'world'\n"""
_EMPTY_DIFF = ""


# ---------------------------------------------------------------------------
# _extract_changed_files
# ---------------------------------------------------------------------------

def test_extract_changed_files_parses_added_lines():
    diff = "+++ b/tools/foo.py\n--- a/tools/foo.py\n+line\n"
    files = _extract_changed_files(diff)
    assert "tools/foo.py" in files


def test_extract_changed_files_skips_dev_null():
    diff = "+++ /dev/null\n--- a/tools/old.py\n"
    files = _extract_changed_files(diff)
    assert "/dev/null" not in files


def test_extract_changed_files_deduplicates():
    diff = "+++ b/tools/foo.py\n--- a/tools/foo.py\n"
    files = _extract_changed_files(diff)
    assert files.count("tools/foo.py") == 1


def test_extract_changed_files_empty_diff():
    assert _extract_changed_files("") == []


# ---------------------------------------------------------------------------
# _check_env_files
# ---------------------------------------------------------------------------

def test_env_file_dot_env_fails():
    ok, msg = _check_env_files([".env"])
    assert ok is False
    assert ".env" in msg


def test_env_file_dotenv_local_fails():
    ok, msg = _check_env_files([".env.local"])
    assert ok is False


def test_env_file_in_subdir_fails():
    ok, msg = _check_env_files(["runner/langgraph/.env"])
    assert ok is False


def test_non_env_file_passes():
    ok, _ = _check_env_files(["config.py", "tools/foo.py"])
    assert ok is True


def test_env_looking_name_passes_if_no_dot():
    ok, _ = _check_env_files(["env_utils.py"])
    assert ok is True


# ---------------------------------------------------------------------------
# _check_forbidden_scope
# ---------------------------------------------------------------------------

def test_forbidden_scope_no_ac_passes():
    ok, _ = _check_forbidden_scope(["app/routes.py"], _task())
    assert ok is True


def test_forbidden_scope_no_ac_dict_passes():
    task = _task(acceptance_criteria="do not modify UI")
    ok, _ = _check_forbidden_scope(["app/routes.py"], task)
    assert ok is True


def test_forbidden_scope_empty_string_passes():
    task = _task(acceptance_criteria={"forbidden_scope": ""})
    ok, _ = _check_forbidden_scope(["app/ui.py"], task)
    assert ok is True


def test_forbidden_scope_match_fails():
    task = _task(acceptance_criteria={"forbidden_scope": "Do not modify app/ui/ or styles/"})
    ok, msg = _check_forbidden_scope(["app/ui/button.tsx"], task)
    assert ok is False
    assert "forbidden scope" in msg


def test_forbidden_scope_no_match_passes():
    task = _task(acceptance_criteria={"forbidden_scope": "Do not modify app/ui/"})
    ok, _ = _check_forbidden_scope(["runner/langgraph/tools/foo.py"], task)
    assert ok is True


# ---------------------------------------------------------------------------
# _check_secret_patterns
# ---------------------------------------------------------------------------

def test_no_secrets_in_clean_diff_passes():
    ok, _ = _check_secret_patterns(_CLEAN_DIFF)
    assert ok is True


def test_empty_diff_passes():
    ok, _ = _check_secret_patterns("")
    assert ok is True


def test_api_key_in_addition_fails():
    diff = "+API_KEY=ABCDEFGHIJKLMNOPQRSTUVWXYZ1234\n"
    ok, msg = _check_secret_patterns(diff)
    assert ok is False
    assert "secret" in msg


def test_password_in_addition_fails():
    diff = "+password=mysupersecretpassword123\n"
    ok, msg = _check_secret_patterns(diff)
    assert ok is False


def test_aws_key_in_addition_fails():
    diff = "+AWS_ACCESS_KEY=AKIAIOSFODNN7EXAMPLE\n"
    ok, msg = _check_secret_patterns(diff)
    assert ok is False


def test_openai_key_in_addition_fails():
    diff = "+OPENAI_KEY=sk-abcdefghijklmnopqrstuvwxyz123456\n"
    ok, msg = _check_secret_patterns(diff)
    assert ok is False


def test_secret_in_removal_line_ignored():
    # Lines starting with "-" (removals) should not be flagged.
    diff = "-API_KEY=ABCDEFGHIJKLMNOPQRSTUVWXYZ1234\n"
    ok, _ = _check_secret_patterns(diff)
    assert ok is True


def test_secret_in_context_line_ignored():
    # Context lines (no leading + or -) are not additions.
    diff = " API_KEY=ABCDEFGHIJKLMNOPQRSTUVWXYZ1234\n"
    ok, _ = _check_secret_patterns(diff)
    assert ok is True


def test_hunk_header_not_flagged():
    diff = "+++ b/config.py\n"
    ok, _ = _check_secret_patterns(diff)
    assert ok is True


# ---------------------------------------------------------------------------
# _check_allowed_scope
# ---------------------------------------------------------------------------

def test_allowed_scope_no_ac_passes():
    ok, _ = _check_allowed_scope(["tools/foo.py"], _task())
    assert ok is True


def test_allowed_scope_empty_passes():
    task = _task(acceptance_criteria={"allowed_scope": ""})
    ok, _ = _check_allowed_scope(["tools/foo.py"], task)
    assert ok is True


def test_allowed_scope_list_in_scope_passes():
    task = _task(acceptance_criteria={"allowed_scope": ["runner/langgraph/tools/", "tests/"]})
    ok, _ = _check_allowed_scope(["runner/langgraph/tools/foo.py"], task)
    assert ok is True


def test_allowed_scope_string_in_scope_passes():
    task = _task(acceptance_criteria={"allowed_scope": "runner/langgraph/tools/"})
    ok, _ = _check_allowed_scope(["runner/langgraph/tools/bar.py"], task)
    assert ok is True


def test_allowed_scope_out_of_scope_fails():
    task = _task(acceptance_criteria={"allowed_scope": ["runner/langgraph/tools/"]})
    ok, msg = _check_allowed_scope(["app/ui/page.tsx"], task)
    assert ok is False
    assert "outside allowed_scope" in msg


def test_allowed_scope_none_value_ignored():
    task = _task(acceptance_criteria={"allowed_scope": ["runner/"]})
    ok, _ = _check_allowed_scope(["none", "n/a"], task)
    assert ok is True


# ---------------------------------------------------------------------------
# validate_code_review
# ---------------------------------------------------------------------------

def test_validate_all_clean_passes():
    ok, issues = validate_code_review(_CLEAN_DIFF, _summary(), _task())
    assert ok is True
    assert issues == []


def test_validate_env_file_in_summary_fails():
    summary = _summary(files_created=[".env.local"])
    ok, issues = validate_code_review(_EMPTY_DIFF, summary, _task())
    assert ok is False
    assert any(".env" in i for i in issues)


def test_validate_secret_in_diff_fails():
    diff = "+API_KEY=ABCDEFGHIJKLMNOPQRSTUVWXYZ1234\n"
    ok, issues = validate_code_review(diff, _summary(), _task())
    assert ok is False
    assert any("secret" in i for i in issues)


def test_validate_forbidden_scope_violation_fails():
    task = _task(acceptance_criteria={"forbidden_scope": "Do not touch app/ui/"})
    summary = _summary(files_modified=["app/ui/page.tsx"])
    ok, issues = validate_code_review(_EMPTY_DIFF, summary, task)
    assert ok is False
    assert any("forbidden scope" in i for i in issues)


def test_validate_multiple_issues_all_reported():
    diff = "+API_KEY=ABCDEFGHIJKLMNOPQRSTUVWXYZ1234\n"
    summary = _summary(files_created=[".env"])
    ok, issues = validate_code_review(diff, summary, _task())
    assert ok is False
    assert len(issues) >= 2


def test_validate_files_from_diff_and_summary_merged():
    diff = "+++ b/.env\n"
    summary = _summary(files_created=["app/routes.py"])
    ok, issues = validate_code_review(diff, summary, _task())
    assert ok is False


# ---------------------------------------------------------------------------
# guard_code_review
# ---------------------------------------------------------------------------

def test_guard_returns_passed_true_on_success():
    result = guard_code_review(_CLEAN_DIFF, _summary(), _task())
    assert result["passed"] is True
    assert result["issues"] == []


def test_guard_returns_passed_false_on_failure():
    diff = "+API_KEY=ABCDEFGHIJKLMNOPQRSTUVWXYZ1234\n"
    result = guard_code_review(diff, _summary(), _task())
    assert result["passed"] is False
    assert len(result["issues"]) > 0


def test_guard_strict_mode_flag_mirrored():
    result = guard_code_review(_CLEAN_DIFF, _summary(), _task(), strict_mode=True)
    assert result["strict_mode"] is True

    result2 = guard_code_review(_CLEAN_DIFF, _summary(), _task(), strict_mode=False)
    assert result2["strict_mode"] is False


def test_guard_non_strict_still_returns_issues():
    diff = "+API_KEY=ABCDEFGHIJKLMNOPQRSTUVWXYZ1234\n"
    result = guard_code_review(diff, _summary(), _task(), strict_mode=False)
    assert result["passed"] is False
    assert len(result["issues"]) > 0


def test_guard_context_accepted():
    result = guard_code_review(_CLEAN_DIFF, _summary(), _task(), context="post-check")
    assert result["passed"] is True


# ---------------------------------------------------------------------------
# Config field checks
# ---------------------------------------------------------------------------

def test_config_has_gate_enabled_field():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "independent_code_review_enabled")
    assert isinstance(cfg.independent_code_review_enabled, bool)


def test_config_has_strict_mode_field():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "independent_code_review_strict_mode")
    assert isinstance(cfg.independent_code_review_strict_mode, bool)


def test_config_gate_enabled_by_default():
    import unittest.mock as mock
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("INDEPENDENT_CODE_REVIEW_ENABLED", None)
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.independent_code_review_enabled is True


def test_config_gate_can_be_disabled_via_env():
    import unittest.mock as mock
    with mock.patch.dict(os.environ, {"INDEPENDENT_CODE_REVIEW_ENABLED": "false"}):
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.independent_code_review_enabled is False


def test_config_strict_mode_disabled_by_default():
    import unittest.mock as mock
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("INDEPENDENT_CODE_REVIEW_STRICT_MODE", None)
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.independent_code_review_strict_mode is False


def test_config_strict_mode_can_be_enabled_via_env():
    import unittest.mock as mock
    with mock.patch.dict(os.environ, {"INDEPENDENT_CODE_REVIEW_STRICT_MODE": "true"}):
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.independent_code_review_strict_mode is True


# ---------------------------------------------------------------------------
# Wiring check
# ---------------------------------------------------------------------------

def test_guard_is_imported_in_graph():
    import graph
    assert hasattr(graph, "guard_code_review")


if __name__ == "__main__":
    tests = [
        test_extract_changed_files_parses_added_lines,
        test_extract_changed_files_skips_dev_null,
        test_extract_changed_files_deduplicates,
        test_extract_changed_files_empty_diff,
        test_env_file_dot_env_fails,
        test_env_file_dotenv_local_fails,
        test_env_file_in_subdir_fails,
        test_non_env_file_passes,
        test_env_looking_name_passes_if_no_dot,
        test_forbidden_scope_no_ac_passes,
        test_forbidden_scope_no_ac_dict_passes,
        test_forbidden_scope_empty_string_passes,
        test_forbidden_scope_match_fails,
        test_forbidden_scope_no_match_passes,
        test_no_secrets_in_clean_diff_passes,
        test_empty_diff_passes,
        test_api_key_in_addition_fails,
        test_password_in_addition_fails,
        test_aws_key_in_addition_fails,
        test_openai_key_in_addition_fails,
        test_secret_in_removal_line_ignored,
        test_secret_in_context_line_ignored,
        test_hunk_header_not_flagged,
        test_allowed_scope_no_ac_passes,
        test_allowed_scope_empty_passes,
        test_allowed_scope_list_in_scope_passes,
        test_allowed_scope_string_in_scope_passes,
        test_allowed_scope_out_of_scope_fails,
        test_allowed_scope_none_value_ignored,
        test_validate_all_clean_passes,
        test_validate_env_file_in_summary_fails,
        test_validate_secret_in_diff_fails,
        test_validate_forbidden_scope_violation_fails,
        test_validate_multiple_issues_all_reported,
        test_validate_files_from_diff_and_summary_merged,
        test_guard_returns_passed_true_on_success,
        test_guard_returns_passed_false_on_failure,
        test_guard_strict_mode_flag_mirrored,
        test_guard_non_strict_still_returns_issues,
        test_guard_context_accepted,
        test_config_has_gate_enabled_field,
        test_config_has_strict_mode_field,
        test_config_gate_enabled_by_default,
        test_config_gate_can_be_disabled_via_env,
        test_config_strict_mode_disabled_by_default,
        test_config_strict_mode_can_be_enabled_via_env,
        test_guard_is_imported_in_graph,
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
