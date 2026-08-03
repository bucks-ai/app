"""Unit tests for tools/live_batch_validation_report.py — all pure helpers."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

import tools.live_batch_validation_report as _mod

# Silence log_event for all tests
_mod.log_event = lambda *a, **k: None


from tools.live_batch_validation_report import (
    collect_batch_metrics,
    compute_elapsed_minutes,
    format_batch_report,
    generate_live_batch_report,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _tasks(*statuses) -> list[dict]:
    return [
        {"id": f"t-{i:03d}", "title": f"Task {i}", "status": s}
        for i, s in enumerate(statuses, 1)
    ]


def _session(**overrides) -> dict:
    base = {
        "stop_reason": "no_more_tasks",
        "loop_count": 5,
        "session_cost": 0.42,
        "started_at": None,
        "consecutive_failures": 0,
        "worker_timeout_count": 0,
    }
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# collect_batch_metrics
# ---------------------------------------------------------------------------

class TestCollectBatchMetrics:
    def test_empty_list(self):
        m = collect_batch_metrics([])
        assert m["total"] == 0
        assert m["complete"] == 0
        assert m["success_rate"] == 0.0
        assert m["failure_rate"] == 0.0

    def test_all_complete(self):
        m = collect_batch_metrics(_tasks("complete", "complete", "complete"))
        assert m["total"] == 3
        assert m["complete"] == 3
        assert m["failed"] == 0
        assert m["success_rate"] == 1.0
        assert m["failure_rate"] == 0.0

    def test_mixed_statuses(self):
        tasks = _tasks("complete", "failed", "blocked", "queued", "running")
        m = collect_batch_metrics(tasks)
        assert m["total"] == 5
        assert m["complete"] == 1
        assert m["failed"] == 1
        assert m["blocked"] == 1
        assert m["queued"] == 1
        assert m["running"] == 1

    def test_success_rate_calculation(self):
        tasks = _tasks("complete", "complete", "failed", "failed")
        m = collect_batch_metrics(tasks)
        assert m["success_rate"] == pytest.approx(0.5)

    def test_failure_rate_includes_blocked(self):
        tasks = _tasks("failed", "blocked", "complete")
        m = collect_batch_metrics(tasks)
        assert m["failure_rate"] == pytest.approx(round(2 / 3, 3))

    def test_rates_rounded_to_three_decimals(self):
        tasks = _tasks(*["complete"] * 1 + ["failed"] * 2)
        m = collect_batch_metrics(tasks)
        # 1/3 = 0.333...; should be 0.333
        assert isinstance(m["success_rate"], float)
        assert len(str(m["success_rate"]).split(".")[-1]) <= 3

    def test_unknown_status_counted_separately(self):
        tasks = [{"id": "t1", "title": "t", "status": "mystery"}]
        m = collect_batch_metrics(tasks)
        assert m["total"] == 1
        assert m.get("mystery", 0) == 1

    def test_required_keys_present(self):
        m = collect_batch_metrics([])
        for key in ["total", "complete", "failed", "blocked", "queued",
                    "running", "success_rate", "failure_rate"]:
            assert key in m, f"missing key: {key}"


# ---------------------------------------------------------------------------
# compute_elapsed_minutes
# ---------------------------------------------------------------------------

class TestComputeElapsedMinutes:
    def test_none_returns_none(self):
        assert compute_elapsed_minutes(None) is None

    def test_empty_string_returns_none(self):
        assert compute_elapsed_minutes("") is None

    def test_valid_iso_timestamp_returns_positive_float(self):
        # Use a timestamp well in the past
        past = "2020-01-01T00:00:00"
        result = compute_elapsed_minutes(past)
        assert result is not None
        assert result > 0.0

    def test_invalid_timestamp_returns_none(self):
        assert compute_elapsed_minutes("not-a-date") is None

    def test_result_is_rounded(self):
        past = "2020-01-01T00:00:00"
        result = compute_elapsed_minutes(past)
        assert result == round(result, 1)


# ---------------------------------------------------------------------------
# format_batch_report
# ---------------------------------------------------------------------------

class TestFormatBatchReport:
    def _metrics(self, **overrides) -> dict:
        base = {
            "total": 10,
            "complete": 8,
            "failed": 1,
            "blocked": 0,
            "queued": 1,
            "running": 0,
            "success_rate": 0.8,
            "failure_rate": 0.1,
        }
        base.update(overrides)
        return base

    def test_returns_string(self):
        report = format_batch_report(self._metrics(), _session(), [])
        assert isinstance(report, str)

    def test_contains_report_header(self):
        report = format_batch_report(self._metrics(), _session(), [])
        assert "Live-Batch Validation Report" in report

    def test_contains_stop_reason(self):
        report = format_batch_report(self._metrics(), _session(stop_reason="max_loop_tasks"), [])
        assert "max_loop_tasks" in report

    def test_contains_loop_count(self):
        report = format_batch_report(self._metrics(), _session(loop_count=7), [])
        assert "7" in report

    def test_contains_session_cost(self):
        report = format_batch_report(self._metrics(), _session(session_cost=1.2345), [])
        assert "1.2345" in report

    def test_contains_success_pct(self):
        report = format_batch_report(self._metrics(success_rate=0.8), _session(), [])
        assert "80.0%" in report

    def test_contains_task_counts(self):
        m = self._metrics(complete=5, failed=2, blocked=1, queued=2)
        report = format_batch_report(m, _session(), [])
        assert "Complete:" in report or "Complete" in report
        assert "5" in report

    def test_per_task_lines_included(self):
        tasks = _tasks("complete", "failed", "queued")
        report = format_batch_report(self._metrics(), _session(), tasks)
        assert "t-001" in report
        assert "t-002" in report

    def test_per_task_capped_at_50(self):
        tasks = _tasks(*["complete"] * 60)
        report = format_batch_report(self._metrics(), _session(), tasks)
        assert "10 more task" in report

    def test_no_task_section_when_empty(self):
        report = format_batch_report(self._metrics(), _session(), [])
        assert "Per-Task Summary" not in report

    def test_elapsed_shown_when_started_at_present(self):
        session = _session(started_at="2020-01-01T00:00:00")
        report = format_batch_report(self._metrics(), session, [])
        assert "min" in report

    def test_elapsed_unknown_when_no_started_at(self):
        report = format_batch_report(self._metrics(), _session(started_at=None), [])
        assert "unknown" in report

    def test_worker_timeouts_shown(self):
        report = format_batch_report(self._metrics(), _session(worker_timeout_count=3), [])
        assert "3" in report

    def test_status_icons_in_task_lines(self):
        tasks = [
            {"id": "t1", "title": "A", "status": "complete"},
            {"id": "t2", "title": "B", "status": "failed"},
            {"id": "t3", "title": "C", "status": "blocked"},
        ]
        report = format_batch_report(self._metrics(), _session(), tasks)
        assert "[+]" in report
        assert "[x]" in report
        assert "[!]" in report


# ---------------------------------------------------------------------------
# generate_live_batch_report
# ---------------------------------------------------------------------------

class TestGenerateLiveBatchReport:
    def _mock_tasks(self, monkeypatch, tasks):
        monkeypatch.setattr(_mod, "load_tasks", lambda: tasks)

    def test_returns_required_keys(self, monkeypatch):
        self._mock_tasks(monkeypatch, _tasks("complete", "complete", "failed"))
        result = generate_live_batch_report(_session())
        for key in ["report", "metrics", "passed", "stop_reason"]:
            assert key in result, f"missing key: {key}"

    def test_report_is_string(self, monkeypatch):
        self._mock_tasks(monkeypatch, _tasks("complete"))
        result = generate_live_batch_report(_session())
        assert isinstance(result["report"], str)

    def test_passed_true_when_majority_complete(self, monkeypatch):
        tasks = _tasks(*["complete"] * 6 + ["failed"] * 4)
        self._mock_tasks(monkeypatch, tasks)
        result = generate_live_batch_report(_session())
        assert result["passed"] is True

    def test_passed_false_when_few_complete(self, monkeypatch):
        tasks = _tasks(*["failed"] * 4 + ["complete"] * 1)
        self._mock_tasks(monkeypatch, tasks)
        result = generate_live_batch_report(_session())
        assert result["passed"] is False

    def test_stop_reason_from_session(self, monkeypatch):
        self._mock_tasks(monkeypatch, [])
        result = generate_live_batch_report(_session(stop_reason="max_runtime"))
        assert result["stop_reason"] == "max_runtime"

    def test_metrics_match_task_list(self, monkeypatch):
        tasks = _tasks("complete", "complete", "failed")
        self._mock_tasks(monkeypatch, tasks)
        result = generate_live_batch_report(_session())
        assert result["metrics"]["total"] == 3
        assert result["metrics"]["complete"] == 2
        assert result["metrics"]["failed"] == 1

    def test_empty_task_list(self, monkeypatch):
        self._mock_tasks(monkeypatch, [])
        result = generate_live_batch_report(_session())
        assert result["metrics"]["total"] == 0
        assert result["passed"] is False  # 0 / 0 → 0.0 < 0.5

    def test_context_accepted(self, monkeypatch):
        self._mock_tasks(monkeypatch, [])
        result = generate_live_batch_report(_session(), context="test_ctx")
        assert "report" in result

    def test_stop_reason_none_becomes_none_string(self, monkeypatch):
        self._mock_tasks(monkeypatch, [])
        result = generate_live_batch_report(_session(stop_reason=None))
        assert result["stop_reason"] == "none"


# ---------------------------------------------------------------------------
# Config / State / Graph integration
# ---------------------------------------------------------------------------

class TestConfigAndStateIntegration:
    def test_config_has_report_enabled_flag(self):
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert hasattr(cfg, "live_batch_validation_report_enabled")
        assert cfg.live_batch_validation_report_enabled is True

    def test_state_has_live_batch_validation_result(self):
        from state import RunnerState
        s = RunnerState()
        assert hasattr(s, "live_batch_validation_result")
        assert s.live_batch_validation_result is None

    def test_graph_has_node(self):
        import graph as g
        assert hasattr(g, "generate_live_batch_validation_report")
