"""UI Flow Validation Runner for post-deploy multi-step browser flows.

Pure helpers (build_default_flows, evaluate_flow_results, format_flow_report,
load_flows_from_file) are side-effect free and fully unit-testable. Browser
execution (run_flow, run_ui_flow_validation) requires a real Playwright install.

Flow definition format (ui_flows.json):
    [
        {
            "name": "login flow",
            "steps": [
                {"action": "navigate", "value": "/login"},
                {"action": "fill", "selector": "#email", "value": "user@example.com"},
                {"action": "fill", "selector": "#password", "value": "secret"},
                {"action": "click", "selector": "button[type=submit]"},
                {"action": "assert_url", "value": "/dashboard"}
            ]
        }
    ]

Supported step actions:
    navigate          — go to path (relative to base_url) or absolute URL
    click             — click element matching CSS selector
    fill              — type value into input matching CSS selector
    select            — select option value in <select> matching CSS selector
    wait_for_selector — wait for element matching selector to be visible
    assert_text       — assert page body HTML contains text value
    assert_url        — assert current URL contains value
    assert_element    — assert element matching selector exists on page
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional


def build_default_flows(base_url: str) -> list[dict]:  # noqa: ARG001
    """Return an empty default flow list.

    No flows run by default — they must be defined in a ui_flows.json config
    file (UI_FLOW_CONFIG_PATH) or passed directly to run_ui_flow_validation.
    """
    return []


def load_flows_from_file(path: str) -> list[dict]:
    """Load flow definitions from a JSON file at path.

    Returns an empty list when the file is missing, unreadable, or contains
    invalid JSON. The top-level JSON value must be a list; a JSON object
    returns an empty list.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
        data = json.loads(text)
        if isinstance(data, list):
            return data
        return []
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return []


def evaluate_flow_results(results: list[dict]) -> dict:
    """Aggregate flow results into a summary dict.

    Each result dict must have: name (str), passed (bool), error (Optional[str]).

    Returns:
        passed       — True when every flow passed (True when no flows ran)
        total        — total flow count
        passed_count — number of passing flows
        failed       — list of names of failing flows
    """
    if not results:
        return {"passed": True, "total": 0, "passed_count": 0, "failed": []}

    failed = [r["name"] for r in results if not r.get("passed")]
    return {
        "passed": len(failed) == 0,
        "total": len(results),
        "passed_count": len(results) - len(failed),
        "failed": failed,
    }


def format_flow_report(results: list[dict], base_url: str) -> str:
    """Build a human-readable UI flow validation report string."""
    evaluation = evaluate_flow_results(results)
    overall = "PASSED" if evaluation["passed"] else "FAILED"
    header = (
        f"UI Flow Report — {base_url}\n"
        f"Status: {overall}  "
        f"({evaluation['passed_count']}/{evaluation['total']} flows passed)\n"
    )
    lines = [header]
    for r in results:
        icon = "+" if r.get("passed") else "-"
        steps_run = r.get("steps_run", 0)
        line = f"  [{icon}] {r['name']}  ({steps_run} step(s))"
        if not r.get("passed") and r.get("error"):
            line += f"  — {r['error']}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def _run_flow_step(page, base_url: str, step: dict) -> Optional[str]:
    """Execute one flow step against an open Playwright page.

    Returns an error message string on failure, or None on success.
    Must only be called within a sync_playwright context.
    """
    action = step.get("action", "")
    selector = step.get("selector", "")
    value = step.get("value", "")

    try:
        if action == "navigate":
            url = value if value.startswith("http") else base_url.rstrip("/") + value
            page.goto(url, wait_until="domcontentloaded")
        elif action == "click":
            page.click(selector)
        elif action == "fill":
            page.fill(selector, value)
        elif action == "select":
            page.select_option(selector, value)
        elif action == "wait_for_selector":
            page.wait_for_selector(selector)
        elif action == "assert_text":
            if value and value not in page.content():
                return f"page does not contain {value!r}"
        elif action == "assert_url":
            if value and value not in page.url:
                return f"URL {page.url!r} does not contain {value!r}"
        elif action == "assert_element":
            if not page.query_selector(selector):
                return f"element {selector!r} not found"
        else:
            return f"unknown action {action!r}"
    except Exception as exc:
        return f"step {action!r} raised: {exc}"

    return None


def run_flow(page, base_url: str, flow: dict) -> dict:
    """Execute a multi-step flow against an open Playwright page.

    Args:
        page     — open Playwright Page object (inside a browser context)
        base_url — root URL (e.g. "https://my-app.vercel.app")
        flow     — flow dict with ``name`` and ``steps`` list

    Returns:
        {"name": str, "passed": bool, "error": Optional[str], "steps_run": int}
    """
    name = flow.get("name", "unnamed")
    steps = flow.get("steps", [])
    for i, step in enumerate(steps):
        error = _run_flow_step(page, base_url, step)
        if error:
            return {
                "name": name,
                "passed": False,
                "error": f"step {i + 1} ({step.get('action', '?')}): {error}",
                "steps_run": i + 1,
            }
    return {"name": name, "passed": True, "error": None, "steps_run": len(steps)}


def run_ui_flow_validation(
    base_url: str,
    flows: Optional[list[dict]] = None,
    timeout_ms: int = 20000,
    headless: bool = True,
) -> dict:
    """Launch a Chromium browser and run all UI flows against base_url.

    Args:
        base_url   — root URL to test (e.g. "https://my-app.vercel.app")
        flows      — list of flow dicts; defaults to build_default_flows (empty)
        timeout_ms — per-navigation/action timeout in milliseconds
        headless   — run the browser headless (default True)

    Returns:
        success  — True when all flows passed (or no flows were defined)
        results  — list of per-flow result dicts
        report   — human-readable string report
        error    — fatal error message when the browser crashed, else None
    """
    from tools.playwright_harness import is_playwright_available

    if not is_playwright_available():
        return {
            "success": False,
            "results": [],
            "report": "",
            "error": "playwright not installed; run: python -m playwright install",
        }

    if flows is None:
        flows = build_default_flows(base_url)

    if not flows:
        return {
            "success": True,
            "results": [],
            "report": format_flow_report([], base_url),
            "error": None,
        }

    results: list[dict] = []
    error_msg: Optional[str] = None

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            ctx = browser.new_context()
            ctx.set_default_navigation_timeout(timeout_ms)
            page = ctx.new_page()
            for flow in flows:
                result = run_flow(page, base_url, flow)
                results.append(result)
            browser.close()
    except Exception as exc:
        error_msg = str(exc)

    evaluation = evaluate_flow_results(results)
    report = format_flow_report(results, base_url)

    return {
        "success": evaluation["passed"] and error_msg is None,
        "results": results,
        "report": report,
        "error": error_msg,
    }
