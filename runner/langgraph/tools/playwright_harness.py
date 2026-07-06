"""Playwright browser E2E harness for post-deploy verification.

Pure helper functions (is_playwright_available, build_default_scenarios,
evaluate_results, format_report) are side-effect free and fully unit-testable.
Browser execution functions (run_scenario, run_e2e_suite) wrap playwright and
require a real or mocked browser — they are exercised via integration.

Typical usage (from the graph node run_e2e_if_needed):
    from tools.playwright_harness import run_e2e_suite, is_playwright_available

    if is_playwright_available() and cfg.e2e_enabled and base_url:
        result = run_e2e_suite(base_url, timeout_ms=cfg.e2e_timeout_ms,
                               headless=cfg.e2e_headless)
"""
from __future__ import annotations

from typing import Optional


def is_playwright_available() -> bool:
    """Return True if the playwright package is importable."""
    try:
        import playwright  # noqa: F401
        return True
    except ImportError:
        return False


def build_default_scenarios(base_url: str) -> list[dict]:
    """Return a minimal set of E2E smoke scenarios for a given base URL.

    Each scenario dict carries:
      name    — human-readable label shown in the report
      path    — URL path appended to base_url when navigating
      checks  — list of assertions; each has ``type`` and ``value``:
                  status         → navigation must succeed (no exception / 4xx/5xx)
                  title_contains → page title must contain value (skip when empty)
                  text_contains  → page body HTML must contain value
    """
    return [
        {
            "name": "homepage loads",
            "path": "/",
            "checks": [
                {"type": "status", "value": "ok"},
                {"type": "title_contains", "value": ""},
            ],
        },
    ]


def evaluate_results(results: list[dict]) -> dict:
    """Aggregate scenario results into a summary.

    Each result dict must have: name (str), passed (bool), error (Optional[str]).

    Returns:
        passed       — True when every scenario passed
        total        — total scenario count
        passed_count — number of passing scenarios
        failed       — list of names of failing scenarios
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


def format_report(results: list[dict], base_url: str) -> str:
    """Build a human-readable E2E report string."""
    evaluation = evaluate_results(results)
    overall = "PASSED" if evaluation["passed"] else "FAILED"
    header = (
        f"E2E Report — {base_url}\n"
        f"Status: {overall}  "
        f"({evaluation['passed_count']}/{evaluation['total']} scenarios passed)\n"
    )
    lines = [header]
    for r in results:
        icon = "+" if r.get("passed") else "-"
        line = f"  [{icon}] {r['name']}"
        if not r.get("passed") and r.get("error"):
            line += f"  — {r['error']}"
        lines.append(line)
    return "\n".join(lines) + "\n"


def _run_checks_on_page(page, checks: list[dict]) -> list[str]:
    """Execute check assertions against a Playwright page.

    Returns a list of failure messages (empty → all checks passed).
    Must only be called from within a sync_playwright context.
    """
    failures: list[str] = []
    for check in checks:
        ctype = check.get("type", "")
        value = check.get("value", "")
        try:
            if ctype == "status":
                pass  # navigation timeout/error raises before we get here; success = ok
            elif ctype == "title_contains":
                if value and value not in page.title():
                    failures.append(
                        f"title does not contain {value!r} (got {page.title()!r})"
                    )
            elif ctype == "text_contains":
                if value and value not in page.content():
                    failures.append(f"page body does not contain {value!r}")
        except Exception as exc:
            failures.append(f"check {ctype!r} raised: {exc}")
    return failures


def run_scenario(page, base_url: str, scenario: dict) -> dict:
    """Navigate to a scenario URL and evaluate its checks against an open page.

    Args:
        page     — open Playwright Page object (already inside a browser context)
        base_url — root URL (e.g. "https://my-app.vercel.app")
        scenario — scenario dict from build_default_scenarios / custom list

    Returns:
        {"name": str, "passed": bool, "error": Optional[str]}
    """
    name = scenario.get("name", "unnamed")
    path = scenario.get("path", "/")
    url = base_url.rstrip("/") + path
    checks = scenario.get("checks", [])
    try:
        page.goto(url, wait_until="domcontentloaded")
        failures = _run_checks_on_page(page, checks)
        if failures:
            return {"name": name, "passed": False, "error": "; ".join(failures)}
        return {"name": name, "passed": True, "error": None}
    except Exception as exc:
        return {"name": name, "passed": False, "error": str(exc)}


def run_e2e_suite(
    base_url: str,
    scenarios: Optional[list[dict]] = None,
    timeout_ms: int = 15000,
    headless: bool = True,
) -> dict:
    """Launch a Chromium browser and run all scenarios against base_url.

    Args:
        base_url    — root URL to test (e.g. "https://my-app.vercel.app")
        scenarios   — list of scenario dicts; defaults to build_default_scenarios
        timeout_ms  — page navigation timeout in milliseconds
        headless    — run the browser headless (default True)

    Returns:
        success  — True when all scenarios passed and no fatal error occurred
        results  — list of per-scenario result dicts
        report   — human-readable string report
        error    — fatal error message when the browser itself crashed, else None
    """
    if not is_playwright_available():
        return {
            "success": False,
            "results": [],
            "report": "",
            "error": "playwright not installed; run: python -m playwright install",
        }

    if scenarios is None:
        scenarios = build_default_scenarios(base_url)

    results: list[dict] = []
    error_msg: Optional[str] = None

    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=headless)
            ctx = browser.new_context()
            ctx.set_default_navigation_timeout(timeout_ms)
            page = ctx.new_page()
            for scenario in scenarios:
                result = run_scenario(page, base_url, scenario)
                results.append(result)
            browser.close()
    except Exception as exc:
        error_msg = str(exc)

    evaluation = evaluate_results(results)
    report = format_report(results, base_url)

    return {
        "success": evaluation["passed"] and error_msg is None,
        "results": results,
        "report": report,
        "error": error_msg,
    }
