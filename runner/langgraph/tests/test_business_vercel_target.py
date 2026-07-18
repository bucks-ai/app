"""Unit tests for M4b: deploys and post-deploy checks target the business's
Vercel project (mission task m4b-06).

Runs standalone (no pytest dependency), mirroring test_foreign_repo_workspace.py:

    python tests/test_business_vercel_target.py

Covers:
  - Pure targeting logic in tools/vercel_tools.py: ``resolve_scoped_vercel_token``
    (env-by-name, never a stored value) and ``resolve_business_vercel_target``
    (full config success, partial config refusal, missing-secret refusal —
    NEVER a bucks-ai fallback).
  - Token threading through the mocked Vercel API surface
    (``_headers``/``get_deployment_status``/``get_deployment_by_id``/
    ``poll_deployment_until_terminal``/``trigger_deploy``): a business's scoped
    token is used instead of the configured ``VERCEL_TOKEN`` when passed.
  - The graph node ``deploy_if_needed``: a business mission with a full
    sandbox_config deploys to that business's own project_id/token; a partial
    or unresolvable sandbox_config skips the deploy entirely — never falling
    back to ``cfg.vercel_project_id``/``cfg.vercel_token``.
  - ``playwright_harness.build_business_smoke_scenarios`` shape (HTTP 200 on
    ``/`` + non-empty title) and the new ``title_non_empty`` check type.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import tools.vercel_tools as vt
from tools.playwright_harness import build_business_smoke_scenarios, _run_checks_on_page
import graph
from state import RunnerState

# Silence the flight recorder during tests.
vt.log_event = lambda *a, **k: None
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None


# ---------------------------------------------------------------------------
# resolve_scoped_vercel_token
# ---------------------------------------------------------------------------

def test_resolve_scoped_vercel_token_reads_env_by_name():
    os.environ["TEST_BIZ_VERCEL_TOKEN"] = "biz-scoped-token"
    try:
        result = vt.resolve_scoped_vercel_token("TEST_BIZ_VERCEL_TOKEN")
        assert result == {
            "success": True, "token": "biz-scoped-token", "secret_name": "TEST_BIZ_VERCEL_TOKEN",
        }, result
    finally:
        del os.environ["TEST_BIZ_VERCEL_TOKEN"]


def test_resolve_scoped_vercel_token_missing_secret():
    os.environ.pop("TEST_MISSING_VERCEL_TOKEN", None)
    result = vt.resolve_scoped_vercel_token("TEST_MISSING_VERCEL_TOKEN")
    assert result["success"] is False, result
    assert result["error"] == "missing_secret", result
    assert result["secret_name"] == "TEST_MISSING_VERCEL_TOKEN", result
    assert "token" not in result, "must never surface a token value on failure"


def test_resolve_scoped_vercel_token_no_name():
    result = vt.resolve_scoped_vercel_token("")
    assert result == {"success": False, "error": "no_secret_name"}, result


# ---------------------------------------------------------------------------
# resolve_business_vercel_target — pure targeting logic
# ---------------------------------------------------------------------------

def test_resolve_business_target_full_config_succeeds():
    os.environ["TEST_BIZ_VERCEL_TOKEN"] = "biz-scoped-token"
    try:
        target = vt.resolve_business_vercel_target({
            "vercel_project_id": "prj_biz_123",
            "vercel_token_secret_name": "TEST_BIZ_VERCEL_TOKEN",
        })
        assert target == {
            "success": True,
            "project_id": "prj_biz_123",
            "token": "biz-scoped-token",
            "secret_name": "TEST_BIZ_VERCEL_TOKEN",
        }, target
    finally:
        del os.environ["TEST_BIZ_VERCEL_TOKEN"]


def test_resolve_business_target_missing_project_id_is_partial():
    target = vt.resolve_business_vercel_target({
        "vercel_token_secret_name": "TEST_BIZ_VERCEL_TOKEN",
    })
    assert target == {"success": False, "reason": "partial_sandbox_config"}, target


def test_resolve_business_target_missing_secret_name_is_partial():
    target = vt.resolve_business_vercel_target({"vercel_project_id": "prj_biz_123"})
    assert target == {"success": False, "reason": "partial_sandbox_config"}, target


def test_resolve_business_target_empty_config_is_partial():
    assert vt.resolve_business_vercel_target({}) == {
        "success": False, "reason": "partial_sandbox_config",
    }
    assert vt.resolve_business_vercel_target(None) == {
        "success": False, "reason": "partial_sandbox_config",
    }


def test_resolve_business_target_unresolvable_secret():
    os.environ.pop("TEST_UNRESOLVED_VERCEL_TOKEN", None)
    target = vt.resolve_business_vercel_target({
        "vercel_project_id": "prj_biz_123",
        "vercel_token_secret_name": "TEST_UNRESOLVED_VERCEL_TOKEN",
    })
    assert target == {
        "success": False, "reason": "missing_secret", "secret_name": "TEST_UNRESOLVED_VERCEL_TOKEN",
    }, target


def test_resolve_business_target_never_returns_bucks_ai_fallback():
    """CRITICAL SAFETY: a partial/unresolvable config must never carry a
    project_id/token at all — callers must not be able to misuse the return
    value as a deploy target."""
    for config in (
        {},
        {"vercel_project_id": "prj_biz_123"},
        {"vercel_token_secret_name": "NOPE"},
    ):
        target = vt.resolve_business_vercel_target(config)
        assert target["success"] is False, target
        assert "project_id" not in target, target
        assert "token" not in target, target


# ---------------------------------------------------------------------------
# Token threading through the (mocked) Vercel API surface
# ---------------------------------------------------------------------------

def test_headers_uses_override_token():
    cfg = vt.get_config()
    saved = cfg.vercel_token
    cfg.vercel_token = "bucks-ai-token"
    try:
        assert vt._headers()["Authorization"] == "Bearer bucks-ai-token"
        assert vt._headers("biz-token")["Authorization"] == "Bearer biz-token"
    finally:
        cfg.vercel_token = saved


def test_get_deployment_status_available_with_token_and_no_global_token():
    """A business's scoped token makes get_deployment_status available even
    when the runner's own VERCEL_TOKEN is unset."""
    cfg = vt.get_config()
    saved = cfg.vercel_token
    cfg.vercel_token = None
    try:
        seen_headers = {}

        class _Resp:
            def raise_for_status(self):
                pass

            def json(self):
                return {"deployments": [{"uid": "dpl_1", "readyState": "READY"}]}

        def _fake_get(url, headers=None, params=None, timeout=None):
            seen_headers.update(headers or {})
            return _Resp()

        saved_retry = vt.retry_request
        vt.retry_request = lambda fn, *a, **kw: fn(*a, **kw)
        try:
            import requests
            saved_requests_get = requests.get
            requests.get = _fake_get
            try:
                result = vt.get_deployment_status("prj_biz_123", token="biz-token")
            finally:
                requests.get = saved_requests_get
        finally:
            vt.retry_request = saved_retry

        assert result["available"] is True, result
        assert seen_headers.get("Authorization") == "Bearer biz-token", seen_headers
    finally:
        cfg.vercel_token = saved


