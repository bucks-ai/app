"""Tests for the ui-flows.json flow definitions shipped with the runner.

Uses only the existing pure helpers in tools/ui_flow_validator.py — no
Playwright/browser execution.
"""
import os

import pytest

from tools.ui_flow_validator import (
    evaluate_flow_results,
    format_flow_report,
    load_flows_from_file,
)

CONFIG_PATH = os.path.join(os.path.dirname(__file__), "..", "ui-flows.json")

VALID_ACTIONS = {
    "navigate",
    "click",
    "fill",
    "select",
    "wait_for_selector",
    "assert_text",
    "assert_url",
    "assert_element",
}

SELECTOR_ACTIONS = {"click", "fill", "select", "wait_for_selector", "assert_element"}
VALUE_ACTIONS = {"navigate", "fill", "select", "assert_text", "assert_url"}

EXPECTED_FLOW_NAMES = {
    "login flow",
    "signup flow",
    "intake to blueprint flow",
    "dashboard render flow",
    "business tabs render flow",
}


@pytest.fixture(scope="module")
def flows():
    return load_flows_from_file(CONFIG_PATH)


def test_config_file_loads_a_nonempty_list(flows):
    assert isinstance(flows, list)
    assert len(flows) == 5


def test_config_covers_the_five_core_flows(flows):
    names = {flow["name"] for flow in flows}
    assert names == EXPECTED_FLOW_NAMES


def test_every_flow_has_a_name_and_nonempty_steps(flows):
    for flow in flows:
        assert isinstance(flow.get("name"), str) and flow["name"]
        assert isinstance(flow.get("steps"), list) and len(flow["steps"]) > 0


def test_every_step_uses_a_supported_action(flows):
    for flow in flows:
        for step in flow["steps"]:
            assert step.get("action") in VALID_ACTIONS, (
                f"{flow['name']!r} has unsupported action {step.get('action')!r}"
            )


def test_selector_actions_carry_a_selector(flows):
    for flow in flows:
        for step in flow["steps"]:
            if step["action"] in SELECTOR_ACTIONS:
                assert step.get("selector"), (
                    f"{flow['name']!r} step {step['action']!r} is missing a selector"
                )


def test_value_actions_carry_a_value(flows):
    for flow in flows:
        for step in flow["steps"]:
            if step["action"] in VALUE_ACTIONS:
                assert step.get("value"), (
                    f"{flow['name']!r} step {step['action']!r} is missing a value"
                )


def test_every_flow_starts_with_a_navigate_step(flows):
    for flow in flows:
        assert flow["steps"][0]["action"] == "navigate", (
            f"{flow['name']!r} does not start with a navigate step"
        )


def test_intake_flow_only_asserts_form_render_and_validation_errors(flows):
    intake = next(f for f in flows if f["name"] == "intake to blueprint flow")
    actions = [step["action"] for step in intake["steps"]]
    # No generation/save step — this flow only exercises rendering and
    # client-side validation, since fake AI mode isn't available against
    # prod/preview deploys.
    assert "wait_for_selector" not in actions
    assert any(step["action"] == "assert_text" for step in intake["steps"])
    generate_clicks = [
        step
        for step in intake["steps"]
        if step["action"] == "click" and "generate" in step.get("selector", "").lower()
    ]
    assert generate_clicks == []


def test_load_flows_from_file_missing_path_returns_empty_list():
    assert load_flows_from_file("/nonexistent/ui-flows.json") == []


# ── Simulated pass/fail reporting using the flow names from the real config ──

def test_evaluate_flow_results_all_passed_for_configured_flows(flows):
    results = [
        {"name": flow["name"], "passed": True, "error": None} for flow in flows
    ]
    evaluation = evaluate_flow_results(results)
    assert evaluation["passed"] is True
    assert evaluation["total"] == len(flows)
    assert evaluation["failed"] == []


def test_evaluate_flow_results_reports_per_step_failure_detail(flows):
    results = [
        {"name": flow["name"], "passed": True, "error": None} for flow in flows
    ]
    # Simulate the login flow failing on its assert_text step, the way
    # run_flow() reports per-step detail in its "error" field.
    results[0] = {
        "name": "login flow",
        "passed": False,
        "error": "step 7 (assert_text): page does not contain 'Invalid login credentials'",
    }
    evaluation = evaluate_flow_results(results)
    assert evaluation["passed"] is False
    assert evaluation["failed"] == ["login flow"]

    report = format_flow_report(
        [{**r, "steps_run": 7 if r["name"] == "login flow" else 8} for r in results],
        "https://example.vercel.app",
    )
    assert "FAILED" in report
    assert "login flow" in report
    assert "step 7 (assert_text)" in report
