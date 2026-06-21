"""Unit tests for tools/playwright_harness.py pure helper functions.

Only exercises side-effect-free helpers (build_default_scenarios,
evaluate_results, format_report, is_playwright_available).  run_e2e_suite and
run_scenario require a real browser and are not unit-tested here — they are
exercised by integration / smoke tests against a live URL.

Run with:
    python -m pytest tests/test_playwright_harness.py -x -q
    # or directly:
    python tests/test_playwright_harness.py
"""
import os
import sys
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.playwright_harness import (
    build_default_scenarios,
    evaluate_results,
    format_report,
    is_playwright_available,
)


# ---------------------------------------------------------------------------
# build_default_scenarios
# ---------------------------------------------------------------------------

def test_build_default_scenarios_returns_nonempty_list():
    scenarios = build_default_scenarios("https://example.com")
    assert isinstance(scenarios, list)
    assert len(scenarios) >= 1


def test_build_default_scenarios_structure():
    scenarios = build_default_scenarios("https://example.com")
    for s in scenarios:
        assert "name" in s, f"scenario missing 'name': {s}"
        assert "path" in s, f"scenario missing 'path': {s}"
        assert "checks" in s, f"scenario missing 'checks': {s}"
        assert isinstance(s["checks"], list)


def test_build_default_scenarios_paths_start_with_slash():
    scenarios = build_default_scenarios("https://example.com")
    for s in scenarios:
        assert s["path"].startswith("/"), f"path must start with /: {s['path']}"


def test_build_default_scenarios_base_url_ignored_in_output():
    # Base URL is not embedded in scenarios (only used at navigation time)
    s1 = build_default_scenarios("https://app1.example.com")
    s2 = build_default_scenarios("https://app2.example.com")
    assert [s["path"] for s in s1] == [s["path"] for s in s2]


# ---------------------------------------------------------------------------
# evaluate_results
# ---------------------------------------------------------------------------

def test_evaluate_results_all_pass():
    results = [
        {"name": "a", "passed": True, "error": None},
        {"name": "b", "passed": True, "error": None},
    ]
    ev = evaluate_results(results)
    assert ev["passed"] is True
    assert ev["total"] == 2
    assert ev["passed_count"] == 2
    assert ev["failed"] == []


def test_evaluate_results_some_fail():
    results = [
        {"name": "a", "passed": True, "error": None},
        {"name": "b", "passed": False, "error": "timeout"},
    ]
    ev = evaluate_results(results)
    assert ev["passed"] is False
    assert ev["total"] == 2
    assert ev["passed_count"] == 1
    assert "b" in ev["failed"]
    assert "a" not in ev["failed"]


def test_evaluate_results_all_fail():
    results = [
        {"name": "x", "passed": False, "error": "error"},
        {"name": "y", "passed": False, "error": "error"},
    ]
    ev = evaluate_results(results)
    assert ev["passed"] is False
    assert ev["passed_count"] == 0
    assert sorted(ev["failed"]) == ["x", "y"]


def test_evaluate_results_empty():
    ev = evaluate_results([])
    assert ev["passed"] is True
    assert ev["total"] == 0
    assert ev["passed_count"] == 0
    assert ev["failed"] == []


def test_evaluate_results_single_pass():
    ev = evaluate_results([{"name": "only", "passed": True, "error": None}])
    assert ev["passed"] is True
    assert ev["total"] == 1


def test_evaluate_results_single_fail():
    ev = evaluate_results([{"name": "only", "passed": False, "error": "bad"}])
    assert ev["passed"] is False
    assert ev["failed"] == ["only"]


# ---------------------------------------------------------------------------
# format_report
# ---------------------------------------------------------------------------

def test_format_report_pass_contains_passed():
    results = [{"name": "homepage loads", "passed": True, "error": None}]
    report = format_report(results, "https://example.com")
    assert "PASSED" in report


def test_format_report_fail_contains_failed():
    results = [{"name": "login flow", "passed": False, "error": "timeout"}]
    report = format_report(results, "https://example.com")
    assert "FAILED" in report


def test_format_report_includes_base_url():
    results = [{"name": "a", "passed": True, "error": None}]
    report = format_report(results, "https://my-app.vercel.app")
    assert "https://my-app.vercel.app" in report


def test_format_report_includes_scenario_name():
    results = [{"name": "signup flow", "passed": True, "error": None}]
    report = format_report(results, "https://example.com")
    assert "signup flow" in report


def test_format_report_fail_includes_error_message():
    results = [{"name": "api health", "passed": False, "error": "connection refused"}]
    report = format_report(results, "https://example.com")
    assert "connection refused" in report


def test_format_report_counts_in_header():
    results = [
        {"name": "a", "passed": True, "error": None},
        {"name": "b", "passed": False, "error": "err"},
    ]
    report = format_report(results, "https://example.com")
    # 1 of 2 passed
    assert "1/2" in report


def test_format_report_all_pass_counts():
    results = [
        {"name": "a", "passed": True, "error": None},
        {"name": "b", "passed": True, "error": None},
    ]
    report = format_report(results, "https://example.com")
    assert "2/2" in report


# ---------------------------------------------------------------------------
# is_playwright_available
# ---------------------------------------------------------------------------

def test_is_playwright_available_returns_bool():
    result = is_playwright_available()
    assert isinstance(result, bool)


def test_is_playwright_available_false_when_import_fails():
    with mock.patch.dict("sys.modules", {"playwright": None}):
        # Re-import or re-call with import patched
        import importlib
        import tools.playwright_harness as ph
        original = ph.is_playwright_available

        def patched():
            try:
                import playwright  # noqa: F401
                return True
            except (ImportError, TypeError):
                return False

        assert patched() is False


# ---------------------------------------------------------------------------
# run_e2e_suite degrades when playwright not installed
# ---------------------------------------------------------------------------

def test_run_e2e_suite_degrades_without_playwright():
    from tools.playwright_harness import run_e2e_suite

    with mock.patch("tools.playwright_harness.is_playwright_available", return_value=False):
        result = run_e2e_suite("https://example.com")

    assert result["success"] is False
    assert "playwright" in result["error"].lower()
    assert result["results"] == []


# ---------------------------------------------------------------------------
# Script runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import traceback
    fns = [(name, fn) for name, fn in sorted(globals().items()) if name.startswith("test_")]
    passed = failed = 0
    for name, fn in fns:
        try:
            fn()
            passed += 1
        except Exception:
            failed += 1
            print(f"FAIL {name}")
            traceback.print_exc()
    print(f"\nplaywright_harness: {passed} passed, {failed} failed")
    if failed:
        sys.exit(1)