def test_trigger_deploy_uses_business_token_and_project(monkeypatched=None):
    cfg = vt.get_config()
    saved_status = vt.get_deployment_status
    saved_poll = vt.poll_deployment_until_terminal
    saved_auto = cfg.auto_deploy
    saved_pollcfg = cfg.auto_deploy_poll
    saved_token = cfg.vercel_token
    cfg.auto_deploy = True
    cfg.auto_deploy_poll = True
    cfg.vercel_token = None  # no bucks-ai token configured at all

    seen = {}

    def _status(project_id=None, token=None):
        seen["status_project_id"] = project_id
        seen["status_token"] = token
        return {"available": True, "latest": {"uid": "dpl_biz", "readyState": "BUILDING"}}

    def _poll(**kw):
        seen["poll_project_id"] = kw.get("project_id")
        seen["poll_token"] = kw.get("token")
        return {"available": True, "ready": True, "terminal": True, "timed_out": False, "state": "READY", "polls": 1}

    vt.get_deployment_status = _status
    vt.poll_deployment_until_terminal = _poll
    try:
        res = vt.trigger_deploy(project_id="prj_biz_123", token="biz-scoped-token")
        assert res["success"] is True, res
        assert seen["status_project_id"] == "prj_biz_123", seen
        assert seen["status_token"] == "biz-scoped-token", seen
        assert seen["poll_project_id"] == "prj_biz_123", seen
        assert seen["poll_token"] == "biz-scoped-token", seen
    finally:
        vt.get_deployment_status = saved_status
        vt.poll_deployment_until_terminal = saved_poll
        cfg.auto_deploy = saved_auto
        cfg.auto_deploy_poll = saved_pollcfg
        cfg.vercel_token = saved_token


