"""Tests for tools/ui_flow_validator.py — pure helper functions only."""
import json

import pytest

from tools.ui_flow_validator import (
    build_default_flows,
    evaluate_flow_results,
    format_flow_report,
    load_flows_from_file,
)


# ── build_default_flows ─────────────────────────────────────────────────────

def test_build_default_flows_returns_empty_list():
    assert build_default_flows("https://example.com") == []


def test_build_default_flows_returns_list():
    result = build_default_flows("https://x.com")
    assert isinstance(result, list)


# ── evaluate_flow_results ───────────────────────────────────────────────────

def test_evaluate_flow_results_empty():
    result = evaluate_flow_results([])
    assert result == {"passed": True, "total": 0, "passed_count": 0, "failed": []}


def test_evaluate_flow_results_all_pass():
    results = [
        {"name": "flow a", "passed": True, "error": None},
        {"name": "flow b", "passed": True, "error": None},
    ]
    out = evaluate_flow_results(results)
    assert out["passed"] is True
    assert out["total"] == 2
    assert out["passed_count"] == 2
    assert out["failed"] == []


def test_evaluate_flow_results_some_fail():
    results = [
        {"name": "flow a", "passed": True, "error": None},
        {"name": "flow b", "passed": False, "error": "step 1: element not found"},
    ]
    out = evaluate_flow_results(results)
    assert out["passed"] is False
    assert out["total"] == 2
    assert out["passed_count"] == 1
    assert out["failed"] == ["flow b"]


def test_evaluate_flow_results_all_fail():
    results = [
        {"name": "flow a", "passed": False, "error": "oops"},
        {"name": "flow b", "passed": False, "error": "also bad"},
    ]
    out = evaluate_flow_results(results)
    assert out["passed"] is False
    assert out["passed_count"] == 0
    assert set(out["failed"]) == {"flow a", "flow b"}


def test_evaluate_flow_results_single_pass():
    results = [{"name": "only flow", "passed": True, "error": None}]
    out = evaluate_flow_results(results)
    assert out["passed"] is True
    assert out["total"] == 1
    assert out["passed_count"] == 1
    assert out["failed"] == []


def test_evaluate_flow_results_single_fail():
    results = [{"name": "only flow", "passed": False, "error": "bad"}]
    out = evaluate_flow_results(results)
    assert out["passed"] is False
    assert out["failed"] == ["only flow"]


# ── format_flow_report ──────────────────────────────────────────────────────

def test_format_flow_report_all_pass():
    results = [{"name": "login flow", "passed": True, "error": None, "steps_run": 3}]
    report = format_flow_report(results, "https://example.com")
    assert "PASSED" in report
    assert "login flow" in report
    assert "1/1" in report
    assert "3 step(s)" in report


def test_format_flow_report_some_fail():
    results = [
        {"name": "flow a", "passed": True, "error": None, "steps_run": 2},
        {
            "name": "flow b",
            "passed": False,
            "error": "step 2 (click): element #submit not found",
            "steps_run": 2,
        },
    ]
    report = format_flow_report(results, "https://example.com")
    assert "FAILED" in report
    assert "flow a" in report
    assert "flow b" in report
    assert "element #submit not found" in report
    assert "1/2" in report


def test_format_flow_report_empty():
    report = format_flow_report([], "https://example.com")
    assert "PASSED" in report
    assert "0/0" in report


def test_format_flow_report_contains_base_url():
    report = format_flow_report([], "https://my-app.vercel.app")
    assert "https://my-app.vercel.app" in report


def test_format_flow_report_pass_no_error_shown():
    results = [{"name": "checkout", "passed": True, "error": None, "steps_run": 5}]
    report = format_flow_report(results, "https://example.com")
    assert "[+]" in report
    assert "[-]" not in report


def test_format_flow_report_fail_shows_error():
    results = [{"name": "checkout", "passed": False, "error": "step 3: timeout", "steps_run": 3}]
    report = format_flow_report(results, "https://example.com")
    assert "[-]" in report
    assert "step 3: timeout" in report


# ── load_flows_from_file ────────────────────────────────────────────────────

def test_load_flows_from_file_valid(tmp_path):
    flows = [
        {
            "name": "login flow",
            "steps": [
                {"action": "navigate", "value": "/login"},
                {"action": "fill", "selector": "#email", "value": "test@example.com"},
            ],
        }
    ]
    p = tmp_path / "ui_flows.json"
    p.write_text(json.dumps(flows))
    loaded = load_flows_from_file(str(p))
    assert loaded == flows


def test_load_flows_from_file_multiple_flows(tmp_path):
    flows = [
        {"name": "flow a", "steps": []},
        {"name": "flow b", "steps": []},
    ]
    p = tmp_path / "ui_flows.json"
    p.write_text(json.dumps(flows))
    loaded = load_flows_from_file(str(p))
    assert len(loaded) == 2
    assert loaded[0]["name"] == "flow a"


def test_load_flows_from_file_empty_list(tmp_path):
    p = tmp_path / "ui_flows.json"
    p.write_text("[]")
    result = load_flows_from_file(str(p))
    assert result == []


def test_load_flows_from_file_not_found():
    result = load_flows_from_file("/nonexistent/path/does_not_exist.json")
    assert result == []


def test_load_flows_from_file_invalid_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("not valid json {{{{")
    result = load_flows_from_file(str(p))
    assert result == []


def test_load_flows_from_file_non_list_json(tmp_path):
    p = tmp_path / "obj.json"
    p.write_text(json.dumps({"flows": [{"name": "flow a"}]}))
    result = load_flows_from_file(str(p))
    assert result == []


def test_load_flows_from_file_null_json(tmp_path):
    p = tmp_path / "null.json"
    p.write_text("null")
    result = load_flows_from_file(str(p))
    assert result == []
