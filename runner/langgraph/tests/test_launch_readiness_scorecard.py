"""Unit tests for tools/launch_readiness_scorecard.py — pure helpers only."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.launch_readiness_scorecard import (
    _score_config_completeness,
    _score_credentials_available,
    _score_safety_gates_active,
    _score_operational_health,
    score_launch_readiness_dimensions,
    evaluate_launch_readiness,
    format_scorecard_report,
    run_launch_readiness_scorecard,
    guard_launch_readiness,
    _PASS_THRESHOLD_DEFAULT,
)

import tools.launch_readiness_scorecard as _lrs
_lrs.log_event = lambda *a, **k: None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _full_config(**overrides) -> dict:
    """A fully-populated config snapshot that should yield a high score."""
    base = {
        "repo_path": "/home/user/bucks-ai",
        "max_loop_tasks": 10,
        "max_runtime_minutes": 480,
        "max_consecutive_failures": 3,
        "max_task_retries": 1,
        "openai": True,
        "anthropic": True,
        "github": True,
        "supabase": True,
        "vercel": True,
        "failure_guard_enabled": True,
        "resource_gate_enabled": True,
        "acceptance_criteria_gate_enabled": True,
        "independent_code_review_enabled": True,
        "auto_repair_loop_enabled": True,
        "risk_based_merge_approval_enabled": True,
    }
    base.update(overrides)
    return base


def _healthy_state(**overrides) -> dict:
    base = {
        "stop_reason": None,
        "consecutive_failures": 0,
        "worker_timeout_count": 0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# _score_config_completeness
# ---------------------------------------------------------------------------

class TestScoreConfigCompleteness:
    def test_full_config_scores_max(self):
        score, rationale = _score_config_completeness(_full_config())
        assert score == 1.0
        assert "all critical" in rationale

    def test_missing_repo_path_penalises(self):
        score, rationale = _score_config_completeness(_full_config(repo_path=""))
        assert score < 1.0
        assert "BUCKS_AI_REPO_PATH" in rationale

    def test_zero_max_loop_tasks_penalises(self):
        score, rationale = _score_config_completeness(_full_config(max_loop_tasks=0))
        assert score < 1.0
        assert "MAX_LOOP_TASKS" in rationale

    def test_zero_max_runtime_penalises(self):
        score, rationale = _score_config_completeness(_full_config(max_runtime_minutes=0))
        assert score < 1.0
        assert "MAX_RUNTIME_MINUTES" in rationale

    def test_zero_max_consecutive_failures_penalises(self):
        score, rationale = _score_config_completeness(_full_config(max_consecutive_failures=0))
        assert score < 1.0
        assert "MAX_CONSECUTIVE_FAILURES" in rationale

    def test_score_is_non_negative(self):
        cfg = _full_config(repo_path="", max_loop_tasks=0, max_runtime_minutes=0,
                           max_consecutive_failures=0)
        score, _ = _score_config_completeness(cfg)
        assert score >= 0.0


# ---------------------------------------------------------------------------
# _score_credentials_available
# ---------------------------------------------------------------------------

class TestScoreCredentialsAvailable:
    def test_all_credentials_scores_full(self):
        score, rationale = _score_credentials_available(_full_config())
        assert score == 1.0
        assert "all 5" in rationale

    def test_no_credentials_scores_zero(self):
        cfg = _full_config(openai=False, anthropic=False, github=False, supabase=False, vercel=False)
        score, rationale = _score_credentials_available(cfg)
        assert score == 0.0
        assert "missing" in rationale

    def test_partial_credentials_score_proportional(self):
        cfg = _full_config(openai=True, anthropic=True, github=False, supabase=False, vercel=False)
        score, rationale = _score_credentials_available(cfg)
        assert score == pytest.approx(2 / 5)
        assert "2/5" in rationale

    def test_missing_names_listed_in_rationale(self):
        cfg = _full_config(github=False, vercel=False)
        _, rationale = _score_credentials_available(cfg)
        assert "GitHub" in rationale
        assert "Vercel" in rationale


# ---------------------------------------------------------------------------
# _score_safety_gates_active
# ---------------------------------------------------------------------------

class TestScoreSafetyGatesActive:
    def test_all_gates_enabled_scores_full(self):
        score, rationale = _score_safety_gates_active(_full_config())
        assert score == 1.0
        assert "all safety gates active" in rationale

    def test_critical_gate_disabled_penalises_heavily(self):
        cfg = _full_config(failure_guard_enabled=False)
        score, rationale = _score_safety_gates_active(cfg)
        assert score <= 0.75
        assert "CRITICAL" in rationale
        assert "failure_guard" in rationale

    def test_all_critical_gates_off_low_score(self):
        cfg = _full_config(
            failure_guard_enabled=False,
            resource_gate_enabled=False,
            acceptance_criteria_gate_enabled=False,
        )
        score, _ = _score_safety_gates_active(cfg)
        assert score <= 0.25

    def test_optional_gate_disabled_minor_penalty(self):
        cfg = _full_config(auto_repair_loop_enabled=False)
        score, rationale = _score_safety_gates_active(cfg)
        assert 0.9 <= score < 1.0
        assert "optional" in rationale

    def test_score_non_negative(self):
        cfg = _full_config(
            failure_guard_enabled=False,
            resource_gate_enabled=False,
            acceptance_criteria_gate_enabled=False,
            independent_code_review_enabled=False,
            auto_repair_loop_enabled=False,
            risk_based_merge_approval_enabled=False,
        )
        score, _ = _score_safety_gates_active(cfg)
        assert score >= 0.0


# ---------------------------------------------------------------------------
# _score_operational_health
# ---------------------------------------------------------------------------

class TestScoreOperationalHealth:
    def test_healthy_state_scores_full(self):
        score, rationale = _score_operational_health(_healthy_state())
        assert score == 1.0
        assert "healthy" in rationale

    def test_empty_state_returns_default_first_launch(self):
        score, rationale = _score_operational_health({})
        assert score == 0.8
        assert "first launch" in rationale

    def test_active_stop_reason_penalises(self):
        score, rationale = _score_operational_health(_healthy_state(stop_reason="deploy_failed"))
        assert score < 1.0
        assert "stop_reason" in rationale

    def test_two_consecutive_failures_penalises(self):
        score, rationale = _score_operational_health(_healthy_state(consecutive_failures=2))
        assert score <= 0.8
        assert "consecutive failures" in rationale

    def test_one_consecutive_failure_minor_penalty(self):
        score_one, _ = _score_operational_health(_healthy_state(consecutive_failures=1))
        score_two, _ = _score_operational_health(_healthy_state(consecutive_failures=2))
        assert score_one > score_two

    def test_many_worker_timeouts_penalises(self):
        score, rationale = _score_operational_health(_healthy_state(worker_timeout_count=3))
        assert score < 1.0
        assert "timeout" in rationale

    def test_score_non_negative(self):
        state = _healthy_state(stop_reason="x", consecutive_failures=5, worker_timeout_count=10)
        score, _ = _score_operational_health(state)
        assert score >= 0.0


# ---------------------------------------------------------------------------
# score_launch_readiness_dimensions
# ---------------------------------------------------------------------------

class TestScoreLaunchReadinessDimensions:
    def test_returns_four_dimensions(self):
        dims = score_launch_readiness_dimensions(_full_config(), _healthy_state())
        assert len(dims) == 4

    def test_dimension_names(self):
        dims = score_launch_readiness_dimensions(_full_config(), _healthy_state())
        names = [d["name"] for d in dims]
        assert "config_completeness" in names
        assert "credentials_available" in names
        assert "safety_gates_active" in names
        assert "operational_health" in names

    def test_weights_sum_to_one(self):
        dims = score_launch_readiness_dimensions(_full_config(), _healthy_state())
        total_weight = sum(d["weight"] for d in dims)
        assert abs(total_weight - 1.0) < 1e-6

    def test_each_dim_has_required_keys(self):
        dims = score_launch_readiness_dimensions(_full_config(), _healthy_state())
        for d in dims:
            assert "name" in d
            assert "weight" in d
            assert "score" in d
            assert "rationale" in d


# ---------------------------------------------------------------------------
# evaluate_launch_readiness
# ---------------------------------------------------------------------------

class TestEvaluateLaunchReadiness:
    def test_empty_dims_returns_full_pass(self):
        result = evaluate_launch_readiness([], pass_threshold=0.7)
        assert result["passed"] is True
        assert result["overall_score"] == 1.0

    def test_high_scoring_dims_pass(self):
        dims = [{"name": "x", "weight": 1.0, "score": 1.0, "rationale": ""}]
        result = evaluate_launch_readiness(dims, pass_threshold=0.7)
        assert result["passed"] is True

    def test_low_scoring_dims_fail(self):
        dims = [{"name": "x", "weight": 1.0, "score": 0.3, "rationale": ""}]
        result = evaluate_launch_readiness(dims, pass_threshold=0.7)
        assert result["passed"] is False

    def test_weighted_average_computed_correctly(self):
        dims = [
            {"name": "a", "weight": 0.5, "score": 1.0, "rationale": ""},
            {"name": "b", "weight": 0.5, "score": 0.0, "rationale": ""},
        ]
        result = evaluate_launch_readiness(dims, pass_threshold=0.5)
        assert result["overall_score"] == pytest.approx(0.5)

    def test_pass_threshold_echoed(self):
        result = evaluate_launch_readiness([], pass_threshold=0.8)
        assert result["pass_threshold"] == 0.8


# ---------------------------------------------------------------------------
# format_scorecard_report
# ---------------------------------------------------------------------------

class TestFormatScorecardReport:
    def _eval(self, passed: bool, score: float) -> dict:
        return {
            "overall_score": score,
            "passed": passed,
            "pass_threshold": 0.7,
            "dimension_scores": [
                {"name": "config_completeness", "weight": 0.25, "score": score, "rationale": "ok"},
            ],
        }

    def test_contains_ready_when_passed(self):
        report = format_scorecard_report(self._eval(True, 0.9))
        assert "READY" in report

    def test_contains_not_ready_when_failed(self):
        report = format_scorecard_report(self._eval(False, 0.4))
        assert "NOT READY" in report

    def test_contains_score(self):
        report = format_scorecard_report(self._eval(True, 0.85))
        assert "0.85" in report

    def test_contains_dimension_name(self):
        report = format_scorecard_report(self._eval(True, 0.9))
        assert "config_completeness" in report


# ---------------------------------------------------------------------------
# run_launch_readiness_scorecard
# ---------------------------------------------------------------------------

class TestRunLaunchReadinessScorecard:
    def test_full_run_passes_with_good_config(self):
        result = run_launch_readiness_scorecard(_full_config(), _healthy_state(), 0.7)
        assert result["passed"] is True
        assert "report" in result
        assert "dimension_scores" in result

    def test_report_is_string(self):
        result = run_launch_readiness_scorecard(_full_config(), _healthy_state())
        assert isinstance(result["report"], str)


# ---------------------------------------------------------------------------
# guard_launch_readiness
# ---------------------------------------------------------------------------

class TestGuardLaunchReadiness:
    def test_passed_returns_passed_true(self):
        result = guard_launch_readiness(_full_config(), _healthy_state(), 0.7, strict_mode=False)
        assert result["passed"] is True

    def test_non_strict_returns_passed_false_without_raising(self):
        bad_cfg = _full_config(
            repo_path="",
            openai=False,
            anthropic=False,
            github=False,
            supabase=False,
            vercel=False,
            failure_guard_enabled=False,
            resource_gate_enabled=False,
            acceptance_criteria_gate_enabled=False,
        )
        result = guard_launch_readiness(bad_cfg, {}, 0.9, strict_mode=False)
        assert result["passed"] is False

    def test_strict_mode_echoed_in_result(self):
        result = guard_launch_readiness(_full_config(), _healthy_state(), strict_mode=True)
        assert result["strict_mode"] is True

    def test_non_strict_mode_echoed_in_result(self):
        result = guard_launch_readiness(_full_config(), _healthy_state(), strict_mode=False)
        assert result["strict_mode"] is False

    def test_result_contains_report(self):
        result = guard_launch_readiness(_full_config(), _healthy_state())
        assert "report" in result
        assert isinstance(result["report"], str)

    def test_result_contains_dimension_scores(self):
        result = guard_launch_readiness(_full_config(), _healthy_state())
        assert "dimension_scores" in result
        assert len(result["dimension_scores"]) == 4


# ---------------------------------------------------------------------------
# Config and State field presence
# ---------------------------------------------------------------------------

class TestConfigAndStateFields:
    def test_config_has_launch_readiness_fields(self):
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert hasattr(cfg, "launch_readiness_scorecard_enabled")
        assert hasattr(cfg, "launch_readiness_scorecard_strict_mode")
        assert hasattr(cfg, "launch_readiness_scorecard_pass_threshold")
        assert cfg.launch_readiness_scorecard_enabled is True
        assert cfg.launch_readiness_scorecard_strict_mode is False
        assert cfg.launch_readiness_scorecard_pass_threshold == pytest.approx(0.7)

    def test_state_has_launch_readiness_result(self):
        from state import RunnerState
        s = RunnerState()
        assert hasattr(s, "launch_readiness_result")
        assert s.launch_readiness_result is None

    def test_graph_has_node(self):
        import graph as g
        assert hasattr(g, "check_launch_readiness_if_needed")


# ---------------------------------------------------------------------------
# Default threshold constant
# ---------------------------------------------------------------------------

def test_default_pass_threshold():
    assert _PASS_THRESHOLD_DEFAULT == 0.7


import pytest
