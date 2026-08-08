"""Tests for M4c.4 repo-health preflight and check-failure classifier.

Behavioural invariants:
- A failing base check halts the loop at startup with stop_reason="repo_unhealthy"
  and a report that names the failing command, exit code, and output excerpt.
- A passing base check dispatches normally (no stop_reason).
- A check that fails on base AND on the task branch is classified environmental;
  it must not burn retry_count, task_attempt_counts, consecutive_failures, or
  the repeated-error guard.
- A check that passes on base and fails on branch is classified a task failure
  and keeps today's handling exactly.
- The completion-evidence gate_blocked event names the uncommitted dirty paths
  when the failure was classified environmental.
- The preflight is skipped entirely when REPO_HEALTH_PREFLIGHT=false.
- A check.sh timeout is handled and does not wedge startup.

All subprocess and git calls are mocked — no real npm or network in tests.
"""
import os
import sys
import subprocess
import types

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.repo_health_preflight import (
    run_repo_health_check,
    classify_check_failure,
    get_dirty_paths,
    format_repo_unhealthy_report,
    _CHECK_SCRIPT,
    _MAX_EXCERPT,
)
from tools.startup_preflight import (
    PASS, FAIL, SKIP,
    check_repo_health,
    make_check,
    summarize_checks,
    run_startup_preflight,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_proc(returncode=0, stdout="", stderr=""):
    """Build a fake subprocess.CompletedProcess."""
    r = types.SimpleNamespace()
    r.returncode = returncode
    r.stdout = stdout
    r.stderr = stderr
    return r


def _make_run_fn(returncode=0, stdout="", stderr=""):
    def run_fn(*args, **kwargs):
        return _make_proc(returncode=returncode, stdout=stdout, stderr=stderr)
    return run_fn


def _make_timeout_fn():
    def run_fn(*args, **kwargs):
        raise subprocess.TimeoutExpired(cmd="bash", timeout=120)
    return run_fn


def _check_exists_patch(monkeypatch_target, exists=True):
    """Return a run_fn that simulates check.sh existing on disk."""
    # Used where we need os.path.isfile to return True for the check script.
    return exists


# ---------------------------------------------------------------------------
# run_repo_health_check
# ---------------------------------------------------------------------------

class TestRunRepoHealthCheck:
    def test_healthy_when_check_passes(self, tmp_path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "check.sh").write_text("#!/bin/bash\nexit 0\n")
        result = run_repo_health_check(
            str(tmp_path),
            timeout=10,
            run_fn=_make_run_fn(returncode=0, stdout="all good"),
        )
        assert result["healthy"] is True
        assert result["timed_out"] is False
        assert result["exit_code"] == 0
        assert result["failed_command"] == ""

    def test_unhealthy_when_check_fails(self, tmp_path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "check.sh").write_text("#!/bin/bash\nexit 1\n")
        result = run_repo_health_check(
            str(tmp_path),
            timeout=10,
            run_fn=_make_run_fn(returncode=1, stdout="npm ci failed"),
        )
        assert result["healthy"] is False
        assert result["timed_out"] is False
        assert result["exit_code"] == 1
        assert result["failed_command"] == _CHECK_SCRIPT
        assert "npm ci failed" in result["output_excerpt"]

    def test_timeout_handled(self, tmp_path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "check.sh").write_text("#!/bin/bash\nsleep 999\n")
        result = run_repo_health_check(
            str(tmp_path),
            timeout=1,
            run_fn=_make_timeout_fn(),
        )
        assert result["healthy"] is False
        assert result["timed_out"] is True
        assert result["exit_code"] is None
        assert "timed out" in result["output_excerpt"]

    def test_healthy_when_no_check_script(self, tmp_path):
        """A repo without scripts/check.sh (foreign repo) is treated as healthy."""
        result = run_repo_health_check(str(tmp_path), timeout=10)
        assert result["healthy"] is True
        assert "skipped" in result["output_excerpt"]

    def test_output_excerpt_capped(self, tmp_path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "check.sh").write_text("#!/bin/bash\nexit 1\n")
        long_output = "x" * 2000
        result = run_repo_health_check(
            str(tmp_path),
            timeout=10,
            run_fn=_make_run_fn(returncode=1, stdout=long_output),
        )
        assert len(result["output_excerpt"]) <= _MAX_EXCERPT


# ---------------------------------------------------------------------------
# classify_check_failure
# ---------------------------------------------------------------------------

class TestClassifyCheckFailure:
    def _make_git_fn(self, *, stash_has_changes=True, stash_rc=0, pop_rc=0):
        """Simulate git stash and git stash pop."""
        calls = []
        def git_fn(args, *a, **kw):
            calls.append(args)
            if args[:3] == ["git", "stash", "--include-untracked"]:
                stdout = "Saved working directory" if stash_has_changes else "No local changes to save"
                return _make_proc(returncode=stash_rc, stdout=stdout)
            if args[:3] == ["git", "stash", "pop"]:
                return _make_proc(returncode=pop_rc)
            return _make_proc()
        git_fn.calls = calls
        return git_fn

    def test_environmental_when_base_also_fails(self, tmp_path):
        """check fails on branch AND on base → environmental."""
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "check.sh").write_text("")
        result = classify_check_failure(
            str(tmp_path),
            timeout=10,
            git_fn=self._make_git_fn(stash_has_changes=False),
            run_fn=_make_run_fn(returncode=1, stdout="npm ci failed"),
        )
        assert result["environmental"] is True
        assert result["base_passed"] is False

    def test_task_failure_when_base_passes(self, tmp_path):
        """check fails on branch but passes on base → task failure."""
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "check.sh").write_text("")
        result = classify_check_failure(
            str(tmp_path),
            timeout=10,
            git_fn=self._make_git_fn(stash_has_changes=True),
            run_fn=_make_run_fn(returncode=0, stdout="all good"),
        )
        assert result["environmental"] is False
        assert result["base_passed"] is True

    def test_stash_restored_after_base_check(self, tmp_path):
        """Stash is always popped even when the base check fails."""
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "check.sh").write_text("")
        git_calls = []
        def git_fn(args, *a, **kw):
            git_calls.append(list(args))
            if args[:3] == ["git", "stash", "--include-untracked"]:
                return _make_proc(returncode=0, stdout="Saved working directory")
            if args[:3] == ["git", "stash", "pop"]:
                return _make_proc(returncode=0)
            return _make_proc()

        classify_check_failure(
            str(tmp_path),
            timeout=10,
            git_fn=git_fn,
            run_fn=_make_run_fn(returncode=1),
        )
        pop_calls = [c for c in git_calls if c[:3] == ["git", "stash", "pop"]]
        assert len(pop_calls) == 1, "stash pop must be called exactly once"

    def test_not_environmental_when_base_check_times_out(self, tmp_path):
        """If the base check times out we cannot confirm environmental → False."""
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "check.sh").write_text("")
        result = classify_check_failure(
            str(tmp_path),
            timeout=1,
            git_fn=self._make_git_fn(stash_has_changes=False),
            run_fn=_make_timeout_fn(),
        )
        assert result["environmental"] is False
        assert result["base_passed"] is None

    def test_no_check_script_returns_not_environmental(self, tmp_path):
        """No scripts/check.sh → not environmental (foreign repo)."""
        result = classify_check_failure(str(tmp_path), timeout=10)
        assert result["environmental"] is False
        assert result["base_passed"] is None


