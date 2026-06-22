"""Tests for the soak and dry-run CLI command helpers.

All tests are pure unit tests — they import the command functions directly
and verify their behaviour without spawning subprocesses or touching the graph.
"""
from __future__ import annotations

import importlib
import json
import os
import sys
import types
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).parent.parent))

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_args(**kwargs):
    """Create a simple namespace object mimicking argparse output."""
    ns = types.SimpleNamespace(**kwargs)
    return ns


# ---------------------------------------------------------------------------
# cmd_soak
# ---------------------------------------------------------------------------


class TestCmdSoak:
    def _run_soak(self, **kwargs):
        """Import and call cmd_soak with a fresh module import each time."""
        import main as m
        args = _make_args(tasks=kwargs.get("tasks", 10),
                          seed=kwargs.get("seed", 42),
                          failure_rate=kwargs.get("failure_rate", 0.0),
                          timeout_rate=kwargs.get("timeout_rate", 0.0))
        m.cmd_soak(args)

    def test_soak_clean_run_exits_zero(self, capsys):
        import main as m
        args = _make_args(tasks=10, seed=42, failure_rate=0.0, timeout_rate=0.0)
        # Should not raise or call sys.exit on a clean run.
        m.cmd_soak(args)
        out = capsys.readouterr().out
        assert "COMPLETED" in out
        assert "Soak Harness Report" in out

    def test_soak_prints_task_count(self, capsys):
        import main as m
        args = _make_args(tasks=5, seed=1, failure_rate=0.0, timeout_rate=0.0)
        m.cmd_soak(args)
        out = capsys.readouterr().out
        assert "5" in out

    def test_soak_high_failure_exits_one(self):
        import main as m
        args = _make_args(tasks=20, seed=1, failure_rate=1.0, timeout_rate=0.0)
        with pytest.raises(SystemExit) as exc_info:
            m.cmd_soak(args)
        assert exc_info.value.code == 1

    def test_soak_prints_success_rate(self, capsys):
        import main as m
        args = _make_args(tasks=10, seed=42, failure_rate=0.0, timeout_rate=0.0)
        m.cmd_soak(args)
        out = capsys.readouterr().out
        assert "100.0%" in out

    def test_soak_default_seed_is_none(self, capsys):
        import main as m
        # With default seed=None the run is non-deterministic but must still complete.
        args = _make_args(tasks=5, seed=None, failure_rate=0.0, timeout_rate=0.0)
        m.cmd_soak(args)
        out = capsys.readouterr().out
        assert "Soak Harness Report" in out

    def test_soak_failure_rate_in_output(self, capsys):
        import main as m
        args = _make_args(tasks=10, seed=7, failure_rate=0.5, timeout_rate=0.0)
        try:
            m.cmd_soak(args)
        except SystemExit:
            pass
        out = capsys.readouterr().out
        assert "Soak Harness Report" in out

    def test_soak_100_tasks_no_failure(self, capsys):
        import main as m
        args = _make_args(tasks=100, seed=42, failure_rate=0.0, timeout_rate=0.0)
        m.cmd_soak(args)
        out = capsys.readouterr().out
        assert "COMPLETED" in out
        assert "100.0%" in out


# ---------------------------------------------------------------------------
# generate_soak_tasks shapes used by dry-run seeding
# ---------------------------------------------------------------------------


class TestSoakTaskGeneration:
    """Verify that tasks generated for the dry-run CLI have the right shape."""

    def test_task_has_required_fields(self):
        from tools.soak_harness import generate_soak_tasks
        tasks = generate_soak_tasks(3, seed=0)
        for t in tasks:
            assert "id" in t
            assert "title" in t
            assert "type" in t
            assert "branch" in t
            assert t["status"] == "queued"

    def test_task_ids_are_unique(self):
        from tools.soak_harness import generate_soak_tasks
        tasks = generate_soak_tasks(50, seed=0)
        ids = [t["id"] for t in tasks]
        assert len(ids) == len(set(ids))

    def test_branches_are_feature_branches(self):
        from tools.soak_harness import generate_soak_tasks
        tasks = generate_soak_tasks(10, seed=5)
        for t in tasks:
            assert t["branch"].startswith("feature/")

    def test_deterministic_with_seed(self):
        from tools.soak_harness import generate_soak_tasks
        a = generate_soak_tasks(20, seed=99)
        b = generate_soak_tasks(20, seed=99)
        assert [t["id"] for t in a] == [t["id"] for t in b]


# ---------------------------------------------------------------------------
# Config dry-run flag
# ---------------------------------------------------------------------------


class TestConfigDryRun:
    def test_runner_dry_run_default_false(self):
        import importlib
        import config as cfg_mod
        importlib.reload(cfg_mod)
        cfg = cfg_mod.RunnerConfig()
        assert cfg.runner_dry_run is False

    def test_runner_dry_run_env_true(self, monkeypatch):
        monkeypatch.setenv("RUNNER_DRY_RUN", "true")
        import config as cfg_mod
        importlib.reload(cfg_mod)
        cfg = cfg_mod.RunnerConfig()
        assert cfg.runner_dry_run is True

    def test_runner_dry_run_in_report(self):
        import config as cfg_mod
        importlib.reload(cfg_mod)
        cfg = cfg_mod.RunnerConfig()
        report = cfg.report()
        assert "runner_dry_run" in report

    def test_runner_dry_run_false_in_report(self, monkeypatch):
        monkeypatch.setenv("RUNNER_DRY_RUN", "false")
        import config as cfg_mod
        importlib.reload(cfg_mod)
        cfg = cfg_mod.RunnerConfig()
        assert cfg.report()["runner_dry_run"] is False


# ---------------------------------------------------------------------------
# graph.py dry-run stubs (unit-level, without invoking LangGraph)
# ---------------------------------------------------------------------------


