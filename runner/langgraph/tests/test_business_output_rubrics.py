"""Unit tests for tools/business_output_rubrics.py — pure helpers only."""
import pytest

from tools.business_output_rubrics import (
    _score_functional_correctness,
    _score_business_value_alignment,
    _score_completeness,
    _score_risk_awareness,
    score_rubric_dimensions,
    evaluate_rubric_scores,
    format_rubric_report,
    evaluate_business_output,
    guard_business_output,
    _PASS_THRESHOLD_DEFAULT,
)


# ---------------------------------------------------------------------------
# _score_functional_correctness
# ---------------------------------------------------------------------------

class TestScoreFunctionalCorrectness:
    def _summary(self, check_result, files_created=None, files_modified=None):
        return {
            "check_result": check_result,
            "files_created": files_created or [],
            "files_modified": files_modified or [],
        }

    def test_check_passed_with_files(self):
        score, rationale = _score_functional_correctness(
            self._summary(True, files_created=["foo.py"])
        )
        assert score == 1.0
        assert "check passed" in rationale

    def test_check_passed_no_files(self):
        score, rationale = _score_functional_correctness(self._summary(True))
        assert score == 0.6
        assert "check passed" in rationale
        assert "no files" in rationale

    def test_check_failed(self):
        score, rationale = _score_functional_correctness(
            self._summary(False, files_created=["foo.py"])
        )
        assert score == 0.0
        assert "failed" in rationale

    def test_check_unknown_with_files(self):
        score, rationale = _score_functional_correctness(
            self._summary(None, files_modified=["bar.py"])
        )
        assert score == 0.7
        assert "unknown" in rationale

    def test_check_unknown_no_files(self):
        score, rationale = _score_functional_correctness(self._summary(None))
        assert score == 0.3
        assert "unknown" in rationale

    def test_empty_string_files_treated_as_none(self):
        summary = {
            "check_result": True,
            "files_created": ["none"],
            "files_modified": [""],
        }
        score, _ = _score_functional_correctness(summary)
        assert score == 0.6  # "none" and "" are empty values

    def test_files_created_counts(self):
        summary = {
            "check_result": True,
            "files_created": ["a.py", "b.py"],
            "files_modified": [],
        }
        score, _ = _score_functional_correctness(summary)
        assert score == 1.0


# ---------------------------------------------------------------------------
# _score_business_value_alignment
# ---------------------------------------------------------------------------

class TestScoreBusinessValueAlignment:
    def _call(self, task, raw_output):
        return _score_business_value_alignment({}, task, raw_output)

    def test_no_task_description(self):
        score, rationale = self._call({}, "some output")
        assert score == 0.8
        assert "no task description" in rationale

    def test_task_with_no_scorable_keywords(self):
        # very short words won't be picked up
        score, rationale = self._call({"title": "do it"}, "some output")
        assert score == 0.8
        assert "no scorable keywords" in rationale

    def test_all_keywords_matched(self):
        task = {"title": "implement authentication module"}
        output = "I implemented the authentication module successfully"
        score, rationale = self._call(task, output)
        assert score == 1.0
        assert "matched" in rationale

    def test_no_keywords_matched(self):
        task = {"title": "implement authentication module"}
        output = "completely unrelated text here"
        score, rationale = self._call(task, output)
        assert score < 0.5
        assert "matched 0/" in rationale

    def test_partial_keyword_match(self):
        task = {"title": "implement authentication module testing"}
        output = "implement and testing complete"
        score, rationale = self._call(task, output)
        assert 0.0 < score < 1.0
        assert "matched" in rationale

    def test_uses_description_too(self):
        task = {"title": "auth", "description": "validate tokens properly"}
        output = "tokens validated properly"
        score, _ = self._call(task, output)
        assert score > 0.5

    def test_case_insensitive_matching(self):
        task = {"title": "implement Authentication Module"}
        output = "authentication module implementation done"
        score, _ = self._call(task, output)
        assert score == 1.0

    def test_deduplicated_keywords(self):
        task = {"title": "authentication authentication authentication"}
        output = "authentication done"
        score, rationale = self._call(task, output)
        assert score == 1.0  # deduplicated, so 1/1


# ---------------------------------------------------------------------------
# _score_completeness
# ---------------------------------------------------------------------------