def test_trigger_deploy_without_token_or_config_is_unavailable():
    cfg = vt.get_config()
    saved_token = cfg.vercel_token
    cfg.vercel_token = None
    try:
        res = vt.trigger_deploy(project_id="prj_biz_123")
        assert res == {"success": False, "reason": "no VERCEL_TOKEN"}, res
    finally:
        cfg.vercel_token = saved_token


# ---------------------------------------------------------------------------
# graph.deploy_if_needed — business mission targeting
# ---------------------------------------------------------------------------

def _landed_business_state(business_id="biz-1"):
    return RunnerState(
        current_task_id="t1",
        current_task={"id": "t1", "title": "demo", "business_id": business_id},
        worker_result={"success": True},
        check_passed=True,
        last_commit="abc1234",
    )


def _stub_trigger(verdict, calls):
    def _trigger(project_name=None, project_id=None, poll=True, token=None):
        calls.append({"project_name": project_name, "project_id": project_id, "token": token})
        return verdict
    return _trigger


def test_deploy_if_needed_targets_business_project_and_token():
    calls = []
    graph.trigger_deploy = _stub_trigger({"success": True, "poll": {"ready": True}}, calls)
    graph.cfg.auto_deploy = True
    graph.cfg.vercel_project_id = "prj_bucks_ai"
    graph.cfg.vercel_token = "bucks-ai-token"

    os.environ["TEST_BIZ2_VERCEL_TOKEN"] = "biz-scoped-token"
    original_fetch = graph.fetch_business_by_id
    graph.fetch_business_by_id = lambda bid: {
        "id": bid,
        "sandbox_config": {
            "vercel_project_id": "prj_biz_999",
            "vercel_token_secret_name": "TEST_BIZ2_VERCEL_TOKEN",
        },
    }
    try:
        state = graph.deploy_if_needed(_landed_business_state("biz-42"))

        assert len(calls) == 1, calls
        assert calls[0]["project_id"] == "prj_biz_999", calls
        assert calls[0]["token"] == "biz-scoped-token", calls
        assert state.deploy_ready is True
    finally:
        graph.fetch_business_by_id = original_fetch
        del os.environ["TEST_BIZ2_VERCEL_TOKEN"]


def test_deploy_if_needed_refuses_fallback_on_partial_sandbox_config():
    """A business with only vercel_project_id set (no secret name yet) must
    skip the deploy entirely — never fall back to the bucks-ai project."""
    calls = []
    graph.trigger_deploy = _stub_trigger({"success": True}, calls)
    graph.cfg.auto_deploy = True
    graph.cfg.vercel_project_id = "prj_bucks_ai"
    graph.cfg.vercel_token = "bucks-ai-token"

    original_fetch = graph.fetch_business_by_id
    graph.fetch_business_by_id = lambda bid: {
        "id": bid,
        "sandbox_config": {"vercel_project_id": "prj_biz_999"},
    }
    try:
        state = graph.deploy_if_needed(_landed_business_state("biz-43"))

        assert calls == [], "must never deploy to the bucks-ai project on partial config"
        assert state.deploy_result is None, state.deploy_result
    finally:
        graph.fetch_business_by_id = original_fetch


