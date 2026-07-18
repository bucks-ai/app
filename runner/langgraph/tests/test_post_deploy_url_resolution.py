"""Unit tests for post-deploy URL resolution in the E2E and UI flow graph nodes.

Runs standalone (no pytest dependency), mirroring test_deploy_node.py:

    python tests/test_post_deploy_url_resolution.py

Covers the M2 fix for run_e2e_if_needed / run_ui_flow_validation_if_needed:
a successful, polled Vercel deploy must produce a URL the harnesses actually
use (state.deploy_result["url"]), E2E_BASE_URL must still override it, and a
deploy_url_validated event must record which URL/source was used. Playwright
execution itself (run_e2e_suite / run_ui_flow_validation) is stubbed so no
browser is launched.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

os.environ.setdefault("VERCEL_TOKEN", "test-token")

import graph
from state import RunnerState

graph.update_state = lambda *a, **k: None


def _ready_state(deploy_result):
    return RunnerState(
        current_task_id="t1",
        deploy_ready=True,
        deploy_result=deploy_result,
    )


def _capture_events():
    events = []
    graph.log_event = lambda event_type, payload, **kw: events.append((event_type, payload))
    return events


def _stub_e2e_suite(result, calls):
    def _run(base_url, timeout_ms, headless, scenarios=None):
        calls.append(base_url)
        return result
    return _run


def _stub_ui_flow(result, calls):
    def _run(base_url, flows, timeout_ms, headless):
        calls.append(base_url)
        return result
    return _run


# ---------------------------------------------------------------------------
# run_e2e_if_needed
# ---------------------------------------------------------------------------

def test_e2e_uses_deploy_result_url_when_no_override():
    events = _capture_events()
    calls = []
    graph.cfg.e2e_enabled = True
    graph.cfg.e2e_base_url = None
    graph.is_playwright_available = lambda: True
    graph.run_e2e_suite = _stub_e2e_suite({"success": True, "results": []}, calls)

    state = graph.run_e2e_if_needed(_ready_state({"url": "https://my-app.vercel.app"}))

    assert calls == ["https://my-app.vercel.app"], calls
    assert state.e2e_result["success"] is True
    validated = [p for t, p in events if t == "deploy_url_validated"]
    assert validated == [{
        "task_id": "t1", "harness": "e2e",
        "url": "https://my-app.vercel.app", "source": "deploy_result",
        "business_id": None,
    }], validated


def test_e2e_base_url_override_wins_over_deploy_result():
    events = _capture_events()
    calls = []
    graph.cfg.e2e_enabled = True
    graph.cfg.e2e_base_url = "https://override.example.com"
    graph.is_playwright_available = lambda: True
    graph.run_e2e_suite = _stub_e2e_suite({"success": True, "results": []}, calls)

    graph.run_e2e_if_needed(_ready_state({"url": "https://my-app.vercel.app"}))

    assert calls == ["https://override.example.com"], calls
    validated = [p for t, p in events if t == "deploy_url_validated"]
    assert validated[0]["source"] == "env_override", validated

    graph.cfg.e2e_base_url = None  # restore for other tests


def test_e2e_skipped_when_no_url_anywhere():
    events = _capture_events()
    graph.cfg.e2e_enabled = True
    graph.cfg.e2e_base_url = None
    graph.is_playwright_available = lambda: True

    state = graph.run_e2e_if_needed(_ready_state({}))

    assert state.e2e_result is None
    reasons = [p.get("reason") for t, p in events if t == "e2e_skipped"]
    assert reasons == ["no E2E_BASE_URL and no URL in deploy_result"], reasons
    assert not any(t == "deploy_url_validated" for t, _ in events), events


def test_e2e_falls_back_to_legacy_deployment_url_key():
    events = _capture_events()
    calls = []
    graph.cfg.e2e_enabled = True
    graph.cfg.e2e_base_url = None
    graph.is_playwright_available = lambda: True
    graph.run_e2e_suite = _stub_e2e_suite({"success": True, "results": []}, calls)

    graph.run_e2e_if_needed(_ready_state({"deployment_url": "https://legacy.vercel.app"}))

    assert calls == ["https://legacy.vercel.app"], calls


# ---------------------------------------------------------------------------
# run_ui_flow_validation_if_needed
# ---------------------------------------------------------------------------

def test_ui_flow_uses_deploy_result_url_when_no_override():
    events = _capture_events()
    calls = []
    graph.cfg.ui_flow_validation_enabled = True
    graph.cfg.e2e_base_url = None
    graph.cfg.ui_flow_config_path = "flows.json"
    graph.is_playwright_available = lambda: True
    graph.load_flows_from_file = lambda path: [{"name": "f1", "steps": []}]
    graph.run_ui_flow_validation = _stub_ui_flow({"success": True, "results": []}, calls)

    state = graph.run_ui_flow_validation_if_needed(_ready_state({"url": "https://my-app.vercel.app"}))

    assert calls == ["https://my-app.vercel.app"], calls
    assert state.ui_flow_result["success"] is True
    validated = [p for t, p in events if t == "deploy_url_validated"]
    assert validated == [{
        "task_id": "t1", "harness": "ui_flow",
        "url": "https://my-app.vercel.app", "source": "deploy_result",
    }], validated

    graph.cfg.ui_flow_validation_enabled = False  # restore for other tests


def test_ui_flow_base_url_override_wins_over_deploy_result():
    events = _capture_events()
    calls = []
    graph.cfg.ui_flow_validation_enabled = True
    graph.cfg.e2e_base_url = "https://override.example.com"
    graph.cfg.ui_flow_config_path = "flows.json"
    graph.is_playwright_available = lambda: True
    graph.load_flows_from_file = lambda path: [{"name": "f1", "steps": []}]
    graph.run_ui_flow_validation = _stub_ui_flow({"success": True, "results": []}, calls)

    graph.run_ui_flow_validation_if_needed(_ready_state({"url": "https://my-app.vercel.app"}))

    assert calls == ["https://override.example.com"], calls
    validated = [p for t, p in events if t == "deploy_url_validated"]
    assert validated[0]["source"] == "env_override", validated

    graph.cfg.e2e_base_url = None  # restore for other tests
    graph.cfg.ui_flow_validation_enabled = False


def test_ui_flow_skipped_when_no_url_anywhere():
    events = _capture_events()
    graph.cfg.ui_flow_validation_enabled = True
    graph.cfg.e2e_base_url = None

    graph.is_playwright_available = lambda: True

    state = graph.run_ui_flow_validation_if_needed(_ready_state({}))

    assert state.ui_flow_result is None
    reasons = [p.get("reason") for t, p in events if t == "ui_flow_skipped"]
    assert reasons == ["no base URL available (set E2E_BASE_URL or ensure deploy_result contains a URL)"], reasons
    assert not any(t == "deploy_url_validated" for t, _ in events), events

    graph.cfg.ui_flow_validation_enabled = False


if __name__ == "__main__":
    tests = [
        test_e2e_uses_deploy_result_url_when_no_override,
        test_e2e_base_url_override_wins_over_deploy_result,
        test_e2e_skipped_when_no_url_anywhere,
        test_e2e_falls_back_to_legacy_deployment_url_key,
        test_ui_flow_uses_deploy_result_url_when_no_override,
        test_ui_flow_base_url_override_wins_over_deploy_result,
        test_ui_flow_skipped_when_no_url_anywhere,
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
