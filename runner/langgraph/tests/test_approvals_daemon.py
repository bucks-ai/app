"""Unit tests for approvals_daemon.py's startup validation and config wiring.

Runs standalone (no pytest dependency), mirroring the other test modules:

    python tests/test_approvals_daemon.py

No live Slack calls anywhere: these tests only exercise validate_startup_config
(pure) and the RunnerConfig fields/properties it reads. ApprovalsDaemon itself
(which imports slack_sdk and opens a socket connection) is intentionally not
instantiated here — that would require a live/mocked Slack Socket Mode
connection, which is out of scope for CI per the task brief ("no live Slack
calls in CI").
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from config import get_config
from approvals_daemon import validate_startup_config


def _cfg(**env):
    """Fresh config with only the given env vars set, isolated from the real .env."""
    keys = ("SLACK_INTERACTIVE_APPROVALS", "SLACK_BOT_TOKEN", "SLACK_APP_TOKEN", "SLACK_CHANNEL_ID")
    saved = {k: os.environ.get(k) for k in keys}
    for k in keys:
        os.environ.pop(k, None)
    os.environ.update(env)
    config._config = None
    try:
        return get_config()
    finally:
        for k in keys:
            if saved[k] is None:
                os.environ.pop(k, None)
            else:
                os.environ[k] = saved[k]
        config._config = None


# ---------------------------------------------------------------------------
# Config field/property wiring
# ---------------------------------------------------------------------------

def test_slack_interactive_approvals_defaults_false():
    cfg = _cfg()
    assert cfg.slack_interactive_approvals is False


def test_slack_interactive_approvals_true_when_set():
    cfg = _cfg(SLACK_INTERACTIVE_APPROVALS="true")
    assert cfg.slack_interactive_approvals is True


def test_slack_tokens_default_none():
    cfg = _cfg()
    assert cfg.slack_bot_token is None
    assert cfg.slack_app_token is None
    assert cfg.slack_channel_id is None


def test_slack_tokens_load_from_env():
    cfg = _cfg(SLACK_BOT_TOKEN="xoxb-fake", SLACK_APP_TOKEN="xapp-fake", SLACK_CHANNEL_ID="C123")
    assert cfg.slack_bot_token == "xoxb-fake"
    assert cfg.slack_app_token == "xapp-fake"
    assert cfg.slack_channel_id == "C123"


def test_has_slack_interactive_approvals_requires_all_three():
    cfg = _cfg(SLACK_BOT_TOKEN="xoxb-fake")
    assert cfg.has_slack_interactive_approvals is False
    cfg = _cfg(SLACK_BOT_TOKEN="xoxb-fake", SLACK_APP_TOKEN="xapp-fake", SLACK_CHANNEL_ID="C123")
    assert cfg.has_slack_interactive_approvals is True


def test_report_includes_slack_interactive_approvals_keys():
    cfg = _cfg(SLACK_INTERACTIVE_APPROVALS="true", SLACK_BOT_TOKEN="xoxb-fake", SLACK_APP_TOKEN="xapp-fake", SLACK_CHANNEL_ID="C123")
    report = cfg.report()
    assert report["slack_interactive_approvals"] is True
    assert report["slack_interactive_approvals_configured"] is True


# ---------------------------------------------------------------------------
# validate_startup_config — graceful degradation
# ---------------------------------------------------------------------------

def test_validate_flag_off_reports_single_problem():
    cfg = _cfg()
    problems = validate_startup_config(cfg)
    assert len(problems) == 1
    assert "SLACK_INTERACTIVE_APPROVALS" in problems[0]


def test_validate_flag_on_missing_all_tokens():
    cfg = _cfg(SLACK_INTERACTIVE_APPROVALS="true")
    problems = validate_startup_config(cfg)
    assert len(problems) == 3
    joined = " ".join(problems)
    assert "SLACK_BOT_TOKEN" in joined
    assert "SLACK_APP_TOKEN" in joined
    assert "SLACK_CHANNEL_ID" in joined


def test_validate_flag_on_missing_one_token():
    cfg = _cfg(SLACK_INTERACTIVE_APPROVALS="true", SLACK_BOT_TOKEN="xoxb-fake", SLACK_APP_TOKEN="xapp-fake")
    problems = validate_startup_config(cfg)
    assert len(problems) == 1
    assert "SLACK_CHANNEL_ID" in problems[0]


def test_validate_fully_configured_reports_no_problems():
    cfg = _cfg(
        SLACK_INTERACTIVE_APPROVALS="true",
        SLACK_BOT_TOKEN="xoxb-fake",
        SLACK_APP_TOKEN="xapp-fake",
        SLACK_CHANNEL_ID="C123",
    )
    assert validate_startup_config(cfg) == []


if __name__ == "__main__":
    tests = [
        test_slack_interactive_approvals_defaults_false,
        test_slack_interactive_approvals_true_when_set,
        test_slack_tokens_default_none,
        test_slack_tokens_load_from_env,
        test_has_slack_interactive_approvals_requires_all_three,
        test_report_includes_slack_interactive_approvals_keys,
        test_validate_flag_off_reports_single_problem,
        test_validate_flag_on_missing_all_tokens,
        test_validate_flag_on_missing_one_token,
        test_validate_fully_configured_reports_no_problems,
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
