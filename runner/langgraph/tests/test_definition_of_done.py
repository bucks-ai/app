"""Unit tests for the Definition of Done enforcement gate.

Runs standalone (no pytest dependency):

    python tests/test_definition_of_done.py

Covers:
- validate_definition_of_done: files_touched, check_not_failed,
  output_present, success_evidence checks.
- guard_definition_of_done: strict vs non-strict mode logging.
- Config fields: gate enabled/disabled, strict mode flag.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.definition_of_done import (
    validate_definition_of_done,
    guard_definition_of_done,
    _MIN_OUTPUT_LENGTH,
)

import tools.definition_of_done as _dod
_dod.log_event = lambda *a, **k: None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _summary(**kwargs) -> dict:
    base = {
        "files_created": ["tools/foo.py"],
        "files_modified": [],
        "check_result": None,
    }
    base.update(kwargs)
    return base


def _task(**kwargs) -> dict:
    base = {"id": "t-001", "title": "Add feature"}
    base.update(kwargs)
    return base


_GOOD_OUTPUT = "x" * _MIN_OUTPUT_LENGTH


# ---------------------------------------------------------------------------
# validate_definition_of_done
# ---------------------------------------------------------------------------

def test_all_checks_pass_returns_ok():
    ok, issues = validate_definition_of_done(_summary(), _task(), _GOOD_OUTPUT)
    assert ok is True
    assert issues == []


def test_no_files_touched_fails():
    ok, issues = validate_definition_of_done(
        _summary(files_created=[], files_modified=[]), _task(), _GOOD_OUTPUT
    )
    assert ok is False
    assert any("no files" in i for i in issues)


def test_files_modified_satisfies_files_touched():
    ok, issues = validate_definition_of_done(
        _summary(files_created=[], files_modified=["tools/bar.py"]), _task(), _GOOD_OUTPUT
    )
    assert ok is True


def test_empty_string_files_ignored():
    ok, issues = validate_definition_of_done(
        _summary(files_created=[""], files_modified=[" "]), _task(), _GOOD_OUTPUT
    )
    assert ok is False
    assert any("no files" in i for i in issues)


def test_none_values_in_files_ignored():
    ok, issues = validate_definition_of_done(
        _summary(files_created=[None], files_modified=["n/a"]), _task(), _GOOD_OUTPUT
    )
    assert ok is False


def test_check_result_false_fails():
    ok, issues = validate_definition_of_done(
        _summary(check_result=False), _task(), _GOOD_OUTPUT
    )
    assert ok is False
    assert any("check result" in i for i in issues)


def test_check_result_none_passes():
    ok, issues = validate_definition_of_done(
        _summary(check_result=None), _task(), _GOOD_OUTPUT
    )
    assert ok is True


def test_check_result_true_passes():
    ok, issues = validate_definition_of_done(
        _summary(check_result=True), _task(), _GOOD_OUTPUT
    )
    assert ok is True


def test_output_too_short_fails():
    short_output = "x" * (_MIN_OUTPUT_LENGTH - 1)
    ok, issues = validate_definition_of_done(_summary(), _task(), short_output)
    assert ok is False
    assert any("too short" in i for i in issues)


def test_output_at_min_length_passes():
    ok, issues = validate_definition_of_done(
        _summary(), _task(), "x" * _MIN_OUTPUT_LENGTH
    )
    assert ok is True


def test_output_empty_fails():
    ok, issues = validate_definition_of_done(_summary(), _task(), "")
    assert ok is False


def test_output_whitespace_only_fails():
    ok, issues = validate_definition_of_done(_summary(), _task(), "   ")
    assert ok is False


def test_no_success_evidence_in_ac_passes():
    task = _task(acceptance_criteria={"allowed_scope": ["tools/"], "forbidden_scope": []})
    ok, issues = validate_definition_of_done(_summary(), task, _GOOD_OUTPUT)
    assert ok is True


def test_success_evidence_matched_passes():
    task = _task(acceptance_criteria={"success_evidence": "gate validates worker output"})
    output = _GOOD_OUTPUT + " gate validates worker output"
    ok, issues = validate_definition_of_done(_summary(), task, output)
    assert ok is True


def test_success_evidence_not_matched_fails():
    task = _task(acceptance_criteria={"success_evidence": "database migration applied"})
    ok, issues = validate_definition_of_done(_summary(), task, _GOOD_OUTPUT)
    assert ok is False
    assert any("success evidence" in i for i in issues)


def test_success_evidence_partial_keyword_match_passes():
    task = _task(acceptance_criteria={"success_evidence": "migration applied successfully"})
    # "migration" and "applied" appear in output — 2/3 keywords >= threshold of 1
    output = _GOOD_OUTPUT + " migration applied"
    ok, issues = validate_definition_of_done(_summary(), task, output)
    assert ok is True


def test_success_evidence_empty_string_skipped():
    task = _task(acceptance_criteria={"success_evidence": ""})
    ok, issues = validate_definition_of_done(_summary(), task, _GOOD_OUTPUT)
    assert ok is True


def test_success_evidence_only_short_words_skipped():
    task = _task(acceptance_criteria={"success_evidence": "ok if it"})
    ok, issues = validate_definition_of_done(_summary(), task, _GOOD_OUTPUT)
    assert ok is True


def test_no_ac_field_skips_evidence_check():
    task = _task()
    ok, issues = validate_definition_of_done(_summary(), task, _GOOD_OUTPUT)
    assert ok is True


def test_ac_not_dict_skips_evidence_check():
    task = _task(acceptance_criteria="some string description")
    ok, issues = validate_definition_of_done(_summary(), task, _GOOD_OUTPUT)
    assert ok is True


def test_multiple_failures_reported():
    ok, issues = validate_definition_of_done(
        _summary(files_created=[], files_modified=[], check_result=False),
        _task(),
        "",
    )
    assert ok is False
    assert len(issues) >= 2


# ---------------------------------------------------------------------------
# guard_definition_of_done
# ---------------------------------------------------------------------------

def test_guard_returns_passed_true_on_success():
    result = guard_definition_of_done(_summary(), _task(), _GOOD_OUTPUT)
    assert result["passed"] is True
    assert result["issues"] == []


def test_guard_returns_passed_false_on_failure():
    result = guard_definition_of_done(
        _summary(files_created=[], files_modified=[]), _task(), _GOOD_OUTPUT
    )
    assert result["passed"] is False
    assert len(result["issues"]) > 0


def test_guard_strict_mode_flag_mirrored():
    result = guard_definition_of_done(_summary(), _task(), _GOOD_OUTPUT, strict_mode=True)
    assert result["strict_mode"] is True

    result2 = guard_definition_of_done(_summary(), _task(), _GOOD_OUTPUT, strict_mode=False)
    assert result2["strict_mode"] is False


def test_guard_non_strict_still_returns_issues():
    result = guard_definition_of_done(
        _summary(files_created=[], files_modified=[]), _task(), _GOOD_OUTPUT, strict_mode=False
    )
    assert result["passed"] is False
    assert len(result["issues"]) > 0


def test_guard_context_accepted():
    result = guard_definition_of_done(
        _summary(), _task(), _GOOD_OUTPUT, context="post-worker-run"
    )
    assert result["passed"] is True


# ---------------------------------------------------------------------------
# Config field checks
# ---------------------------------------------------------------------------

def test_config_has_gate_enabled_field():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "definition_of_done_gate_enabled")
    assert isinstance(cfg.definition_of_done_gate_enabled, bool)


def test_config_has_strict_mode_field():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "definition_of_done_strict_mode")
    assert isinstance(cfg.definition_of_done_strict_mode, bool)


def test_config_gate_enabled_by_default():
    import unittest.mock as mock
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("DEFINITION_OF_DONE_GATE_ENABLED", None)
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.definition_of_done_gate_enabled is True


def test_config_gate_can_be_disabled_via_env():
    import unittest.mock as mock
    with mock.patch.dict(os.environ, {"DEFINITION_OF_DONE_GATE_ENABLED": "false"}):
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.definition_of_done_gate_enabled is False


def test_config_strict_mode_disabled_by_default():
    import unittest.mock as mock
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("DEFINITION_OF_DONE_STRICT_MODE", None)
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.definition_of_done_strict_mode is False


def test_config_strict_mode_can_be_enabled_via_env():
    import unittest.mock as mock
    with mock.patch.dict(os.environ, {"DEFINITION_OF_DONE_STRICT_MODE": "true"}):
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.definition_of_done_strict_mode is True


# ---------------------------------------------------------------------------
# Wiring checks
# ---------------------------------------------------------------------------

def test_guard_is_imported_in_graph():
    import graph
    assert hasattr(graph, "guard_definition_of_done")


if __name__ == "__main__":
    tests = [
        test_all_checks_pass_returns_ok,
        test_no_files_touched_fails,
        test_files_modified_satisfies_files_touched,
        test_empty_string_files_ignored,
        test_none_values_in_files_ignored,
        test_check_result_false_fails,
        test_check_result_none_passes,
        test_check_result_true_passes,
        test_output_too_short_fails,
        test_output_at_min_length_passes,
        test_output_empty_fails,
        test_output_whitespace_only_fails,
        test_no_success_evidence_in_ac_passes,
        test_success_evidence_matched_passes,
        test_success_evidence_not_matched_fails,
        test_success_evidence_partial_keyword_match_passes,
        test_success_evidence_empty_string_skipped,
        test_success_evidence_only_short_words_skipped,
        test_no_ac_field_skips_evidence_check,
        test_ac_not_dict_skips_evidence_check,
        test_multiple_failures_reported,
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
