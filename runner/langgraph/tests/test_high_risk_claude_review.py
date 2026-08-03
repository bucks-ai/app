"""Unit tests for the High-Risk Claude Review Gate.

Covers:
- is_high_risk: explicit flags and keyword inference.
- build_review_prompt: structure and content.
- parse_verdict: all three verdict strings and fallback.
- guard_high_risk_claude_review: approved / rejected / needs_review / skipped /
  api-error paths; strict vs non-strict mode.
- Config fields: enabled/disabled, strict mode, model.
- Graph wiring: node and routing helper imported in graph module.
"""
import os
import sys
import traceback
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.high_risk_claude_review import (
    is_high_risk,
    build_review_prompt,
    parse_verdict,
    call_claude_review,
    call_claude_cli_review,
    guard_high_risk_claude_review,
)

# Silence log_event calls during tests.
import tools.high_risk_claude_review as _hrr
_hrr.log_event = lambda *a, **k: None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _task(**kwargs) -> dict:
    base = {"id": "t-001", "title": "Add new endpoint"}
    base.update(kwargs)
    return base


def _summary(**kwargs) -> dict:
    base = {"files_created": ["tools/foo.py"], "files_modified": []}
    base.update(kwargs)
    return base


_CLEAN_DIFF = "+++ b/tools/foo.py\n+def hello(): return 'world'\n"
_EMPTY_DIFF = ""


# ---------------------------------------------------------------------------
# is_high_risk
# ---------------------------------------------------------------------------

def test_explicit_high_risk_flag():
    assert is_high_risk(_task(high_risk=True)) is True


def test_explicit_risk_level_high():
    assert is_high_risk(_task(risk_level="high")) is True


def test_risk_level_case_insensitive():
    assert is_high_risk(_task(risk_level="HIGH")) is True


def test_no_flag_low_risk_returns_false():
    assert is_high_risk(_task(title="Update landing page copy")) is False


def test_keyword_in_title_auth():
    assert is_high_risk(_task(title="Refactor authentication flow")) is True


def test_keyword_in_title_payment():
    assert is_high_risk(_task(title="Add payment webhook handler")) is True


def test_keyword_in_title_migration():
    assert is_high_risk(_task(title="Write SQL migration for users table")) is True


def test_keyword_in_type():
    assert is_high_risk(_task(title="Routine cleanup", type="database")) is True


def test_keyword_in_description():
    assert is_high_risk(_task(
        title="Fix bug",
        description="This touches the authorization middleware",
    )) is True


def test_unrelated_task_returns_false():
    assert is_high_risk(_task(
        title="Add unit tests for formatter",
        type="backend",
        description="Cover edge cases in string formatting",
    )) is False


# ---------------------------------------------------------------------------
# build_review_prompt
# ---------------------------------------------------------------------------

def test_prompt_contains_task_title():
    prompt = build_review_prompt(_CLEAN_DIFF, _task(title="Secure admin route"), _summary())
    assert "Secure admin route" in prompt


def test_prompt_contains_diff():
    prompt = build_review_prompt(_CLEAN_DIFF, _task(), _summary())
    assert "def hello" in prompt


def test_prompt_truncates_long_diff():
    long_diff = "+" + "x" * 5000
    prompt = build_review_prompt(long_diff, _task(), _summary())
    assert "truncated" in prompt


def test_prompt_lists_changed_files():
    summary = _summary(files_modified=["app/auth.py"])
    prompt = build_review_prompt(_CLEAN_DIFF, _task(), summary)
    assert "app/auth.py" in prompt


def test_prompt_filters_none_file_entries():
    summary = _summary(files_created=["none", "n/a", "tools/foo.py"])
    prompt = build_review_prompt(_CLEAN_DIFF, _task(), summary)
    assert "tools/foo.py" in prompt


def test_prompt_requests_verdict_format():
    prompt = build_review_prompt(_CLEAN_DIFF, _task(), _summary())
    assert "APPROVED" in prompt
    assert "REJECTED" in prompt
    assert "NEEDS_REVIEW" in prompt


