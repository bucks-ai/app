"""Unit tests for tools/environment_ownership.py.

Runs standalone (no pytest dependency):

    python tests/test_environment_ownership.py

All tests are pure / injected — no network, no Sentry/PostHog credentials,
no real git repo.

Invariants under test:

  check_sentry_after_deploy  — FAIL-OPEN: missing config, network error, and
                               unexpected exceptions all return
                               {"available": False, ...}, never raise.

  should_deploy_for_sha_mismatch — pure decision; only triggers on FAIL+auto_deploy.

  trigger_deploy_for_sha_mismatch — FAIL-OPEN: vercel missing or raising degrades
                                    to {"success": False, ...}, never raises.

  check_posthog_analytics_health — FAIL-OPEN: same pattern as Sentry.

  verify_push_destination — mismatch returns ok=False; git error is degraded
                            (ok=True, degraded=True) so the loop continues.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tools.environment_ownership as eo


# ---------------------------------------------------------------------------
# check_sentry_after_deploy — fail-open
# ---------------------------------------------------------------------------

def test_sentry_check_degrades_when_unconfigured(monkeypatch=None):
    """No Sentry credentials → available=False, no exception."""
    import tools.environment_ownership as _eo
    original = None

    class _FakeCfg:
        has_sentry = False

    orig_get = None
    import config as _cfg_mod
    orig_get = _cfg_mod.get_config
    _cfg_mod.get_config = lambda: _FakeCfg()
    try:
        result = _eo.check_sentry_after_deploy(since_iso="2026-01-01T00:00:00")
        assert result["available"] is False
        assert "reason" in result
    finally:
        _cfg_mod.get_config = orig_get


def test_sentry_check_degrades_on_exception():
    """If list_new_issues raises, the function returns available=False."""
    import tools.environment_ownership as _eo
    import tools.sentry_tools as st
    import config as _cfg_mod

    class _FakeCfg:
        has_sentry = True

    orig_get = _cfg_mod.get_config
    original = st.list_new_issues

    def _boom(since_iso):
        raise RuntimeError("network error")

    _cfg_mod.get_config = lambda: _FakeCfg()
    st.list_new_issues = _boom
    try:
        result = _eo.check_sentry_after_deploy(since_iso="2026-01-01T00:00:00")
        assert result["available"] is False
        assert "network error" in result.get("reason", "")
    finally:
        _cfg_mod.get_config = orig_get
        st.list_new_issues = original


def test_sentry_check_returns_summary_on_success():
    """Happy path: configured Sentry with no new issues → available=True, total=0."""
    import tools.environment_ownership as _eo
    import tools.sentry_tools as st
    import config as _cfg_mod

    class _FakeCfg:
        has_sentry = True

    orig_get = _cfg_mod.get_config
    orig_list = st.list_new_issues
    _cfg_mod.get_config = lambda: _FakeCfg()
    st.list_new_issues = lambda since_iso: []
    try:
        result = _eo.check_sentry_after_deploy(since_iso="2026-01-01T00:00:00")
        assert result["available"] is True
        assert result["total"] == 0
    finally:
        _cfg_mod.get_config = orig_get
        st.list_new_issues = orig_list


# ---------------------------------------------------------------------------
# should_deploy_for_sha_mismatch — pure decision
# ---------------------------------------------------------------------------

def test_should_deploy_true_on_fail_and_auto_deploy():
    sha_check = {"status": "fail", "data": {"origin_sha": "abc1234", "deployed_sha": "xyz9999"}}
    assert eo.should_deploy_for_sha_mismatch(sha_check, auto_deploy=True) is True


def test_should_deploy_false_when_auto_deploy_off():
    sha_check = {"status": "fail"}
    assert eo.should_deploy_for_sha_mismatch(sha_check, auto_deploy=False) is False


def test_should_deploy_false_on_pass():
    sha_check = {"status": "pass"}
    assert eo.should_deploy_for_sha_mismatch(sha_check, auto_deploy=True) is False


def test_should_deploy_false_on_warn():
    # WARN = transient, could not determine; don't trigger a deploy
    sha_check = {"status": "warn"}
    assert eo.should_deploy_for_sha_mismatch(sha_check, auto_deploy=True) is False


def test_should_deploy_false_on_skip():
    sha_check = {"status": "skip"}
    assert eo.should_deploy_for_sha_mismatch(sha_check, auto_deploy=True) is False


def test_should_deploy_false_on_empty_check():
    assert eo.should_deploy_for_sha_mismatch({}, auto_deploy=True) is False
    assert eo.should_deploy_for_sha_mismatch(None, auto_deploy=True) is False


# ---------------------------------------------------------------------------
# trigger_deploy_for_sha_mismatch — fail-open
# ---------------------------------------------------------------------------

def test_trigger_deploy_skips_when_not_needed():
    class _Cfg:
        auto_deploy = True
        has_vercel = True
        vercel_project_id = "prj_123"

    sha_check = {"status": "pass"}
    result = eo.trigger_deploy_for_sha_mismatch(_Cfg(), sha_check)
    assert result["success"] is False
    assert "sha_current" in result["reason"] or "disabled" in result["reason"]


def test_trigger_deploy_skips_when_no_vercel_token():
    class _Cfg:
        auto_deploy = True
        has_vercel = False
        vercel_project_id = None

    sha_check = {"status": "fail", "data": {"origin_sha": "abc", "deployed_sha": "xyz"}}
    result = eo.trigger_deploy_for_sha_mismatch(_Cfg(), sha_check)
    assert result["success"] is False
    assert result["reason"] == "no_vercel_token"


def test_trigger_deploy_degrades_on_exception():
    """trigger_deploy raising should not propagate — degrade to success=False."""
    import tools.vercel_tools as vt

    class _Cfg:
        auto_deploy = True
        has_vercel = True
        vercel_project_id = "prj_123"

    sha_check = {"status": "fail", "data": {"origin_sha": "abc", "deployed_sha": "xyz"}}

    original = vt.trigger_deploy
    vt.trigger_deploy = lambda **kw: (_ for _ in ()).throw(RuntimeError("boom"))
    try:
        result = eo.trigger_deploy_for_sha_mismatch(_Cfg(), sha_check)
        assert result["success"] is False
    finally:
        vt.trigger_deploy = original


def test_trigger_deploy_calls_trigger_with_project_id():
    import tools.vercel_tools as vt

    class _Cfg:
        auto_deploy = True
        has_vercel = True
        vercel_project_id = "prj_abc"

    sha_check = {"status": "fail", "data": {"origin_sha": "abc", "deployed_sha": "xyz"}}

    calls = []

    def _stub(**kw):
        calls.append(kw)
        return {"success": True}

    original = vt.trigger_deploy
    vt.trigger_deploy = _stub
    try:
        eo.trigger_deploy_for_sha_mismatch(_Cfg(), sha_check)
        assert calls, "trigger_deploy should have been called"
        assert calls[0]["project_id"] == "prj_abc"
    finally:
        vt.trigger_deploy = original


# ---------------------------------------------------------------------------
# check_posthog_analytics_health — fail-open
# ---------------------------------------------------------------------------

def test_posthog_health_degrades_when_unconfigured():
    import config as _cfg_mod

    class _FakeCfg:
        has_posthog = False

    orig = _cfg_mod.get_config
    _cfg_mod.get_config = lambda: _FakeCfg()
    try:
        result = eo.check_posthog_analytics_health(["pageview"])
        assert result["available"] is False
    finally:
        _cfg_mod.get_config = orig


def test_posthog_health_degrades_on_exception():
    import tools.posthog_tools as pt
    import config as _cfg_mod

    class _FakeCfg:
        has_posthog = True

    orig_get = _cfg_mod.get_config
    orig_query = pt.query_event_count
    _cfg_mod.get_config = lambda: _FakeCfg()
    pt.query_event_count = lambda event, days: (_ for _ in ()).throw(RuntimeError("timeout"))
    try:
        result = eo.check_posthog_analytics_health(["pageview"])
        assert result["available"] is False
    finally:
        _cfg_mod.get_config = orig_get
        pt.query_event_count = orig_query


def test_posthog_health_returns_event_counts():
    import tools.posthog_tools as pt
    import config as _cfg_mod

    class _FakeCfg:
        has_posthog = True

    orig_get = _cfg_mod.get_config
    orig_query = pt.query_event_count
    _cfg_mod.get_config = lambda: _FakeCfg()
    pt.query_event_count = lambda event, days: {"available": True, "event": event, "days": days, "count": 42}
    try:
        result = eo.check_posthog_analytics_health(["pageview", "click"])
        assert result["available"] is True
        assert len(result["events"]) == 2
        assert all(r["count"] == 42 for r in result["events"])
    finally:
        _cfg_mod.get_config = orig_get
        pt.query_event_count = orig_query


def test_posthog_health_empty_event_list():
    import config as _cfg_mod

    class _FakeCfg:
        has_posthog = True

    orig = _cfg_mod.get_config
    _cfg_mod.get_config = lambda: _FakeCfg()
    try:
        result = eo.check_posthog_analytics_health([])
        assert result["available"] is True
        assert result["events"] == []
    finally:
        _cfg_mod.get_config = orig


# ---------------------------------------------------------------------------
# verify_push_destination
# ---------------------------------------------------------------------------

def test_verify_push_destination_passes_on_match():
    import tools.dispatch_preflight as dp

    orig = dp.verify_origin_remote
    dp.verify_origin_remote = lambda path, name: {"ok": True, "reason": "", "expected": name, "actual": name}
    try:
        result = eo.verify_push_destination("/repo", "owner/name")
        assert result["ok"] is True
        assert not result.get("degraded")
    finally:
        dp.verify_origin_remote = orig


def test_verify_push_destination_fails_on_mismatch():
    import tools.dispatch_preflight as dp

    orig = dp.verify_origin_remote
    dp.verify_origin_remote = lambda path, name: {
        "ok": False,
        "reason": "remote_mismatch",
        "expected": "owner/business",
        "actual": "owner/wrong",
    }
    try:
        result = eo.verify_push_destination("/repo", "owner/business")
        assert result["ok"] is False
        assert not result.get("degraded")
    finally:
        dp.verify_origin_remote = orig


def test_verify_push_destination_degrades_on_exception():
    """A git subprocess error should NOT propagate — degrade to ok=True, degraded=True."""
    import tools.dispatch_preflight as dp

    orig = dp.verify_origin_remote
    dp.verify_origin_remote = lambda path, name: (_ for _ in ()).throw(OSError("git missing"))
    try:
        result = eo.verify_push_destination("/repo", "owner/name")
        assert result["ok"] is True
        assert result.get("degraded") is True
    finally:
        dp.verify_origin_remote = orig


def test_verify_push_destination_skips_on_missing_args():
    result = eo.verify_push_destination("", "owner/name")
    assert result["ok"] is True
    assert result.get("degraded") is True

    result2 = eo.verify_push_destination("/repo", "")
    assert result2["ok"] is True
    assert result2.get("degraded") is True


# ---------------------------------------------------------------------------
# Test runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_sentry_check_degrades_when_unconfigured,
        test_sentry_check_degrades_on_exception,
        test_sentry_check_returns_summary_on_success,
        test_should_deploy_true_on_fail_and_auto_deploy,
        test_should_deploy_false_when_auto_deploy_off,
        test_should_deploy_false_on_pass,
        test_should_deploy_false_on_warn,
        test_should_deploy_false_on_skip,
        test_should_deploy_false_on_empty_check,
        test_trigger_deploy_skips_when_not_needed,
        test_trigger_deploy_skips_when_no_vercel_token,
        test_trigger_deploy_degrades_on_exception,
        test_trigger_deploy_calls_trigger_with_project_id,
        test_posthog_health_degrades_when_unconfigured,
        test_posthog_health_degrades_on_exception,
        test_posthog_health_returns_event_counts,
        test_posthog_health_empty_event_list,
        test_verify_push_destination_passes_on_match,
        test_verify_push_destination_fails_on_mismatch,
        test_verify_push_destination_degrades_on_exception,
        test_verify_push_destination_skips_on_missing_args,
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
