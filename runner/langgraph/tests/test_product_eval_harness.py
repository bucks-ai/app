"""Unit tests for tools/product_eval_harness.py — pure helpers only."""
import json
import pytest

from tools.product_eval_harness import (
    build_default_evals,
    load_evals_from_file,
    evaluate_eval_results,
    format_eval_report,
    run_product_eval_suite,
    _run_check,
)


class TestBuildDefaultEvals:
    def test_returns_empty_list(self):
        assert build_default_evals("https://example.com") == []

    def test_ignores_base_url_arg(self):
        assert build_default_evals("https://anything.com") == []


class TestLoadEvalsFromFile:
    def test_loads_valid_json_list(self, tmp_path):
        data = [{"name": "test", "path": "/", "checks": []}]
        p = tmp_path / "evals.json"
        p.write_text(json.dumps(data))
        assert load_evals_from_file(str(p)) == data

    def test_returns_empty_on_missing_file(self):
        assert load_evals_from_file("/no/such/file.json") == []

    def test_returns_empty_on_invalid_json(self, tmp_path):
        p = tmp_path / "bad.json"
        p.write_text("not json {{{")
        assert load_evals_from_file(str(p)) == []

    def test_returns_empty_when_top_level_is_dict(self, tmp_path):
        p = tmp_path / "obj.json"
        p.write_text(json.dumps({"name": "x"}))
        assert load_evals_from_file(str(p)) == []

    def test_returns_empty_list_for_empty_array(self, tmp_path):
        p = tmp_path / "empty.json"
        p.write_text("[]")
        assert load_evals_from_file(str(p)) == []

    def test_multiple_evals_loaded(self, tmp_path):
        data = [
            {"name": "a", "path": "/a", "checks": []},
            {"name": "b", "path": "/b", "checks": []},
        ]
        p = tmp_path / "multi.json"
        p.write_text(json.dumps(data))
        assert load_evals_from_file(str(p)) == data


class TestEvaluateEvalResults:
    def test_empty_results_pass(self):
        result = evaluate_eval_results([])
        assert result["passed"] is True
        assert result["total"] == 0
        assert result["passed_count"] == 0
        assert result["failed"] == []

    def test_all_passed(self):
        results = [
            {"name": "a", "passed": True},
            {"name": "b", "passed": True},
        ]
        r = evaluate_eval_results(results)
        assert r["passed"] is True
        assert r["total"] == 2
        assert r["passed_count"] == 2
        assert r["failed"] == []

    def test_some_failed(self):
        results = [
            {"name": "a", "passed": True},
            {"name": "b", "passed": False},
            {"name": "c", "passed": False},
        ]
        r = evaluate_eval_results(results)
        assert r["passed"] is False
        assert r["total"] == 3
        assert r["passed_count"] == 1
        assert set(r["failed"]) == {"b", "c"}

    def test_all_failed(self):
        results = [{"name": "x", "passed": False}]
        r = evaluate_eval_results(results)
        assert r["passed"] is False
        assert r["passed_count"] == 0
        assert r["failed"] == ["x"]

    def test_single_pass(self):
        results = [{"name": "only", "passed": True}]
        r = evaluate_eval_results(results)
        assert r["passed"] is True
        assert r["total"] == 1
        assert r["passed_count"] == 1


class TestFormatEvalReport:
    def test_empty_results(self):
        report = format_eval_report([], "https://example.com")
        assert "PASSED" in report
        assert "0/0" in report

    def test_passed_result(self):
        results = [{"name": "homepage", "passed": True, "checks_run": 2}]
        report = format_eval_report(results, "https://example.com")
        assert "PASSED" in report
        assert "1/1" in report
        assert "[+]" in report
        assert "homepage" in report
        assert "2 check(s)" in report

    def test_failed_result_with_error(self):
        results = [{"name": "api", "passed": False, "checks_run": 1, "error": "status 500"}]
        report = format_eval_report(results, "https://example.com")
        assert "FAILED" in report
        assert "0/1" in report
        assert "[-]" in report
        assert "status 500" in report

    def test_includes_base_url(self):
        report = format_eval_report([], "https://my-app.vercel.app")
        assert "https://my-app.vercel.app" in report

    def test_mixed_results(self):
        results = [
            {"name": "ok", "passed": True, "checks_run": 1},
            {"name": "bad", "passed": False, "checks_run": 1, "error": "oops"},
        ]
        report = format_eval_report(results, "https://example.com")
        assert "FAILED" in report
        assert "1/2" in report
        assert "[+]" in report
        assert "[-]" in report

    def test_failed_result_no_error_field(self):
        results = [{"name": "x", "passed": False, "checks_run": 0}]
        report = format_eval_report(results, "https://example.com")
        assert "[-]" in report