# ---------------------------------------------------------------------------
# parse_verdict
# ---------------------------------------------------------------------------

def test_parse_approved():
    assert parse_verdict("APPROVED: looks fine") == "approved"


def test_parse_approved_lowercase():
    assert parse_verdict("Approved: no issues") == "approved"


def test_parse_rejected():
    assert parse_verdict("REJECTED: exposes secret") == "rejected"


def test_parse_needs_review():
    assert parse_verdict("NEEDS_REVIEW: unclear intent") == "needs_review"


def test_parse_unknown_text_returns_needs_review():
    assert parse_verdict("I'm not sure about this change.") == "needs_review"


def test_parse_empty_returns_needs_review():
    assert parse_verdict("") == "needs_review"


def test_parse_none_like_returns_needs_review():
    # Non-verdict text doesn't crash, just falls back.
    assert parse_verdict("Sure, this looks okay to me.") == "needs_review"


# ---------------------------------------------------------------------------
# guard_high_risk_claude_review — non-high-risk skip
# ---------------------------------------------------------------------------

def test_guard_skips_non_high_risk_task():
    result = guard_high_risk_claude_review(
        _CLEAN_DIFF, _summary(), _task(title="Update README"), api_key="fake"
    )
    assert result["passed"] is True
    assert result["skipped"] is True
    assert result["verdict"] == "skipped"


def test_guard_skips_when_no_api_key():
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = guard_high_risk_claude_review(
            _CLEAN_DIFF, _summary(), _task(high_risk=True),
            api_key=None,
        )
    assert result["passed"] is True
    assert result["skipped"] is True


# ---------------------------------------------------------------------------
# guard_high_risk_claude_review — approved path
# ---------------------------------------------------------------------------

def test_guard_approved_passes():
    with mock.patch.object(_hrr, "call_claude_review", return_value={
        "verdict": "approved", "response_text": "APPROVED: looks safe", "error": None,
    }):
        result = guard_high_risk_claude_review(
            _CLEAN_DIFF, _summary(), _task(high_risk=True), api_key="fake"
        )
    assert result["passed"] is True
    assert result["verdict"] == "approved"
    assert result["issues"] == []
    assert result["skipped"] is False


# ---------------------------------------------------------------------------
# guard_high_risk_claude_review — rejected path
# ---------------------------------------------------------------------------

def test_guard_rejected_non_strict_warns():
    with mock.patch.object(_hrr, "call_claude_review", return_value={
        "verdict": "rejected", "response_text": "REJECTED: exposes secret key", "error": None,
    }):
        result = guard_high_risk_claude_review(
            _CLEAN_DIFF, _summary(), _task(high_risk=True),
            strict_mode=False, api_key="fake",
        )
    assert result["passed"] is False
    assert result["verdict"] == "rejected"
    assert len(result["issues"]) == 1
    assert result["strict_mode"] is False


def test_guard_rejected_strict_fails():
    with mock.patch.object(_hrr, "call_claude_review", return_value={
        "verdict": "rejected", "response_text": "REJECTED: auth bypass", "error": None,
    }):
        result = guard_high_risk_claude_review(
            _CLEAN_DIFF, _summary(), _task(high_risk=True),
            strict_mode=True, api_key="fake",
        )
    assert result["passed"] is False
    assert result["strict_mode"] is True


# ---------------------------------------------------------------------------
# guard_high_risk_claude_review — needs_review path
# ---------------------------------------------------------------------------

def test_guard_needs_review_non_strict_warns():
    with mock.patch.object(_hrr, "call_claude_review", return_value={
        "verdict": "needs_review",
        "response_text": "NEEDS_REVIEW: unclear intent",
        "error": None,
    }):
        result = guard_high_risk_claude_review(
            _CLEAN_DIFF, _summary(), _task(high_risk=True),
            strict_mode=False, api_key="fake",
        )
    assert result["passed"] is False
    assert result["verdict"] == "needs_review"