# ---------------------------------------------------------------------------
# get_dirty_paths
# ---------------------------------------------------------------------------

class TestGetDirtyPaths:
    def test_returns_paths_from_git_status(self, tmp_path):
        def git_fn(args, *a, **kw):
            return _make_proc(returncode=0, stdout="M  src/foo.py\nA  src/bar.py\n")
        paths = get_dirty_paths(str(tmp_path), git_fn=git_fn)
        assert "src/foo.py" in paths
        assert "src/bar.py" in paths

    def test_empty_on_clean_tree(self, tmp_path):
        def git_fn(args, *a, **kw):
            return _make_proc(returncode=0, stdout="")
        assert get_dirty_paths(str(tmp_path), git_fn=git_fn) == []

    def test_empty_on_git_error(self, tmp_path):
        def git_fn(args, *a, **kw):
            return _make_proc(returncode=128, stdout="", stderr="fatal: not a git repo")
        assert get_dirty_paths(str(tmp_path), git_fn=git_fn) == []


# ---------------------------------------------------------------------------
# format_repo_unhealthy_report
# ---------------------------------------------------------------------------

class TestFormatRepoUnhealthyReport:
    def test_includes_command_and_exit_code(self):
        report = format_repo_unhealthy_report({
            "failed_command": "scripts/check.sh",
            "exit_code": 1,
            "timed_out": False,
            "output_excerpt": "npm ci failed",
        })
        assert "scripts/check.sh" in report
        assert "1" in report
        assert "npm ci failed" in report
        assert "PRE-EXISTING" in report

    def test_timeout_case_says_timed_out(self):
        report = format_repo_unhealthy_report({
            "failed_command": "scripts/check.sh",
            "exit_code": None,
            "timed_out": True,
            "output_excerpt": "[timed out after 120s]",
        })
        assert "timed out" in report.lower()
        assert "PRE-EXISTING" in report

    def test_diagnosis_sentence_present(self):
        report = format_repo_unhealthy_report({
            "failed_command": "scripts/check.sh",
            "exit_code": 2,
            "timed_out": False,
            "output_excerpt": "",
        })
        assert "No task can complete" in report


