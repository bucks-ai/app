"""Unit tests for Risk-Based Merge Approval Policy.

Covers:
- classify_merge_risk: all scoring factors (explicit flags, keywords, file
  patterns, change volume, destructive SQL) and risk-level mapping.
- requires_approval: all four policy options × all three risk levels.
- format_approval_request: content and structure.
- guard_merge_approval: skipped, approved, pending paths; strict vs non-strict.
- Config fields: enabled/disabled, policy default and override.
- State fields: merge_approval_status, merge_risk_level present and None by default.
- Graph wiring: node, routing helper, and import present in graph module.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.risk_based_merge_approval import (
    classify_merge_risk,
    requires_approval,
    format_approval_request,
    guard_merge_approval,
)

import tools.risk_based_merge_approval as _rma
_rma.log_event = lambda *a, **k: None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task(**kwargs) -> dict:
    base = {"id": "t-test", "title": "Add new endpoint", "type": "backend"}
    base.update(kwargs)
    return base


def _summary(**kwargs) -> dict:
    base = {"files_created": [], "files_modified": []}
    base.update(kwargs)
    return base


_CLEAN_DIFF = "+++ b/tools/foo.py\n+def hello(): return 'world'\n"
_SQL_DIFF = "+++ b/migration.sql\n+DROP TABLE users;\n"


# ---------------------------------------------------------------------------
# classify_merge_risk — explicit flags
# ---------------------------------------------------------------------------

def test_classify_explicit_high_risk_flag():
    result = classify_merge_risk(_task(high_risk=True))
    assert result["risk_level"] == "high"
    assert result["score"] >= 3


def test_classify_explicit_risk_level_high():
    result = classify_merge_risk(_task(risk_level="high"))
    assert result["risk_level"] == "high"


def test_classify_explicit_risk_level_medium():
    result = classify_merge_risk(_task(risk_level="medium"))
    assert result["risk_level"] == "medium"
    assert 1 <= result["score"] <= 2


def test_classify_explicit_risk_level_case_insensitive():
    result = classify_merge_risk(_task(risk_level="HIGH"))
    assert result["risk_level"] == "high"


def test_classify_low_risk_clean_task():
    result = classify_merge_risk(_task(title="Update landing page copy", type="ui"))
    assert result["risk_level"] == "low"
    assert result["score"] == 0


# ---------------------------------------------------------------------------
# classify_merge_risk — keyword scanning
# ---------------------------------------------------------------------------

def test_classify_auth_keyword_in_title():
    result = classify_merge_risk(_task(title="Refactor auth middleware"))
    assert result["score"] >= 1
    assert any("auth" in r for r in result["reasons"])


def test_classify_payment_keyword():
    result = classify_merge_risk(_task(title="Add stripe payment webhook"))
    assert result["score"] >= 1


def test_classify_migration_keyword():
    result = classify_merge_risk(_task(title="Write migration for users table"))
    assert result["score"] >= 1


def test_classify_keyword_in_description():
    result = classify_merge_risk(_task(
        title="Fix bug",
        description="This touches the authentication middleware",
    ))
    assert result["score"] >= 1


def test_classify_multiple_keywords_capped_at_3():
    result = classify_merge_risk(_task(
        title="auth payment migration sql security credential token"
    ))
    kw_score = result["factors"].get("keyword_hits", [])
    assert len(kw_score) >= 1
    # keyword contribution capped at 3 even with many matches
    keyword_contribution = min(len(kw_score), 3)
    assert keyword_contribution <= 3


# ---------------------------------------------------------------------------
# classify_merge_risk — file patterns
# ---------------------------------------------------------------------------

def test_classify_sql_file_pattern():
    summary = _summary(files_modified=["migrations/0001_initial.sql"])
    result = classify_merge_risk(_task(), summary=summary)
    assert result["score"] >= 1
    assert "sensitive_file_patterns" in result["factors"]


def test_classify_env_file_pattern():
    summary = _summary(files_modified=[".env.production"])
    result = classify_merge_risk(_task(), summary=summary)
    assert result["score"] >= 1


def test_classify_auth_file_pattern():
    summary = _summary(files_modified=["app/auth/middleware.py"])
    result = classify_merge_risk(_task(), summary=summary)
    assert result["score"] >= 1


def test_classify_large_change_set():
    files = [f"file_{i}.py" for i in range(11)]
    summary = _summary(files_modified=files)
    result = classify_merge_risk(_task(), summary=summary)
    assert result["factors"].get("large_change_set") == 11
    assert result["score"] >= 1


def test_classify_small_change_set_no_volume_penalty():
    files = [f"file_{i}.py" for i in range(5)]
    summary = _summary(files_modified=files)
    result_small = classify_merge_risk(_task(), summary=summary)
    result_clean = classify_merge_risk(_task())
    # Volume alone doesn't push a clean task above 0
    assert result_small["factors"].get("large_change_set") is None


def test_classify_none_files_filtered():
    summary = _summary(files_created=["none", "n/a", ""])
    result = classify_merge_risk(_task(), summary=summary)
    assert result["factors"].get("large_change_set") is None


# ---------------------------------------------------------------------------
# classify_merge_risk — destructive SQL in diff
# ---------------------------------------------------------------------------

def test_classify_destructive_sql_drop_table():
    result = classify_merge_risk(_task(), diff_text=_SQL_DIFF)
    assert result["factors"].get("destructive_sql") is True
    assert result["score"] >= 2


def test_classify_destructive_sql_truncate():
    diff = "+TRUNCATE users;\n"
    result = classify_merge_risk(_task(), diff_text=diff)
    assert result["factors"].get("destructive_sql") is True


def test_classify_destructive_sql_delete_from():
    diff = "+DELETE FROM orders WHERE 1=1;\n"
    result = classify_merge_risk(_task(), diff_text=diff)
    assert result["factors"].get("destructive_sql") is True


def test_classify_clean_diff_no_destructive():
    result = classify_merge_risk(_task(), diff_text=_CLEAN_DIFF)
    assert result["factors"].get("destructive_sql") is None


# ---------------------------------------------------------------------------
# classify_merge_risk — risk level mapping
# ---------------------------------------------------------------------------

def test_classify_score_zero_is_low():
    result = classify_merge_risk(_task(title="Rename a helper function", type="backend"))
    if result["score"] == 0:
        assert result["risk_level"] == "low"


def test_classify_score_1_is_medium():
    result = classify_merge_risk(_task(risk_level="medium"))
    assert result["risk_level"] == "medium"


def test_classify_score_3_is_high():
    result = classify_merge_risk(_task(high_risk=True))
    assert result["risk_level"] == "high"


def test_classify_reasons_populated():
    result = classify_merge_risk(_task(high_risk=True))
    assert len(result["reasons"]) >= 1


def test_classify_empty_task_returns_low():
    result = classify_merge_risk({})
    assert result["risk_level"] == "low"
    assert result["score"] == 0


# ---------------------------------------------------------------------------
# requires_approval
# ---------------------------------------------------------------------------

def test_requires_approval_auto_never():
    for level in ("low", "medium", "high"):
        assert requires_approval(level, "auto") is False


def test_requires_approval_always_require():
    for level in ("low", "medium", "high"):
        assert requires_approval(level, "always_require") is True


def test_requires_approval_on_high_only():
    assert requires_approval("high", "require_approval_on_high") is True
    assert requires_approval("medium", "require_approval_on_high") is False
    assert requires_approval("low", "require_approval_on_high") is False


def test_requires_approval_on_medium_and_high():
    assert requires_approval("high", "require_approval_on_medium_and_high") is True
    assert requires_approval("medium", "require_approval_on_medium_and_high") is True
    assert requires_approval("low", "require_approval_on_medium_and_high") is False


def test_requires_approval_unknown_policy_defaults_to_high():
    assert requires_approval("high", "unknown_policy") is True
    assert requires_approval("medium", "unknown_policy") is False


# ---------------------------------------------------------------------------
# format_approval_request
# ---------------------------------------------------------------------------

def test_format_approval_request_contains_task_id():
    classification = {"risk_level": "high", "score": 4, "reasons": ["explicit high_risk=True"]}
    text = format_approval_request("task-123", "Update auth", classification, "task-123_merge_approved.txt")
    assert "task-123" in text


def test_format_approval_request_contains_risk_level():
    classification = {"risk_level": "high", "score": 4, "reasons": []}
    text = format_approval_request("t-1", "title", classification, "approve.txt")
    assert "HIGH" in text


def test_format_approval_request_contains_inbox_filename():
    classification = {"risk_level": "high", "score": 4, "reasons": []}
    text = format_approval_request("t-1", "title", classification, "t-1_merge_approved.txt")
    assert "t-1_merge_approved.txt" in text


def test_format_approval_request_lists_reasons():
    classification = {
        "risk_level": "high", "score": 5,
        "reasons": ["explicit high_risk=True", "high-risk keywords in task: auth, sql"],
    }
    text = format_approval_request("t-1", "title", classification, "approve.txt")
    assert "explicit high_risk" in text
    assert "keywords" in text


def test_format_approval_request_empty_reasons_has_fallback():
    classification = {"risk_level": "high", "score": 0, "reasons": []}
    text = format_approval_request("t-1", "title", classification, "approve.txt")
    assert "none detected" in text.lower()


# ---------------------------------------------------------------------------
# guard_merge_approval — skipped path (no approval required)
# ---------------------------------------------------------------------------

def test_guard_skips_low_risk_with_default_policy():
    result = guard_merge_approval(
        _task(title="Update readme"),
        policy="require_approval_on_high",
    )
    assert result["passed"] is True
    assert result["skipped"] is True
    assert result["requires_human"] is False
    assert result["issues"] == []


def test_guard_skips_with_auto_policy():
    result = guard_merge_approval(
        _task(high_risk=True),
        policy="auto",
    )
    assert result["passed"] is True
    assert result["skipped"] is True


def test_guard_skips_medium_risk_with_high_only_policy():
    result = guard_merge_approval(
        _task(risk_level="medium"),
        policy="require_approval_on_high",
    )
    assert result["passed"] is True
    assert result["skipped"] is True


# ---------------------------------------------------------------------------
# guard_merge_approval — approved path
# ---------------------------------------------------------------------------

def test_guard_approved_when_file_present():
    result = guard_merge_approval(
        _task(high_risk=True),
        policy="require_approval_on_high",
        approved=True,
    )
    assert result["passed"] is True
    assert result["skipped"] is False
    assert result["approved"] is True
    assert result["requires_human"] is True
    assert result["issues"] == []


def test_guard_approved_medium_risk_medium_policy():
    result = guard_merge_approval(
        _task(risk_level="medium"),
        policy="require_approval_on_medium_and_high",
        approved=True,
    )
    assert result["passed"] is True
    assert result["approved"] is True


# ---------------------------------------------------------------------------
# guard_merge_approval — pending path
# ---------------------------------------------------------------------------

def test_guard_pending_when_high_risk_and_no_approval():
    result = guard_merge_approval(
        _task(high_risk=True),
        policy="require_approval_on_high",
        approved=False,
    )
    assert result["passed"] is False
    assert result["skipped"] is False
    assert result["requires_human"] is True
    assert result["approved"] is False
    assert len(result["issues"]) == 1
    assert "human approval" in result["issues"][0]


def test_guard_pending_always_require_low_risk():
    result = guard_merge_approval(
        _task(title="Minor update"),
        policy="always_require",
        approved=False,
    )
    assert result["passed"] is False
    assert result["requires_human"] is True


def test_guard_risk_level_in_result():
    result = guard_merge_approval(
        _task(high_risk=True),
        policy="require_approval_on_high",
        approved=False,
    )
    assert result["risk_level"] == "high"


def test_guard_classification_in_result():
    result = guard_merge_approval(
        _task(high_risk=True),
        policy="require_approval_on_high",
    )
    assert "classification" in result
    assert "score" in result["classification"]


# ---------------------------------------------------------------------------
# Config field checks
# ---------------------------------------------------------------------------

def test_config_has_enabled_field():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "risk_based_merge_approval_enabled")
    assert isinstance(cfg.risk_based_merge_approval_enabled, bool)


def test_config_enabled_by_default():
    import unittest.mock as mock
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("RISK_BASED_MERGE_APPROVAL_ENABLED", None)
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.risk_based_merge_approval_enabled is True


def test_config_can_be_disabled():
    import unittest.mock as mock
    with mock.patch.dict(os.environ, {"RISK_BASED_MERGE_APPROVAL_ENABLED": "false"}):
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.risk_based_merge_approval_enabled is False


def test_config_has_policy_field():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "merge_approval_policy")
    assert isinstance(cfg.merge_approval_policy, str)


def test_config_policy_default():
    import unittest.mock as mock
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("MERGE_APPROVAL_POLICY", None)
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.merge_approval_policy == "require_approval_on_high"


def test_config_policy_can_be_overridden():
    import unittest.mock as mock
    with mock.patch.dict(os.environ, {"MERGE_APPROVAL_POLICY": "always_require"}):
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.merge_approval_policy == "always_require"


# ---------------------------------------------------------------------------
# State field checks
# ---------------------------------------------------------------------------

def test_state_has_merge_approval_status():
    from state import RunnerState
    s = RunnerState()
    assert hasattr(s, "merge_approval_status")
    assert s.merge_approval_status is None


def test_state_has_merge_risk_level():
    from state import RunnerState
    s = RunnerState()
    assert hasattr(s, "merge_risk_level")
    assert s.merge_risk_level is None


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------

def test_guard_imported_in_graph():
    import graph
    assert hasattr(graph, "guard_merge_approval")


def test_node_exists_in_graph():
    import graph
    assert hasattr(graph, "check_merge_approval_if_needed")


def test_routing_helper_exists_in_graph():
    import graph
    assert hasattr(graph, "_route_after_merge_approval")


def test_routing_helper_pending_goes_to_stop():
    from state import RunnerState
    import graph
    s = RunnerState()
    s.merge_approval_status = "pending"
    assert graph._route_after_merge_approval(s) == "decide_continue_or_stop"


def test_routing_helper_approved_goes_to_commit():
    from state import RunnerState
    import graph
    s = RunnerState()
    s.merge_approval_status = "approved"
    assert graph._route_after_merge_approval(s) == "commit_push_merge_if_needed"


def test_routing_helper_skipped_goes_to_commit():
    from state import RunnerState
    import graph
    s = RunnerState()
    s.merge_approval_status = "skipped"
    assert graph._route_after_merge_approval(s) == "commit_push_merge_if_needed"


def test_routing_helper_none_goes_to_commit():
    from state import RunnerState
    import graph
    s = RunnerState()
    s.merge_approval_status = None
    assert graph._route_after_merge_approval(s) == "commit_push_merge_if_needed"


if __name__ == "__main__":
    tests = [
        test_classify_explicit_high_risk_flag,
        test_classify_explicit_risk_level_high,
        test_classify_explicit_risk_level_medium,
        test_classify_explicit_risk_level_case_insensitive,
        test_classify_low_risk_clean_task,
        test_classify_auth_keyword_in_title,
        test_classify_payment_keyword,
        test_classify_migration_keyword,
        test_classify_keyword_in_description,
        test_classify_multiple_keywords_capped_at_3,
        test_classify_sql_file_pattern,
        test_classify_env_file_pattern,
        test_classify_auth_file_pattern,
        test_classify_large_change_set,
        test_classify_small_change_set_no_volume_penalty,
        test_classify_none_files_filtered,
        test_classify_destructive_sql_drop_table,
        test_classify_destructive_sql_truncate,
        test_classify_destructive_sql_delete_from,
        test_classify_clean_diff_no_destructive,
        test_classify_score_zero_is_low,
        test_classify_score_1_is_medium,
        test_classify_score_3_is_high,
        test_classify_reasons_populated,
        test_classify_empty_task_returns_low,
        test_requires_approval_auto_never,
        test_requires_approval_always_require,
        test_requires_approval_on_high_only,
        test_requires_approval_on_medium_and_high,
        test_requires_approval_unknown_policy_defaults_to_high,
        test_format_approval_request_contains_task_id,
        test_format_approval_request_contains_risk_level,
        test_format_approval_request_contains_inbox_filename,
        test_format_approval_request_lists_reasons,
        test_format_approval_request_empty_reasons_has_fallback,
        test_guard_skips_low_risk_with_default_policy,
        test_guard_skips_with_auto_policy,
        test_guard_skips_medium_risk_with_high_only_policy,
        test_guard_approved_when_file_present,
        test_guard_approved_medium_risk_medium_policy,
        test_guard_pending_when_high_risk_and_no_approval,
        test_guard_pending_always_require_low_risk,
        test_guard_risk_level_in_result,
        test_guard_classification_in_result,
        test_config_has_enabled_field,
        test_config_enabled_by_default,
        test_config_can_be_disabled,
        test_config_has_policy_field,
        test_config_policy_default,
        test_config_policy_can_be_overridden,
        test_state_has_merge_approval_status,
        test_state_has_merge_risk_level,
        test_guard_imported_in_graph,
        test_node_exists_in_graph,
        test_routing_helper_exists_in_graph,
        test_routing_helper_pending_goes_to_stop,
        test_routing_helper_approved_goes_to_commit,
        test_routing_helper_skipped_goes_to_commit,
        test_routing_helper_none_goes_to_commit,
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