def test_guard_needs_review_strict_fails():
    with mock.patch.object(_hrr, "call_claude_review", return_value={
        "verdict": "needs_review",
        "response_text": "NEEDS_REVIEW: unclear",
        "error": None,
    }):
        result = guard_high_risk_claude_review(
            _CLEAN_DIFF, _summary(), _task(high_risk=True),
            strict_mode=True, api_key="fake",
        )
    assert result["passed"] is False
    assert result["strict_mode"] is True


# ---------------------------------------------------------------------------
# guard_high_risk_claude_review — API error path
# ---------------------------------------------------------------------------

def test_guard_api_error_is_non_blocking():
    with mock.patch.object(_hrr, "call_claude_review", return_value={
        "verdict": "needs_review", "response_text": "", "error": "Connection refused",
    }):
        result = guard_high_risk_claude_review(
            _CLEAN_DIFF, _summary(), _task(high_risk=True), api_key="fake"
        )
    assert result["passed"] is True
    assert "Connection refused" in result["issues"][0]


# ---------------------------------------------------------------------------
# Config field checks
# ---------------------------------------------------------------------------

def test_config_has_enabled_field():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "high_risk_claude_review_enabled")
    assert isinstance(cfg.high_risk_claude_review_enabled, bool)


def test_config_enabled_by_default():
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("HIGH_RISK_CLAUDE_REVIEW_ENABLED", None)
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.high_risk_claude_review_enabled is True


def test_config_can_be_disabled():
    with mock.patch.dict(os.environ, {"HIGH_RISK_CLAUDE_REVIEW_ENABLED": "false"}):
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.high_risk_claude_review_enabled is False


def test_config_has_strict_mode_field():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "high_risk_claude_review_strict_mode")
    assert isinstance(cfg.high_risk_claude_review_strict_mode, bool)


def test_config_strict_mode_disabled_by_default():
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("HIGH_RISK_CLAUDE_REVIEW_STRICT_MODE", None)
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.high_risk_claude_review_strict_mode is False


def test_config_strict_mode_can_be_enabled():
    with mock.patch.dict(os.environ, {"HIGH_RISK_CLAUDE_REVIEW_STRICT_MODE": "true"}):
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.high_risk_claude_review_strict_mode is True


def test_config_has_model_field():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "high_risk_claude_review_model")
    assert isinstance(cfg.high_risk_claude_review_model, str)


def test_config_model_default():
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("HIGH_RISK_CLAUDE_REVIEW_MODEL", None)
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.high_risk_claude_review_model == "claude-haiku-4-5-20251001"


def test_config_model_can_be_overridden():
    with mock.patch.dict(os.environ, {"HIGH_RISK_CLAUDE_REVIEW_MODEL": "claude-sonnet-4-6"}):
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.high_risk_claude_review_model == "claude-sonnet-4-6"


# ---------------------------------------------------------------------------
# State field check
# ---------------------------------------------------------------------------

def test_state_has_high_risk_review_status_field():
    from state import RunnerState
    s = RunnerState()
    assert hasattr(s, "high_risk_review_status")
    assert s.high_risk_review_status is None


# ---------------------------------------------------------------------------
# call_claude_cli_review
# ---------------------------------------------------------------------------

def test_cli_review_returns_needs_review_when_cli_missing():
    with mock.patch("shutil.which", return_value=None):
        result = call_claude_cli_review("prompt text")
    assert result["verdict"] == "needs_review"
    assert "not found" in result["error"]


def test_cli_review_parses_approved_response():
    from state import ToolResult
    with mock.patch("shutil.which", return_value="/usr/bin/claude"), \
         mock.patch("tools.shell_tools.run_command", return_value=ToolResult(
             tool="shell", success=True, output="APPROVED: no issues found"
         )):
        result = call_claude_cli_review("prompt text")
    assert result["verdict"] == "approved"
    assert result["error"] is None