# ---------------------------------------------------------------------------
# check_repo_health (startup_preflight integration)
# ---------------------------------------------------------------------------

class TestCheckRepoHealth:
    def test_skip_when_disabled(self):
        check = check_repo_health("/repo", enabled=False)
        assert check["status"] == SKIP
        assert check["halting"] is False

    def test_pass_when_check_succeeds(self, tmp_path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "check.sh").write_text("")
        check = check_repo_health(
            str(tmp_path),
            enabled=True,
            timeout=10,
            run_fn=_make_run_fn(returncode=0),
        )
        assert check["status"] == PASS
        assert check["halting"] is False

    def test_fail_and_halting_when_check_fails(self, tmp_path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "check.sh").write_text("")
        check = check_repo_health(
            str(tmp_path),
            enabled=True,
            timeout=10,
            run_fn=_make_run_fn(returncode=1, stdout="npm ci failed"),
        )
        assert check["status"] == FAIL
        assert check["halting"] is True, "repo_health failure must halt the loop"
        assert check["data"]["exit_code"] == 1

    def test_fail_and_halting_on_timeout(self, tmp_path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "check.sh").write_text("")
        check = check_repo_health(
            str(tmp_path),
            enabled=True,
            timeout=1,
            run_fn=_make_timeout_fn(),
        )
        assert check["status"] == FAIL
        assert check["halting"] is True
        assert check["data"]["timed_out"] is True


# ---------------------------------------------------------------------------
# run_startup_preflight: repo_health included in probes
# ---------------------------------------------------------------------------