class TestScoreCompleteness:
    def test_all_positive(self):
        summary = {
            "files_created": ["a.py"],
            "files_modified": [],
            "credentials_needed": [],
            "known_limitations": [],
        }
        score, notes = _score_completeness(summary)
        assert score == pytest.approx(1.0)  # 0.5 + 0.3 + 0.1 + 0.1 = 1.0
        assert "file(s) touched" in notes

    def test_no_files_no_creds_no_limits(self):
        summary = {
            "files_created": [],
            "files_modified": [],
            "credentials_needed": [],
            "known_limitations": [],
        }
        score, notes = _score_completeness(summary)
        assert score == pytest.approx(0.7)
        assert "no files" in notes

    def test_credentials_needed_deducts(self):
        summary = {
            "files_created": ["x.py"],
            "files_modified": [],
            "credentials_needed": ["OPENAI_API_KEY"],
            "known_limitations": [],
        }
        score, notes = _score_completeness(summary)
        assert score == pytest.approx(0.8)
        assert "credential(s) needed" in notes

    def test_known_limitations_deducts(self):
        summary = {
            "files_created": ["x.py"],
            "files_modified": [],
            "credentials_needed": [],
            "known_limitations": ["requires manual step"],
        }
        score, notes = _score_completeness(summary)
        assert score == pytest.approx(0.8)
        assert "known limitation(s)" in notes

    def test_creds_and_limits_both_deduct(self):
        summary = {
            "files_created": [],
            "files_modified": [],
            "credentials_needed": ["KEY"],
            "known_limitations": ["limitation"],
        }
        score, _ = _score_completeness(summary)
        assert score == pytest.approx(0.3)

    def test_none_values_treated_as_empty(self):
        summary = {
            "files_created": None,
            "files_modified": None,
            "credentials_needed": ["none"],
            "known_limitations": ["n/a"],
        }
        score, notes = _score_completeness(summary)
        assert score == pytest.approx(0.7)
        assert "no files" in notes

    def test_score_floor_is_zero(self):
        summary = {
            "files_created": [],
            "files_modified": [],
            "credentials_needed": ["A", "B", "C"],
            "known_limitations": ["X", "Y", "Z"],
        }
        score, _ = _score_completeness(summary)
        assert score >= 0.0


# ---------------------------------------------------------------------------
# _score_risk_awareness
# ---------------------------------------------------------------------------

class TestScoreRiskAwareness:
    def test_clean_output(self):
        score, rationale = _score_risk_awareness({}, "all good here, no secrets")
        assert score == 1.0
        assert "no security red flags" in rationale

    def test_password_in_output(self):
        score, rationale = _score_risk_awareness(
            {}, "password=supersecret123 was set"
        )
        assert score < 1.0
        assert "credential" in rationale

    def test_api_key_pattern(self):
        score, rationale = _score_risk_awareness(
            {}, "api_key: sk-abcdefghijklmnopqrstuvwx"
        )
        assert score < 1.0

    def test_private_key_header(self):
        score, rationale = _score_risk_awareness(
            {}, "-----BEGIN RSA PRIVATE KEY-----"
        )
        assert score < 1.0

    def test_api_key_prefix_pattern(self):
        score, _ = _score_risk_awareness(
            {}, "using sk-ABCDEFGHIJKLMNOPQRSTUVWXYZ1234"
        )
        assert score < 1.0

    def test_score_floor_at_zero(self):
        # Trigger multiple red flags — score must not go below 0
        output = (
            "password=leaked123 "
            "secret: sk-aaaabbbbccccddddeeeeffffgggghhhh "
            "-----BEGIN PRIVATE KEY-----"
        )
        score, _ = _score_risk_awareness({}, output)
        assert score >= 0.0

    def test_benign_key_name_in_output(self):
        # Mentioning key names without values is fine
        score, rationale = _score_risk_awareness(
            {}, "OPENAI_API_KEY is required but was not provided"
        )
        assert score == 1.0
        assert "no security red flags" in rationale


# ---------------------------------------------------------------------------
# score_rubric_dimensions
# ---------------------------------------------------------------------------