def test_cli_review_parses_rejected_response():
    from state import ToolResult
    with mock.patch("shutil.which", return_value="/usr/bin/claude"), \
         mock.patch("tools.shell_tools.run_command", return_value=ToolResult(
             tool="shell", success=True, output="REJECTED: exposes credentials"
         )):
        result = call_claude_cli_review("prompt text")
    assert result["verdict"] == "rejected"


def test_cli_review_non_zero_exit_returns_needs_review():
    from state import ToolResult
    with mock.patch("shutil.which", return_value="/usr/bin/claude"), \
         mock.patch("tools.shell_tools.run_command", return_value=ToolResult(
             tool="shell", success=False, output="", error="timeout"
         )):
        result = call_claude_cli_review("prompt text")
    assert result["verdict"] == "needs_review"
    assert result["error"] is not None


# ---------------------------------------------------------------------------
# guard — subscription mode fallback paths
# ---------------------------------------------------------------------------

def test_guard_subscription_mode_uses_cli_when_no_api_key():
    """In subscription mode without API key, the guard calls the CLI instead of skipping."""
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with mock.patch.object(_hrr, "call_claude_cli_review", return_value={
            "verdict": "approved", "response_text": "APPROVED: safe", "error": None,
        }) as mock_cli, \
             mock.patch("shutil.which", return_value="/usr/bin/claude"):
            result = guard_high_risk_claude_review(
                _CLEAN_DIFF, _summary(), _task(high_risk=True),
                claude_auth_mode="subscription",
                api_key=None,
            )
    mock_cli.assert_called_once()
    assert result["passed"] is True
    assert result["skipped"] is False
    assert result["verdict"] == "approved"


def test_guard_subscription_mode_no_cli_skips():
    """In subscription mode without API key and no CLI, the guard skips gracefully."""
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with mock.patch("shutil.which", return_value=None):
            result = guard_high_risk_claude_review(
                _CLEAN_DIFF, _summary(), _task(high_risk=True),
                claude_auth_mode="subscription",
                api_key=None,
            )
    assert result["passed"] is True
    assert result["skipped"] is True


def test_guard_api_key_mode_still_skips_without_key():
    """In api_key mode (default) without a key the gate still skips — no regression."""
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        result = guard_high_risk_claude_review(
            _CLEAN_DIFF, _summary(), _task(high_risk=True),
            claude_auth_mode="api_key",
            api_key=None,
        )
    assert result["passed"] is True
    assert result["skipped"] is True


def test_guard_subscription_mode_cli_rejected_non_strict_warns():
    """CLI returns REJECTED in subscription mode, non-strict → warned, not blocking."""
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with mock.patch.object(_hrr, "call_claude_cli_review", return_value={
            "verdict": "rejected", "response_text": "REJECTED: auth bypass", "error": None,
        }), mock.patch("shutil.which", return_value="/usr/bin/claude"):
            result = guard_high_risk_claude_review(
                _CLEAN_DIFF, _summary(), _task(high_risk=True),
                claude_auth_mode="subscription",
                strict_mode=False,
                api_key=None,
            )
    assert result["passed"] is False
    assert result["strict_mode"] is False
    assert len(result["issues"]) == 1


def test_guard_subscription_mode_cli_rejected_strict_fails():
    """CLI returns REJECTED in subscription mode, strict → hard failure."""
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with mock.patch.object(_hrr, "call_claude_cli_review", return_value={
            "verdict": "rejected", "response_text": "REJECTED: secret leak", "error": None,
        }), mock.patch("shutil.which", return_value="/usr/bin/claude"):
            result = guard_high_risk_claude_review(
                _CLEAN_DIFF, _summary(), _task(high_risk=True),
                claude_auth_mode="subscription",
                strict_mode=True,
                api_key=None,
            )
    assert result["passed"] is False
    assert result["strict_mode"] is True


