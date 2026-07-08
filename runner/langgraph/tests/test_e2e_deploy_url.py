"""Unit tests for post-deploy validation harnesses actually targeting the
deployed URL (graph.run_e2e_if_needed, run_ui_flow_validation_if_needed,
run_product_eval_if_needed, and the shared graph._resolve_validation_base_url).

Runs standalone (no pytest dependency), mirroring test_deploy_node.py:

    python tests/test_e2e_deploy_url.py

Covers the M1 regression where every run logged e2e_skipped with reason
"no E2E_BASE_URL and no URL in deploy_result" even after a successful Vercel
deploy, because deploy_result.get("url") was always None — the real hostname
lives at deploy_result["poll"]["deployment"]["url"].
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("VERCEL_TOKEN", "test-token")

import graph
from state import RunnerState

graph.update_state = lambda *a, **k: None


def _events(capture):
    def _log(event_type, payload, task_id=None):
        capture.append((event_type, payload))
    return _log


def _ready_state(deploy_result=None):
    return RunnerState(
        current_task_id="t1",
        current_task={"id": "t1", "title": "demo", "issue_number": None},
        deploy_ready=True,
        deploy_result=deploy_result,
    )


# ---------------------------------------------------------------------------
# graph._resolve_validation_base_url
# ---------------------------------------------------------------------------

def test_resolve_prefers_env_override_over_deploy_result():
    events = []
    graph.log_event = _events(events)
    graph.cfg.e2e_base_url = "https://staging.example.com"
    try:
        deploy_result = {"poll": {"deployment": {"url": "my-app.vercel.app"}}}
        state = _ready_state(deploy_result)
        base_url = graph._resolve_validation_base_url(state, "e2e")

        assert base_url == "https://staging.example.com", base_url
        resolved = [p for (t, p) in events if t == "deploy_url_resolved"]
        assert resolved[0]["source"] == "E2E_BASE_URL_override", resolved
    finally:
        graph.cfg.e2e_base_url = None


def test_resolve_falls_back_to_deploy_result_url():
    events = []
    graph.log_event = _events(events)
    graph.cfg.e2e_base_url = None

    deploy_result = {
        "success": True,
        "poll": {"ready": True, "deployment": {"url": "my-app-abc123.vercel.app"}},
    }
    state = _ready_state(deploy_result)
    base_url = graph._resolve_validation_base_url(state, "e2e")

    assert base_url == "https://my-app-abc123.vercel.app", base_url
    resolved = [p for (t, p) in events if t == "deploy_url_resolved"]
    assert len(resolved) == 1, events
    assert resolved[0]["source"] == "deploy_result", resolved
    assert resolved[0]["base_url"] == "https://my-app-abc123.vercel.app", resolved
    assert resolved[0]["harness"] == "e2e", resolved


def test_resolve_returns_none_and_logs_nothing_when_unavailable():
    events = []
    graph.log_event = _events(events)
    graph.cfg.e2e_base_url = None

    state = _ready_state({"success": False, "poll": {}})
    base_url = graph._resolve_validation_base_url(state, "e2e")

    assert base_url is None
    assert [p for (t, p) in events if t == "deploy_url_resolved"] == []


# ---------------------------------------------------------------------------
# run_e2e_if_needed — end-to-end through the real deploy_result shape
# ---------------------------------------------------------------------------

def test_run_e2e_targets_deployed_url_on_success():
    events = []
    graph.log_event = _events(events)
    graph.cfg.e2e_enabled = True
    graph.cfg.e2e_base_url = None
    graph.is_playwright_available = lambda: True

    captured = {}

    def _fake_suite(base_url, timeout_ms, headless):
        captured["base_url"] = base_url
        return {"success": True, "results": []}

    graph.run_e2e_suite = _fake_suite

    deploy_result = {
        "success": True,
        "poll": {"ready": True, "deployment": {"url": "my-app-abc123.vercel.app"}},
    }
    state = _ready_state(deploy_result)
    out = graph.run_e2e_if_needed(state)

    assert captured["base_url"] == "https://my-app-abc123.vercel.app", captured
    assert out.e2e_result["success"] is True
    assert any(t == "e2e_passed" for t, _ in events), events
    assert not any(t == "e2e_skipped" for t, _ in events), events


def test_run_e2e_env_override_wins_over_deploy_url():
    events = []
    graph.log_event = _events(events)
    graph.cfg.e2e_enabled = True
    graph.cfg.e2e_base_url = "https://fixed-staging.example.com"
    graph.is_playwright_available = lambda: True

    captured = {}

    def _fake_suite(base_url, timeout_ms, headless):
        captured["base_url"] = base_url
        return {"success": True, "results": []}

    graph.run_e2e_suite = _fake_suite

    try:
        deploy_result = {"poll": {"deployment": {"url": "my-app-abc123.vercel.app"}}}
        state = _ready_state(deploy_result)
        graph.run_e2e_if_needed(state)

        assert captured["base_url"] == "https://fixed-staging.example.com", captured
    finally:
        graph.cfg.e2e_base_url = None


def test_run_e2e_skips_when_no_url_available():
    events = []
    graph.log_event = _events(events)
    graph.cfg.e2e_enabled = True
    graph.cfg.e2e_base_url = None
    graph.is_playwright_available = lambda: True

    state = _ready_state({"success": False, "poll": {}})
    out = graph.run_e2e_if_needed(state)

    assert out.e2e_result is None
    skipped = [p for (t, p) in events if t == "e2e_skipped"]
    assert len(skipped) == 1, events
    assert skipped[0]["reason"] == "no E2E_BASE_URL and no URL in deploy_result", skipped


# ---------------------------------------------------------------------------
# run_ui_flow_validation_if_needed — same resolution path
# ---------------------------------------------------------------------------

def test_run_ui_flow_targets_deployed_url_on_success():
    events = []
    graph.log_event = _events(events)
    graph.cfg.ui_flow_validation_enabled = True
    graph.cfg.e2e_base_url = None
    graph.cfg.ui_flow_config_path = "ui-flows.json"
    graph.is_playwright_available = lambda: True
    graph.load_flows_from_file = lambda path: [{"name": "flow-a", "steps": []}]

    captured = {}

    def _fake_flow(base_url, flows, timeout_ms, headless):
        captured["base_url"] = base_url
        return {"success": True, "results": []}

    graph.run_ui_flow_validation = _fake_flow

    deploy_result = {
        "success": True,
        "poll": {"ready": True, "deployment": {"url": "my-app-abc123.vercel.app"}},
    }
    state = _ready_state(deploy_result)
    out = graph.run_ui_flow_validation_if_needed(state)

    assert captured["base_url"] == "https://my-app-abc123.vercel.app", captured
    assert out.ui_flow_result["success"] is True
    assert any(t == "ui_flow_passed" for t, _ in events), events


if __name__ == "__main__":
    tests = [
        test_resolve_prefers_env_override_over_deploy_result,
        test_resolve_falls_back_to_deploy_result_url,
        test_resolve_returns_none_and_logs_nothing_when_unavailable,
        test_run_e2e_targets_deployed_url_on_success,
        test_run_e2e_env_override_wins_over_deploy_url,
        test_run_e2e_skips_when_no_url_available,
        test_run_ui_flow_targets_deployed_url_on_success,
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