class TestScoreRubricDimensions:
    def test_returns_four_dimensions(self):
        summary = {"check_result": True, "files_created": ["f.py"]}
        task = {"id": "t1", "title": "add feature"}
        dims = score_rubric_dimensions(summary, task, "feature added successfully")
        assert len(dims) == 4

    def test_dimension_keys(self):
        dims = score_rubric_dimensions({}, {}, "")
        for d in dims:
            assert "name" in d
            assert "weight" in d
            assert "score" in d
            assert "rationale" in d

    def test_weights_sum_to_one(self):
        dims = score_rubric_dimensions({}, {}, "")
        total = sum(d["weight"] for d in dims)
        assert total == pytest.approx(1.0)

    def test_dimension_names(self):
        dims = score_rubric_dimensions({}, {}, "")
        names = [d["name"] for d in dims]
        assert "functional_correctness" in names
        assert "business_value_alignment" in names
        assert "completeness" in names
        assert "risk_awareness" in names

    def test_scores_in_range(self):
        summary = {"check_result": False}
        dims = score_rubric_dimensions(summary, {}, "")
        for d in dims:
            assert 0.0 <= d["score"] <= 1.0


# ---------------------------------------------------------------------------
# evaluate_rubric_scores
# ---------------------------------------------------------------------------

class TestEvaluateRubricScores:
    def test_empty_dimensions_pass(self):
        result = evaluate_rubric_scores([])
        assert result["passed"] is True
        assert result["overall_score"] == 1.0

    def test_all_ones_pass(self):
        dims = [
            {"name": "a", "weight": 0.5, "score": 1.0},
            {"name": "b", "weight": 0.5, "score": 1.0},
        ]
        result = evaluate_rubric_scores(dims)
        assert result["passed"] is True
        assert result["overall_score"] == pytest.approx(1.0)

    def test_all_zeros_fail(self):
        dims = [
            {"name": "a", "weight": 0.5, "score": 0.0},
            {"name": "b", "weight": 0.5, "score": 0.0},
        ]
        result = evaluate_rubric_scores(dims, pass_threshold=0.6)
        assert result["passed"] is False
        assert result["overall_score"] == pytest.approx(0.0)

    def test_weighted_average(self):
        dims = [
            {"name": "a", "weight": 0.7, "score": 1.0},
            {"name": "b", "weight": 0.3, "score": 0.0},
        ]
        result = evaluate_rubric_scores(dims)
        assert result["overall_score"] == pytest.approx(0.7)

    def test_custom_threshold(self):
        dims = [
            {"name": "a", "weight": 1.0, "score": 0.5},
        ]
        assert evaluate_rubric_scores(dims, pass_threshold=0.4)["passed"] is True
        assert evaluate_rubric_scores(dims, pass_threshold=0.6)["passed"] is False

    def test_result_contains_dimension_scores(self):
        dims = [{"name": "x", "weight": 1.0, "score": 0.8}]
        result = evaluate_rubric_scores(dims)
        assert result["dimension_scores"] == dims

    def test_result_contains_pass_threshold(self):
        result = evaluate_rubric_scores([], pass_threshold=0.75)
        assert result["pass_threshold"] == 0.75


# ---------------------------------------------------------------------------
# format_rubric_report
# ---------------------------------------------------------------------------

class TestFormatRubricReport:
    def _evaluation(self, overall=0.8, passed=True, dims=None):
        return {
            "overall_score": overall,
            "passed": passed,
            "pass_threshold": _PASS_THRESHOLD_DEFAULT,
            "dimension_scores": dims or [],
        }

    def test_passed_status_in_report(self):
        report = format_rubric_report(self._evaluation(overall=0.8, passed=True), {})
        assert "PASSED" in report

    def test_failed_status_in_report(self):
        report = format_rubric_report(self._evaluation(overall=0.3, passed=False), {})
        assert "FAILED" in report

    def test_includes_task_id(self):
        report = format_rubric_report(self._evaluation(), {"id": "t123"})
        assert "t123" in report

    def test_includes_task_title(self):
        report = format_rubric_report(self._evaluation(), {"id": "t1", "title": "my feature"})
        assert "my feature" in report

    def test_includes_score(self):
        report = format_rubric_report(self._evaluation(overall=0.75), {})
        assert "0.75" in report

    def test_dimension_lines_included(self):
        dims = [
            {"name": "functional_correctness", "weight": 0.30, "score": 1.0, "rationale": "all good"},
            {"name": "completeness", "weight": 0.25, "score": 0.2, "rationale": "missing stuff"},
        ]
        report = format_rubric_report(self._evaluation(dims=dims), {"id": "x"})
        assert "functional_correctness" in report
        assert "completeness" in report
        assert "all good" in report
        assert "missing stuff" in report

    def test_plus_icon_for_high_score(self):
        dims = [{"name": "d", "weight": 1.0, "score": 0.9, "rationale": "great"}]
        report = format_rubric_report(self._evaluation(dims=dims), {})
        assert "[+]" in report

    def test_minus_icon_for_low_score(self):
        dims = [{"name": "d", "weight": 1.0, "score": 0.1, "rationale": "bad"}]
        report = format_rubric_report(self._evaluation(dims=dims), {})
        assert "[-]" in report

    def test_tilde_icon_for_mid_score(self):
        dims = [{"name": "d", "weight": 1.0, "score": 0.5, "rationale": "mid"}]
        report = format_rubric_report(self._evaluation(dims=dims), {})
        assert "[~]" in report