def test_guard_subscription_mode_cli_error_non_blocking():
    """CLI error in subscription mode → non-blocking (same as SDK error path)."""
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("ANTHROPIC_API_KEY", None)
        with mock.patch.object(_hrr, "call_claude_cli_review", return_value={
            "verdict": "needs_review", "response_text": "", "error": "timeout",
        }), mock.patch("shutil.which", return_value="/usr/bin/claude"):
            result = guard_high_risk_claude_review(
                _CLEAN_DIFF, _summary(), _task(high_risk=True),
                claude_auth_mode="subscription",
                api_key=None,
            )
    assert result["passed"] is True
    assert "timeout" in result["issues"][0]


def test_guard_subscription_mode_api_key_takes_precedence():
    """When subscription mode AND an API key is present, the SDK path is used."""
    with mock.patch.object(_hrr, "call_claude_review", return_value={
        "verdict": "approved", "response_text": "APPROVED", "error": None,
    }) as mock_sdk, \
         mock.patch.object(_hrr, "call_claude_cli_review") as mock_cli:
        result = guard_high_risk_claude_review(
            _CLEAN_DIFF, _summary(), _task(high_risk=True),
            claude_auth_mode="subscription",
            api_key="sk-ant-test",
        )
    mock_sdk.assert_called_once()
    mock_cli.assert_not_called()
    assert result["passed"] is True


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------

def test_guard_is_imported_in_graph():
    import graph
    assert hasattr(graph, "guard_high_risk_claude_review")


def test_node_exists_in_graph():
    import graph
    assert hasattr(graph, "check_high_risk_claude_review")


def test_routing_helper_exists_in_graph():
    import graph
    assert hasattr(graph, "_route_after_high_risk_review")


if __name__ == "__main__":
    tests = [
        test_explicit_high_risk_flag,
        test_explicit_risk_level_high,
        test_risk_level_case_insensitive,
        test_no_flag_low_risk_returns_false,
        test_keyword_in_title_auth,
        test_keyword_in_title_payment,
        test_keyword_in_title_migration,
        test_keyword_in_type,
        test_keyword_in_description,
        test_unrelated_task_returns_false,
        test_prompt_contains_task_title,
        test_prompt_contains_diff,
        test_prompt_truncates_long_diff,
        test_prompt_lists_changed_files,
        test_prompt_filters_none_file_entries,
        test_prompt_requests_verdict_format,
        test_parse_approved,
        test_parse_approved_lowercase,
        test_parse_rejected,
        test_parse_needs_review,
        test_parse_unknown_text_returns_needs_review,
        test_parse_empty_returns_needs_review,
        test_parse_none_like_returns_needs_review,
        test_guard_skips_non_high_risk_task,
        test_guard_skips_when_no_api_key,
        test_guard_approved_passes,
        test_guard_rejected_non_strict_warns,
        test_guard_rejected_strict_fails,
        test_guard_needs_review_non_strict_warns,
        test_guard_needs_review_strict_fails,
        test_guard_api_error_is_non_blocking,
        test_cli_review_returns_needs_review_when_cli_missing,
        test_cli_review_parses_approved_response,
        test_cli_review_parses_rejected_response,
        test_cli_review_non_zero_exit_returns_needs_review,
        test_guard_subscription_mode_uses_cli_when_no_api_key,
        test_guard_subscription_mode_no_cli_skips,
        test_guard_api_key_mode_still_skips_without_key,
        test_guard_subscription_mode_cli_rejected_non_strict_warns,
        test_guard_subscription_mode_cli_rejected_strict_fails,
        test_guard_subscription_mode_cli_error_non_blocking,
        test_guard_subscription_mode_api_key_takes_precedence,
        test_config_has_enabled_field,
        test_config_enabled_by_default,
        test_config_can_be_disabled,
        test_config_has_strict_mode_field,
        test_config_strict_mode_disabled_by_default,
        test_config_strict_mode_can_be_enabled,
        test_config_has_model_field,
        test_config_model_default,
        test_config_model_can_be_overridden,
        test_state_has_high_risk_review_status_field,
        test_guard_is_imported_in_graph,
        test_node_exists_in_graph,
        test_routing_helper_exists_in_graph,
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
