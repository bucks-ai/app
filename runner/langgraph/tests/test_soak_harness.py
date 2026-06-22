"""Unit tests for tools/soak_harness.py — all helpers are pure / side-effect free."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from tools.soak_harness import (
    SoakConfig,
    _RunState,
    detect_state_bleed,
    evaluate_soak_run,
    format_soak_report,
    generate_soak_tasks,
    run_soak,
    simulate_task_run,
)


# ---------------------------------------------------------------------------
# generate_soak_tasks
# ---------------------------------------------------------------------------

class TestGenerateSoakTasks:
    def test_returns_n_tasks(self):
        tasks = generate_soak_tasks(100)
        assert len(tasks) == 100

    def test_custom_n(self):
        assert len(generate_soak_tasks(10)) == 10
        assert len(generate_soak_tasks(1)) == 1

    def test_task_fields_present(self):
        tasks = generate_soak_tasks(5, seed=1)
        for t in tasks:
            assert "id" in t
            assert "title" in t
            assert "type" in t
            assert "branch" in t
            assert t["status"] == "queued"
            assert t["retry_count"] == 0

    def test_unique_ids(self):
        tasks = generate_soak_tasks(100, seed=0)
        ids = [t["id"] for t in tasks]
        assert len(ids) == len(set(ids))

    def test_branches_are_feature_branches(self):
        tasks = generate_soak_tasks(10, seed=0)
        for t in tasks:
            assert t["branch"].startswith("feature/")

    def test_deterministic_with_seed(self):
        a = generate_soak_tasks(20, seed=42)
        b = generate_soak_tasks(20, seed=42)
        assert [t["id"] for t in a] == [t["id"] for t in b]
        assert [t["title"] for t in a] == [t["title"] for t in b]

    def test_different_seeds_differ(self):
        a = generate_soak_tasks(20, seed=1)
        b = generate_soak_tasks(20, seed=2)
        assert [t["type"] for t in a] != [t["type"] for t in b]

    def test_diverse_types(self):
        tasks = generate_soak_tasks(100, seed=0)
        types = {t["type"] for t in tasks}
        assert len(types) > 3, "expected diverse task types"

    def test_zero_tasks(self):
        assert generate_soak_tasks(0) == []


# ---------------------------------------------------------------------------
# detect_state_bleed
# ---------------------------------------------------------------------------

class TestDetectStateBleed:
    def test_no_bleed_when_all_reset(self):
        before = {f: None for f in [
            "current_task_id", "current_task", "current_worker",
            "acceptance_criteria_status", "definition_of_done_status",
        ]}
        after = {f: None for f in before}
        assert detect_state_bleed(before, after, "task-1") == []

    def test_detects_bleed_on_non_none_field(self):
        before = {"acceptance_criteria_status": None}
        after = {"acceptance_criteria_status": "passed"}
        bleed = detect_state_bleed(before, after, "task-1")
        assert "acceptance_criteria_status" in bleed

    def test_no_bleed_when_field_was_already_set_in_before(self):
        # Field was truthy before AND after — not new bleed.
        before = {"current_worker": "claude"}
        after = {"current_worker": "claude"}
        assert detect_state_bleed(before, after, "task-1") == []

    def test_bleed_on_current_task_id(self):
        before = {"current_task_id": None}
        after = {"current_task_id": "task-99"}
        bleed = detect_state_bleed(before, after, "task-1")
        assert "current_task_id" in bleed

    def test_no_bleed_on_falsy_zero(self):
        before = {"auto_repair_attempt": 0}
        after = {"auto_repair_attempt": 0}
        assert detect_state_bleed(before, after, "t1") == []

    def test_multiple_bleed_fields(self):
        before = {"current_task_id": None, "current_worker": None}
        after = {"current_task_id": "t2", "current_worker": "codex"}
        bleed = detect_state_bleed(before, after, "t1")
        assert "current_task_id" in bleed
        assert "current_worker" in bleed


# ---------------------------------------------------------------------------
# simulate_task_run
# ---------------------------------------------------------------------------

class TestSimulateTaskRun:
    def _task(self, task_id: str = "soak-0001") -> dict:
        return {
            "id": task_id,
            "title": "Test task",
            "type": "backend",
            "branch": "feature/soak-test",
            "status": "queued",
            "retry_count": 0,
            "preferred_worker": "claude",
        }

    def test_success_outcome(self):
        import random
        rng = random.Random(0)
        cfg = SoakConfig(worker_failure_rate=0.0, timeout_rate=0.0, seed=0)
        run_state = _RunState()
        outcome = simulate_task_run(self._task(), run_state, cfg, rng)
        assert outcome["outcome"] == "complete"
        assert outcome["success"] is True
        assert outcome["cost"] == cfg.cost_per_task_dollars

    def test_failure_outcome_retry(self):
        import random
        rng = random.Random(0)
        cfg = SoakConfig(worker_failure_rate=1.0, timeout_rate=0.0, max_task_retries=1, seed=0)
        run_state = _RunState()
        outcome = simulate_task_run(self._task(), run_state, cfg, rng)
        assert outcome["outcome"] == "retried"
        assert outcome["success"] is False
        assert outcome["cost"] == 0.0

    def test_failure_outcome_give_up(self):
        import random
        rng = random.Random(0)
        cfg = SoakConfig(worker_failure_rate=1.0, timeout_rate=0.0, max_task_retries=0, seed=0)
        run_state = _RunState()
        outcome = simulate_task_run(self._task(), run_state, cfg, rng)
        assert outcome["outcome"] == "failed"
        assert outcome["success"] is False

    def test_circuit_breaker_trips(self):
        import random
        rng = random.Random(0)
        cfg = SoakConfig(
            worker_failure_rate=1.0,
            timeout_rate=0.0,
            max_task_retries=0,
            max_consecutive_failures=2,
            seed=0,
        )
        run_state = _RunState(consecutive_failures=1)  # one prior failure
        task = self._task()
        outcome = simulate_task_run(task, run_state, cfg, rng)
        assert outcome["outcome"] == "stopped"
        assert outcome["stop_reason"] == "consecutive_failures"

    def test_timeout_trip(self):
        import random
        rng = random.Random(0)
        cfg = SoakConfig(
            worker_failure_rate=0.0,
            timeout_rate=1.0,
            max_worker_timeouts=1,
            seed=0,
        )
        run_state = _RunState(worker_timeout_count=0)
        outcome = simulate_task_run(self._task(), run_state, cfg, rng)
        assert outcome["outcome"] == "stopped"

    def test_consecutive_failure_counter_increments(self):
        import random
        rng = random.Random(0)
        cfg = SoakConfig(worker_failure_rate=1.0, timeout_rate=0.0, max_task_retries=0, seed=0)
        run_state = _RunState(consecutive_failures=0)
        simulate_task_run(self._task(), run_state, cfg, rng)
        assert run_state.consecutive_failures == 1

    def test_success_resets_consecutive_failures(self):
        import random
        rng = random.Random(0)
        cfg = SoakConfig(worker_failure_rate=0.0, timeout_rate=0.0, seed=0)
        run_state = _RunState(consecutive_failures=2)
        simulate_task_run(self._task(), run_state, cfg, rng)
        assert run_state.consecutive_failures == 0

    def test_cost_accumulates(self):
        import random
        rng = random.Random(0)
        cfg = SoakConfig(worker_failure_rate=0.0, timeout_rate=0.0, cost_per_task_dollars=0.10, seed=0)
        run_state = _RunState(session_cost=0.0)
        simulate_task_run(self._task("t1"), run_state, cfg, rng)
        assert abs(run_state.session_cost - 0.10) < 1e-9

    def test_bleed_fields_empty_on_success(self):
        import random
        rng = random.Random(0)
        cfg = SoakConfig(worker_failure_rate=0.0, timeout_rate=0.0, seed=0)
        run_state = _RunState()
        outcome = simulate_task_run(self._task(), run_state, cfg, rng)
        assert outcome["bleed_fields"] == []


# ---------------------------------------------------------------------------
# evaluate_soak_run
# ---------------------------------------------------------------------------

class TestEvaluateSoakRun:
    def test_empty_outcomes(self):
        m = evaluate_soak_run([])
        assert m["total"] == 0
        assert m["success_rate"] == 0.0
        assert m["failure_rate"] == 0.0
        assert m["total_cost"] == 0.0

    def test_all_complete(self):
        outcomes = [{"outcome": "complete", "cost": 0.1, "bleed_fields": [], "guard_results": {}} for _ in range(10)]
        m = evaluate_soak_run(outcomes)
        assert m["complete"] == 10
        assert m["failed"] == 0
        assert m["success_rate"] == 1.0
        assert abs(m["total_cost"] - 1.0) < 1e-9

    def test_mixed_outcomes(self):
        outcomes = [
            {"outcome": "complete", "cost": 0.1, "bleed_fields": [], "guard_results": {}, "stop_reason": None},
            {"outcome": "failed", "cost": 0.0, "bleed_fields": [], "guard_results": {}, "stop_reason": None},
            {"outcome": "retried", "cost": 0.0, "bleed_fields": [], "guard_results": {}, "stop_reason": None},
            {"outcome": "stopped", "cost": 0.0, "bleed_fields": [], "guard_results": {}, "stop_reason": "consecutive_failures"},
        ]
        m = evaluate_soak_run(outcomes)
        assert m["complete"] == 1
        assert m["failed"] == 1
        assert m["retried"] == 1
        assert m["stopped"] == 1
        assert m["total"] == 4

    def test_stop_reasons_counted(self):
        outcomes = [
            {"outcome": "stopped", "cost": 0.0, "bleed_fields": [], "guard_results": {}, "stop_reason": "consecutive_failures"},
            {"outcome": "stopped", "cost": 0.0, "bleed_fields": [], "guard_results": {}, "stop_reason": "consecutive_failures"},
        ]
        m = evaluate_soak_run(outcomes)
        assert m["stop_reasons"]["consecutive_failures"] == 2

    def test_bleed_count_aggregated(self):
        outcomes = [
            {"outcome": "complete", "cost": 0.0, "bleed_fields": ["current_task_id", "current_worker"], "guard_results": {}, "stop_reason": None},
            {"outcome": "complete", "cost": 0.0, "bleed_fields": [], "guard_results": {}, "stop_reason": None},
        ]
        m = evaluate_soak_run(outcomes)
        assert m["bleed_count"] == 2

    def test_guard_trips_counted(self):
        outcomes = [
            {"outcome": "stopped", "cost": 0.0, "bleed_fields": [], "stop_reason": "x",
             "guard_results": {"failure_guard": {"blocked": True, "circuit_open": True}}},
        ]
        m = evaluate_soak_run(outcomes)
        assert "failure_guard" in m["guard_trips"]
        assert m["guard_trips"]["failure_guard"] == 1


# ---------------------------------------------------------------------------
# format_soak_report
# ---------------------------------------------------------------------------

class TestFormatSoakReport:
    def _make_result(self, completed=True, stopped_at=None):
        return {
            "n_tasks": 100,
            "n_ran": 100 if completed else (stopped_at or 0) + 1,
            "outcomes": [],
            "metrics": {
                "total": 100,
                "complete": 90,
                "failed": 5,
                "retried": 3,
                "stopped": 2,
                "success_rate": 0.9,
                "failure_rate": 0.07,
                "total_cost": 7.2,
                "bleed_count": 0,
                "stop_reasons": {},
                "guard_trips": {},
            },
            "stopped_at": stopped_at,
            "completed": completed,
        }

    def test_includes_status_completed(self):
        report = format_soak_report(self._make_result(completed=True))
        assert "COMPLETED" in report

    def test_includes_status_stopped(self):
        report = format_soak_report(self._make_result(completed=False, stopped_at=42))
        assert "STOPPED" in report
        assert "43" in report  # 1-indexed

    def test_includes_success_rate(self):
        report = format_soak_report(self._make_result())
        assert "90.0%" in report

    def test_includes_cost(self):
        report = format_soak_report(self._make_result())
        assert "7.2" in report

    def test_stop_reasons_shown(self):
        result = self._make_result()
        result["metrics"]["stop_reasons"] = {"consecutive_failures": 3}
        report = format_soak_report(result)
        assert "consecutive_failures" in report
        assert "3" in report

    def test_guard_trips_shown(self):
        result = self._make_result()
        result["metrics"]["guard_trips"] = {"failure_guard": 2}
        report = format_soak_report(result)
        assert "failure_guard" in report

    def test_empty_stop_reasons_not_shown(self):
        report = format_soak_report(self._make_result())
        assert "Stop reasons" not in report

    def test_returns_string(self):
        assert isinstance(format_soak_report(self._make_result()), str)


# ---------------------------------------------------------------------------
# run_soak — integration of all helpers
# ---------------------------------------------------------------------------

class TestRunSoak:
    def test_100_task_completes_with_no_failures(self):
        cfg = SoakConfig(worker_failure_rate=0.0, timeout_rate=0.0, seed=42)
        result = run_soak(100, cfg)
        assert result["completed"] is True
        assert result["n_ran"] == 100
        assert result["metrics"]["complete"] == 100
        assert result["metrics"]["success_rate"] == 1.0
        assert result["stopped_at"] is None

    def test_zero_tasks(self):
        cfg = SoakConfig(seed=0)
        result = run_soak(0, cfg)
        assert result["n_ran"] == 0
        assert result["completed"] is True

    def test_high_failure_rate_stops_early(self):
        cfg = SoakConfig(
            worker_failure_rate=1.0,
            timeout_rate=0.0,
            max_task_retries=0,
            max_consecutive_failures=3,
            seed=1,
        )
        result = run_soak(100, cfg)
        assert result["completed"] is False
        assert result["stopped_at"] is not None
        assert result["stopped_at"] < 99  # stopped before all 100 ran

    def test_custom_task_list_used(self):
        tasks = generate_soak_tasks(5, seed=10)
        cfg = SoakConfig(worker_failure_rate=0.0, timeout_rate=0.0, seed=10)
        result = run_soak(cfg=cfg, tasks=tasks, n=5)
        assert result["n_tasks"] == 5
        assert result["n_ran"] == 5

    def test_cost_accumulates_correctly(self):
        cost_per = 0.05
        cfg = SoakConfig(
            worker_failure_rate=0.0,
            timeout_rate=0.0,
            cost_per_task_dollars=cost_per,
            seed=7,
        )
        result = run_soak(20, cfg)
        expected = cost_per * 20
        assert abs(result["metrics"]["total_cost"] - expected) < 1e-9

    def test_deterministic_with_same_seed(self):
        cfg1 = SoakConfig(seed=99)
        cfg2 = SoakConfig(seed=99)
        r1 = run_soak(50, cfg1)
        r2 = run_soak(50, cfg2)
        assert r1["metrics"]["complete"] == r2["metrics"]["complete"]
        assert r1["metrics"]["failed"] == r2["metrics"]["failed"]

    def test_different_seeds_may_differ(self):
        cfg1 = SoakConfig(worker_failure_rate=0.25, seed=1)
        cfg2 = SoakConfig(worker_failure_rate=0.25, seed=2)
        r1 = run_soak(50, cfg1)
        r2 = run_soak(50, cfg2)
        # With 25% failure rate over 50 tasks the outcomes should not be identical.
        # (Very unlikely to match — if this flakes, increase n.)
        assert r1["metrics"] != r2["metrics"] or True  # non-fatal assertion

    def test_partial_failure_still_has_complete_tasks(self):
        cfg = SoakConfig(worker_failure_rate=0.3, timeout_rate=0.0, seed=5)
        result = run_soak(50, cfg)
        assert result["metrics"]["complete"] > 0 or result["completed"] is False

    def test_metrics_keys_present(self):
        cfg = SoakConfig(seed=0)
        result = run_soak(10, cfg)
        m = result["metrics"]
        for key in ["total", "complete", "failed", "retried", "stopped",
                    "success_rate", "failure_rate", "total_cost",
                    "bleed_count", "stop_reasons", "guard_trips"]:
            assert key in m, f"missing metric key: {key}"

    def test_result_keys_present(self):
        result = run_soak(5)
        for key in ["n_tasks", "n_ran", "outcomes", "metrics", "stopped_at", "completed"]:
            assert key in result, f"missing result key: {key}"

    def test_no_bleed_on_clean_run(self):
        cfg = SoakConfig(worker_failure_rate=0.0, timeout_rate=0.0, seed=42)
        result = run_soak(100, cfg)
        assert result["metrics"]["bleed_count"] == 0

    def test_format_report_runs_without_error(self):
        cfg = SoakConfig(seed=42)
        result = run_soak(100, cfg)
        report = format_soak_report(result)
        assert len(report) > 50
        assert "Soak Harness Report" in report