class TestStartupPreflightRepoHealth:
    def _cfg(self, repo_path, enabled=True, timeout=10):
        cfg = types.SimpleNamespace(
            repo_path=str(repo_path),
            has_database=False,
            vercel_project_id=None,
            has_vercel=False,
            github_repo=None,
            has_github=False,
            repo_health_preflight_enabled=enabled,
            repo_health_preflight_timeout_s=timeout,
            preflight_required_tables=(),
        )
        cfg.report = lambda: {
            "anthropic": True,
            "claude_auth_mode": "api_key",
            "github": False,
            "merge_via_pr": False,
            "auto_apply_sql": False,
            "auto_apply_migrations": False,
            "auto_deploy": False,
            "slack_notify": False,
            "slack_interactive_approvals": False,
            "supabase": False,
            "database": False,
            "vercel": False,
        }
        return cfg

    def test_preflight_passes_when_check_passes(self, tmp_path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "check.sh").write_text("")
        cfg = self._cfg(tmp_path)
        # Patch os.path.isfile via probes injection for both git_state and repo_health
        probes = [
            lambda: {"name": "git_state", "status": PASS, "detail": "ok", "halting": False, "data": {}},
            lambda: check_repo_health(str(tmp_path), enabled=True, timeout=10,
                                      run_fn=_make_run_fn(returncode=0)),
        ]
        from tools.startup_preflight import run_startup_preflight
        summary = run_startup_preflight(cfg, probes=probes)
        repo_check = next(c for c in summary["checks"] if c["name"] == "repo_health")
        assert repo_check["status"] == PASS
        assert not summary["unsafe"]

    def test_preflight_unsafe_when_check_fails(self, tmp_path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "check.sh").write_text("")
        cfg = self._cfg(tmp_path)
        probes = [
            lambda: {"name": "git_state", "status": PASS, "detail": "ok", "halting": False, "data": {}},
            lambda: check_repo_health(str(tmp_path), enabled=True, timeout=10,
                                      run_fn=_make_run_fn(returncode=1, stdout="npm ci failed")),
        ]
        from tools.startup_preflight import run_startup_preflight
        summary = run_startup_preflight(cfg, probes=probes)
        repo_check = next(c for c in summary["checks"] if c["name"] == "repo_health")
        assert repo_check["status"] == FAIL
        assert repo_check["halting"] is True
        assert summary["unsafe"] is True
        assert "repo_health" in summary["unsafe_checks"]

    def test_preflight_skipped_when_disabled(self, tmp_path):
        cfg = self._cfg(tmp_path, enabled=False)
        probes = [
            lambda: {"name": "git_state", "status": PASS, "detail": "ok", "halting": False, "data": {}},
            lambda: check_repo_health(str(tmp_path), enabled=False),
        ]
        from tools.startup_preflight import run_startup_preflight
        summary = run_startup_preflight(cfg, probes=probes)
        repo_check = next((c for c in summary["checks"] if c["name"] == "repo_health"), None)
        assert repo_check is not None
        assert repo_check["status"] == SKIP
        assert not summary["unsafe"]


# ---------------------------------------------------------------------------
# classify_check_failure edge cases
# ---------------------------------------------------------------------------

class TestClassifyCheckFailureEdgeCases:
    def test_had_stash_false_when_nothing_to_stash(self, tmp_path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "check.sh").write_text("")
        def git_fn(args, *a, **kw):
            if args[:3] == ["git", "stash", "--include-untracked"]:
                return _make_proc(returncode=0, stdout="No local changes to save")
            return _make_proc()

        result = classify_check_failure(
            str(tmp_path), timeout=10,
            git_fn=git_fn,
            run_fn=_make_run_fn(returncode=1),
        )
        assert result["had_stash"] is False
        assert result["environmental"] is True  # base check also fails

    def test_stash_not_popped_when_nothing_stashed(self, tmp_path):
        (tmp_path / "scripts").mkdir()
        (tmp_path / "scripts" / "check.sh").write_text("")
        git_calls = []
        def git_fn(args, *a, **kw):
            git_calls.append(list(args))
            if args[:3] == ["git", "stash", "--include-untracked"]:
                return _make_proc(returncode=0, stdout="No local changes to save")
            return _make_proc()

        classify_check_failure(
            str(tmp_path), timeout=10,
            git_fn=git_fn,
            run_fn=_make_run_fn(returncode=1),
        )
        pop_calls = [c for c in git_calls if c[:3] == ["git", "stash", "pop"]]
        assert len(pop_calls) == 0, "no stash pop when nothing was stashed"


if __name__ == "__main__":
    import pytest
    pytest.main([__file__, "-v"])