# ---------------------------------------------------------------------------
# evaluate_business_output
# ---------------------------------------------------------------------------

class TestEvaluateBusinessOutput:
    def test_returns_required_keys(self):
        result = evaluate_business_output({}, {}, "")
        assert "overall_score" in result
        assert "passed" in result
        assert "pass_threshold" in result
        assert "dimension_scores" in result
        assert "report" in result

    def test_full_pass_scenario(self):
        summary = {
            "check_result": True,
            "files_created": ["tools/new.py"],
            "files_modified": [],
            "credentials_needed": [],
            "known_limitations": [],
        }
        task = {"id": "t1", "title": "add new tool"}
        output = "added the new tool successfully to the codebase"
        result = evaluate_business_output(summary, task, output)
        assert result["overall_score"] >= 0.6
        assert result["passed"] is True

    def test_full_fail_scenario(self):
        summary = {
            "check_result": False,
            "files_created": [],
            "files_modified": [],
            "credentials_needed": ["SECRET_KEY"],
            "known_limitations": ["not fully implemented"],
        }
        task = {"id": "t2", "title": "authentication refactor complete"}
        result = evaluate_business_output(summary, task, "error encountered", pass_threshold=0.8)
        assert result["passed"] is False

    def test_custom_pass_threshold(self):
        summary = {"check_result": True, "files_created": ["x.py"]}
        result_strict = evaluate_business_output(summary, {}, "x", pass_threshold=0.96)
        result_lenient = evaluate_business_output(summary, {}, "x", pass_threshold=0.1)
        assert result_lenient["passed"] is True
        assert result_strict["passed"] is False

    def test_report_is_string(self):
        result = evaluate_business_output({}, {"id": "x"}, "")
        assert isinstance(result["report"], str)
        assert len(result["report"]) > 0


# ---------------------------------------------------------------------------
# guard_business_output
# ---------------------------------------------------------------------------

class TestGuardBusinessOutput:
    def _passing_inputs(self):
        summary = {
            "check_result": True,
            "files_created": ["a.py"],
            "files_modified": [],
            "credentials_needed": [],
            "known_limitations": [],
        }
        task = {"id": "guard-task", "title": "implement feature properly"}
        raw = "implemented the feature properly in a.py"
        return summary, task, raw

    def test_returns_required_keys(self):
        summary, task, raw = self._passing_inputs()
        result = guard_business_output(summary, task, raw)
        assert "passed" in result
        assert "overall_score" in result
        assert "dimension_scores" in result
        assert "report" in result
        assert "strict_mode" in result

    def test_strict_mode_reflected(self):
        summary, task, raw = self._passing_inputs()
        result = guard_business_output(summary, task, raw, strict_mode=True)
        assert result["strict_mode"] is True

    def test_non_strict_mode_default(self):
        summary, task, raw = self._passing_inputs()
        result = guard_business_output(summary, task, raw)
        assert result["strict_mode"] is False

    def test_passing_run_returns_passed_true(self):
        summary, task, raw = self._passing_inputs()
        result = guard_business_output(summary, task, raw)
        assert result["passed"] is True

    def test_failing_run_returns_passed_false(self):
        summary = {"check_result": False, "files_created": [], "files_modified": []}
        task = {"id": "t-fail", "title": "unrelated"}
        result = guard_business_output(summary, task, "nothing done", pass_threshold=0.9)
        assert result["passed"] is False

    def test_dimension_scores_is_list(self):
        summary, task, raw = self._passing_inputs()
        result = guard_business_output(summary, task, raw)
        assert isinstance(result["dimension_scores"], list)
        assert len(result["dimension_scores"]) == 4

    def test_overall_score_in_range(self):
        summary, task, raw = self._passing_inputs()
        result = guard_business_output(summary, task, raw)
        assert 0.0 <= result["overall_score"] <= 1.0