def test_deploy_if_needed_refuses_fallback_on_missing_secret():
    calls = []
    graph.trigger_deploy = _stub_trigger({"success": True}, calls)
    graph.cfg.auto_deploy = True
    graph.cfg.vercel_project_id = "prj_bucks_ai"
    graph.cfg.vercel_token = "bucks-ai-token"

    os.environ.pop("TEST_BIZ_NOPE_TOKEN", None)
    original_fetch = graph.fetch_business_by_id
    graph.fetch_business_by_id = lambda bid: {
        "id": bid,
        "sandbox_config": {
            "vercel_project_id": "prj_biz_999",
            "vercel_token_secret_name": "TEST_BIZ_NOPE_TOKEN",
        },
    }
    try:
        state = graph.deploy_if_needed(_landed_business_state("biz-44"))

        assert calls == [], "must never deploy when the scoped secret does not resolve"
        assert state.deploy_result is None, state.deploy_result
    finally:
        graph.fetch_business_by_id = original_fetch


def test_deploy_if_needed_self_mission_unaffected():
    """A task with no business_id keeps using cfg.vercel_project_id/token,
    exactly as before this feature landed."""
    calls = []
    graph.trigger_deploy = _stub_trigger({"success": True, "poll": {}}, calls)
    graph.cfg.auto_deploy = True
    graph.cfg.vercel_project_id = "prj_bucks_ai"
    graph.cfg.vercel_token = "bucks-ai-token"

    state = RunnerState(
        current_task_id="t2",
        current_task={"id": "t2", "title": "self repo task"},
        worker_result={"success": True},
        check_passed=True,
        last_commit="def5678",
    )
    graph.deploy_if_needed(state)

    assert len(calls) == 1, calls
    assert calls[0]["project_id"] == "prj_bucks_ai", calls
    assert calls[0]["token"] is None, calls


# ---------------------------------------------------------------------------
# playwright_harness.build_business_smoke_scenarios / title_non_empty check
# ---------------------------------------------------------------------------

def test_build_business_smoke_scenarios_shape():
    scenarios = build_business_smoke_scenarios("https://biz.vercel.app")
    assert len(scenarios) == 1, scenarios
    scenario = scenarios[0]
    assert scenario["path"] == "/", scenario
    check_types = {c["type"] for c in scenario["checks"]}
    assert check_types == {"status", "title_non_empty"}, check_types


class _FakePage:
    def __init__(self, title):
        self._title = title

    def title(self):
        return self._title


def test_title_non_empty_check_passes_for_real_title():
    failures = _run_checks_on_page(_FakePage("Acme Inc — Home"), [{"type": "title_non_empty", "value": ""}])
    assert failures == [], failures


def test_title_non_empty_check_fails_for_blank_title():
    failures = _run_checks_on_page(_FakePage("   "), [{"type": "title_non_empty", "value": ""}])
    assert failures == ["title is empty"], failures


if __name__ == "__main__":
    tests = [
        test_resolve_scoped_vercel_token_reads_env_by_name,
        test_resolve_scoped_vercel_token_missing_secret,
        test_resolve_scoped_vercel_token_no_name,
        test_resolve_business_target_full_config_succeeds,
        test_resolve_business_target_missing_project_id_is_partial,
        test_resolve_business_target_missing_secret_name_is_partial,
        test_resolve_business_target_empty_config_is_partial,
        test_resolve_business_target_unresolvable_secret,
        test_resolve_business_target_never_returns_bucks_ai_fallback,
        test_headers_uses_override_token,
        test_get_deployment_status_available_with_token_and_no_global_token,
        test_trigger_deploy_uses_business_token_and_project,
        test_trigger_deploy_without_token_or_config_is_unavailable,
        test_deploy_if_needed_targets_business_project_and_token,
        test_deploy_if_needed_refuses_fallback_on_partial_sandbox_config,
        test_deploy_if_needed_refuses_fallback_on_missing_secret,
        test_deploy_if_needed_self_mission_unaffected,
        test_build_business_smoke_scenarios_shape,
        test_title_non_empty_check_passes_for_real_title,
        test_title_non_empty_check_fails_for_blank_title,
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