class TestRunCheck:
    def test_status_pass(self):
        assert _run_check({"type": "status", "value": 200}, 200, "", {}) is None

    def test_status_pass_string_value(self):
        assert _run_check({"type": "status", "value": "200"}, 200, "", {}) is None

    def test_status_fail(self):
        err = _run_check({"type": "status", "value": 200}, 404, "", {})
        assert err is not None
        assert "404" in err

    def test_body_contains_pass(self):
        assert _run_check({"type": "body_contains", "value": "hello"}, 200, "hello world", {}) is None

    def test_body_contains_fail(self):
        err = _run_check({"type": "body_contains", "value": "missing"}, 200, "other text", {})
        assert err is not None
        assert "missing" in err

    def test_header_contains_pass(self):
        assert _run_check(
            {"type": "header_contains", "key": "content-type", "value": "html"},
            200, "", {"content-type": "text/html; charset=utf-8"}
        ) is None

    def test_header_contains_case_insensitive_key(self):
        assert _run_check(
            {"type": "header_contains", "key": "Content-Type", "value": "html"},
            200, "", {"content-type": "text/html"}
        ) is None

    def test_header_contains_fail(self):
        err = _run_check(
            {"type": "header_contains", "key": "content-type", "value": "json"},
            200, "", {"content-type": "text/html"}
        )
        assert err is not None

    def test_header_contains_missing_header(self):
        err = _run_check(
            {"type": "header_contains", "key": "x-missing", "value": "foo"},
            200, "", {}
        )
        assert err is not None

    def test_json_key_pass(self):
        body = json.dumps({"status": "ok"})
        assert _run_check({"type": "json_key", "key": "status", "value": "ok"}, 200, body, {}) is None

    def test_json_key_pass_int_value(self):
        body = json.dumps({"count": 42})
        assert _run_check({"type": "json_key", "key": "count", "value": "42"}, 200, body, {}) is None

    def test_json_key_fail_value(self):
        body = json.dumps({"status": "error"})
        err = _run_check({"type": "json_key", "key": "status", "value": "ok"}, 200, body, {})
        assert err is not None

    def test_json_key_fail_missing_key(self):
        body = json.dumps({"other": "val"})
        err = _run_check({"type": "json_key", "key": "status", "value": "ok"}, 200, body, {})
        assert err is not None
        assert "not found" in err

    def test_json_key_fail_invalid_json(self):
        err = _run_check({"type": "json_key", "key": "status", "value": "ok"}, 200, "not json", {})
        assert err is not None
        assert "JSON" in err

    def test_json_key_exists_pass(self):
        body = json.dumps({"status": "ok"})
        assert _run_check({"type": "json_key_exists", "key": "status"}, 200, body, {}) is None

    def test_json_key_exists_fail(self):
        body = json.dumps({"other": "val"})
        err = _run_check({"type": "json_key_exists", "key": "missing"}, 200, body, {})
        assert err is not None

    def test_json_key_exists_fail_invalid_json(self):
        err = _run_check({"type": "json_key_exists", "key": "k"}, 200, "not-json", {})
        assert err is not None

    def test_unknown_check_type(self):
        err = _run_check({"type": "unknown_type"}, 200, "", {})
        assert err is not None
        assert "unknown" in err

    def test_empty_check_type(self):
        err = _run_check({}, 200, "", {})
        assert err is not None


class TestRunProductEvalSuiteEmpty:
    def test_empty_evals_succeed(self):
        result = run_product_eval_suite("https://example.com", evals=[])
        assert result["success"] is True
        assert result["results"] == []
        assert result["error"] is None
        assert "report" in result

    def test_default_evals_empty(self):
        result = run_product_eval_suite("https://example.com")
        assert result["success"] is True
        assert result["results"] == []

    def test_empty_report_includes_url(self):
        result = run_product_eval_suite("https://myapp.com", evals=[])
        assert "myapp.com" in result["report"]