class TestDispatchWorkerDryRun:
    """Verify that dispatch_worker injects a synthetic result in dry-run mode."""

    def _make_state(self):
        from state import RunnerState
        return RunnerState(
            status="running",
            current_task_id="soak-0001",
            current_task={"id": "soak-0001", "title": "Test", "type": "backend", "branch": "feature/soak-0001"},
            current_worker="claude",
            messages=[{"role": "user", "content": "Do the task."}],
        )

    def test_dry_run_returns_synthetic_success(self, monkeypatch):
        monkeypatch.setenv("RUNNER_DRY_RUN", "true")
        import config as cfg_mod
        importlib.reload(cfg_mod)
        cfg_mod._config = cfg_mod.RunnerConfig()  # force fresh singleton

        from state import RunnerState
        from tools.task_tools import mark_task_running
        from tools.log_tools import update_state, log_event

        state = self._make_state()

        # Patch mark_task_running and _persist to avoid filesystem side-effects.
        with patch("graph.mark_task_running"), \
             patch("graph._persist", side_effect=lambda s, _: s), \
             patch("graph.log_event"), \
             patch("graph.cfg", cfg_mod._config):
            import graph as g_mod
            result_state = g_mod.dispatch_worker(state)

        wr = result_state.worker_result
        assert wr is not None
        assert wr["success"] is True
        assert wr["mode"] == "dry_run"
        assert "Files Created" in (wr.get("output") or "")
        assert wr["api_cost"] == 0.0

    def test_dry_run_does_not_instantiate_worker(self, monkeypatch):
        monkeypatch.setenv("RUNNER_DRY_RUN", "true")
        import config as cfg_mod
        importlib.reload(cfg_mod)
        cfg_mod._config = cfg_mod.RunnerConfig()

        state = self._make_state()

        with patch("graph.mark_task_running"), \
             patch("graph._persist", side_effect=lambda s, _: s), \
             patch("graph.log_event"), \
             patch("graph.cfg", cfg_mod._config), \
             patch("graph.ClaudeWorker") as mock_claude, \
             patch("graph.CodexWorker") as mock_codex:
            import graph as g_mod
            g_mod.dispatch_worker(state)
            mock_claude.assert_not_called()
            mock_codex.assert_not_called()


class TestRunChecksIfNeededDryRun:
    def _make_state(self, worker_success=True):
        from state import RunnerState
        return RunnerState(
            status="running",
            current_task_id="soak-0001",
            worker_result={"success": worker_success, "output": "done"},
        )

    def test_dry_run_sets_check_passed_true(self, monkeypatch):
        monkeypatch.setenv("RUNNER_DRY_RUN", "true")
        import config as cfg_mod
        importlib.reload(cfg_mod)
        cfg_mod._config = cfg_mod.RunnerConfig()

        state = self._make_state(worker_success=True)
        with patch("graph._persist", side_effect=lambda s, _: s), \
             patch("graph.log_event"), \
             patch("graph.run_check") as mock_check, \
             patch("graph.cfg", cfg_mod._config):
            import graph as g_mod
            result = g_mod.run_checks_if_needed(state)
            mock_check.assert_not_called()

        assert result.check_passed is True

    def test_dry_run_skip_when_worker_failed(self, monkeypatch):
        monkeypatch.setenv("RUNNER_DRY_RUN", "true")
        import config as cfg_mod
        importlib.reload(cfg_mod)
        cfg_mod._config = cfg_mod.RunnerConfig()

        state = self._make_state(worker_success=False)
        with patch("graph._persist", side_effect=lambda s, _: s), \
             patch("graph.log_event"), \
             patch("graph.run_check") as mock_check, \
             patch("graph.cfg", cfg_mod._config):
            import graph as g_mod
            result = g_mod.run_checks_if_needed(state)
            # Still should not call run_check because worker failed before reaching dry-run branch
            mock_check.assert_not_called()

        # check_passed unchanged (None)
        assert result.check_passed is None


class TestCommitPushMergeIfNeededDryRun:
    def _make_state(self):
        from state import RunnerState
        return RunnerState(
            status="running",
            current_task_id="soak-0001",
            current_task={"id": "soak-0001", "title": "Test", "branch": "feature/soak-0001"},
            worker_result={"success": True},
            check_passed=True,
        )

    def test_dry_run_skips_git_operations(self, monkeypatch):
        monkeypatch.setenv("RUNNER_DRY_RUN", "true")
        import config as cfg_mod
        importlib.reload(cfg_mod)
        cfg_mod._config = cfg_mod.RunnerConfig()

        state = self._make_state()
        with patch("graph._persist", side_effect=lambda s, _: s), \
             patch("graph.log_event"), \
             patch("graph.create_branch") as mock_branch, \
             patch("graph.commit_all") as mock_commit, \
             patch("graph.push_branch") as mock_push, \
             patch("graph.cfg", cfg_mod._config):
            import graph as g_mod
            g_mod.commit_push_merge_if_needed(state)
            mock_branch.assert_not_called()
            mock_commit.assert_not_called()
            mock_push.assert_not_called()

    def test_dry_run_last_commit_stays_none(self, monkeypatch):
        monkeypatch.setenv("RUNNER_DRY_RUN", "true")
        import config as cfg_mod
        importlib.reload(cfg_mod)
        cfg_mod._config = cfg_mod.RunnerConfig()

        state = self._make_state()
        with patch("graph._persist", side_effect=lambda s, _: s), \
             patch("graph.log_event"), \
             patch("graph.create_branch"), \
             patch("graph.cfg", cfg_mod._config):
            import graph as g_mod
            result = g_mod.commit_push_merge_if_needed(state)

        assert result.last_commit is None
