"""Unit tests for app_approvals_daemon.py's startup validation and config wiring.

Runs standalone (no pytest dependency), mirroring tests/test_approvals_daemon.py:

    python tests/test_app_approvals_daemon.py

No live Supabase calls anywhere: these tests only exercise validate_startup_config
(pure) and the RunnerConfig fields/properties it reads. AppApprovalsDaemon itself
(which opens a Supabase client) is intentionally not instantiated here.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import config
from config import get_config
from app_approvals_daemon import validate_startup_config


def _cfg(**env):
    """Fresh config with only the given env vars set, isolated from the real .env."""
    keys = ("APP_APPROVALS_ENABLED", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY", "RUNNER_OWNER_USER_ID")
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

def test_app_approvals_enabled_defaults_false():
    cfg = _cfg()
    assert cfg.app_approvals_enabled is False


def test_app_approvals_enabled_true_when_set():
    cfg = _cfg(APP_APPROVALS_ENABLED="true")
    assert cfg.app_approvals_enabled is True


def test_runner_owner_user_id_defaults_none():
    cfg = _cfg()
    assert cfg.runner_owner_user_id is None


def test_runner_owner_user_id_loads_from_env():
    cfg = _cfg(RUNNER_OWNER_USER_ID="user-abc")
    assert cfg.runner_owner_user_id == "user-abc"


def test_has_app_approvals_requires_flag_supabase_and_owner():
    cfg = _cfg(APP_APPROVALS_ENABLED="true")
    assert cfg.has_app_approvals is False

    cfg = _cfg(
        APP_APPROVALS_ENABLED="true",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="fake-key",
    )
    assert cfg.has_app_approvals is False

    cfg = _cfg(
        APP_APPROVALS_ENABLED="true",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="fake-key",
        RUNNER_OWNER_USER_ID="user-abc",
    )
    assert cfg.has_app_approvals is True


def test_report_includes_app_approvals_keys():
    cfg = _cfg(
        APP_APPROVALS_ENABLED="true",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="fake-key",
        RUNNER_OWNER_USER_ID="user-abc",
    )
    report = cfg.report()
    assert report["app_approvals_enabled"] is True
    assert report["app_approvals_configured"] is True


# ---------------------------------------------------------------------------
# validate_startup_config — graceful degradation
# ---------------------------------------------------------------------------

def test_validate_flag_off_reports_single_problem():
    cfg = _cfg()
    problems = validate_startup_config(cfg)
    assert len(problems) == 1
    assert "APP_APPROVALS_ENABLED" in problems[0]


def test_validate_flag_on_missing_everything():
    cfg = _cfg(APP_APPROVALS_ENABLED="true")
    problems = validate_startup_config(cfg)
    assert len(problems) == 2
    joined = " ".join(problems)
    assert "SUPABASE_URL" in joined
    assert "RUNNER_OWNER_USER_ID" in joined


def test_validate_flag_on_missing_owner_only():
    cfg = _cfg(
        APP_APPROVALS_ENABLED="true",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="fake-key",
    )
    problems = validate_startup_config(cfg)
    assert len(problems) == 1
    assert "RUNNER_OWNER_USER_ID" in problems[0]


def test_validate_fully_configured_reports_no_problems():
    cfg = _cfg(
        APP_APPROVALS_ENABLED="true",
        SUPABASE_URL="https://example.supabase.co",
        SUPABASE_SERVICE_ROLE_KEY="fake-key",
        RUNNER_OWNER_USER_ID="user-abc",
    )
    assert validate_startup_config(cfg) == []


if __name__ == "__main__":
    tests = [
        test_app_approvals_enabled_defaults_false,
        test_app_approvals_enabled_true_when_set,
        test_runner_owner_user_id_defaults_none,
        test_runner_owner_user_id_loads_from_env,
        test_has_app_approvals_requires_flag_supabase_and_owner,
        test_report_includes_app_approvals_keys,
        test_validate_flag_off_reports_single_problem,
        test_validate_flag_on_missing_everything,
        test_validate_flag_on_missing_owner_only,
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
