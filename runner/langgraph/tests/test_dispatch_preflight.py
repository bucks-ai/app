"""Unit tests for M4c dispatch preflight.

Runs standalone (no pytest dependency):

    python tests/test_dispatch_preflight.py

Covers the four fixes that unblock unattended business execution:
  - The Claude worker dispatches the prompt as the *instruction* (stdin), not
    as an ``@file`` argument, with cwd set to the task's repo_path.
  - A business task's workspace origin must match its repo_full_name; a
    mismatch aborts the task instead of committing to the wrong repo.
  - The loop refuses to start from a non-main branch or a dirty tree.
  - Credentialed remote URLs never leak out of the preflight helpers.
"""
import os
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.dispatch_preflight import (
    parse_repo_full_name,
    verify_origin_remote,
    check_loop_start_preconditions,
    evaluate_loop_start,
)
import graph
from state import RunnerState

graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None

_TOKEN = "ghs_supersecrettokenvalue"


# ---------------------------------------------------------------------------
# parse_repo_full_name
# ---------------------------------------------------------------------------

def test_parses_https_url():
    assert parse_repo_full_name("https://github.com/acme/widgets.git") == "acme/widgets"


def test_parses_https_url_without_git_suffix():
    assert parse_repo_full_name("https://github.com/acme/widgets") == "acme/widgets"


def test_parses_ssh_scp_style_url():
    assert parse_repo_full_name("git@github.com:acme/widgets.git") == "acme/widgets"


def test_parses_credentialed_clone_url_and_drops_token():
    url = f"https://x-access-token:{_TOKEN}@github.com/acme/widgets.git"
    result = parse_repo_full_name(url)
    assert result == "acme/widgets"
    assert _TOKEN not in result


def test_parse_is_case_insensitive():
    assert parse_repo_full_name("https://github.com/ACME/Widgets.git") == "acme/widgets"


def test_parse_returns_empty_for_junk():
    for junk in ("", "   ", "not-a-url", "https://github.com/onlyowner"):
        assert parse_repo_full_name(junk) == "", junk


# ---------------------------------------------------------------------------
# verify_origin_remote
# ---------------------------------------------------------------------------

def _stub_remote(url, success=True, error=""):
    return lambda repo_path: {"success": success, "url": url, "error": error}


def test_verify_passes_on_matching_remote():
    out = verify_origin_remote(
        "/ws/biz", "acme/widgets",
        git_remote_url=_stub_remote("https://github.com/acme/widgets.git"),
    )
    assert out["ok"] is True
    assert out["actual"] == "acme/widgets"


def test_verify_passes_on_matching_credentialed_remote():
    out = verify_origin_remote(
        "/ws/biz", "acme/widgets",
        git_remote_url=_stub_remote(f"https://x-access-token:{_TOKEN}@github.com/acme/widgets.git"),
    )
    assert out["ok"] is True


def test_verify_fails_on_wrong_remote():
    out = verify_origin_remote(
        "/ws/biz", "acme/widgets",
        git_remote_url=_stub_remote("https://github.com/someone-else/other.git"),
    )
    assert out["ok"] is False
    assert out["reason"] == "remote_mismatch"
    assert out["actual"] == "someone-else/other"
    assert out["expected"] == "acme/widgets"


def test_verify_fails_when_remote_is_the_runners_own_repo():
    """The exact M4b hazard: workspace never got redirected off bucks-ai."""
    out = verify_origin_remote(
        "/ws/biz", "acme/widgets",
        git_remote_url=_stub_remote("git@github.com:arnavt687/bucks-ai.git"),
    )
    assert out["ok"] is False
    assert out["reason"] == "remote_mismatch"


def test_verify_fails_when_no_origin():
    out = verify_origin_remote(
        "/ws/biz", "acme/widgets",
        git_remote_url=_stub_remote("", success=False, error="no_origin_remote"),
    )
    assert out["ok"] is False
    assert out["reason"] == "no_origin_remote"


def test_verify_fails_on_unparseable_remote():
    out = verify_origin_remote(
        "/ws/biz", "acme/widgets", git_remote_url=_stub_remote("garbage"),
    )
    assert out["ok"] is False
    assert out["reason"] == "unparseable_remote"


def test_verify_fails_when_expected_repo_missing():
    out = verify_origin_remote("/ws/biz", "", git_remote_url=_stub_remote("https://github.com/a/b.git"))
    assert out["ok"] is False
    assert out["reason"] == "no_expected_repo"


def test_verify_never_returns_the_token():
    url = f"https://x-access-token:{_TOKEN}@github.com/wrong/repo.git"
    out = verify_origin_remote("/ws/biz", "acme/widgets", git_remote_url=_stub_remote(url))
    assert _TOKEN not in repr(out)


def test_verify_reads_a_real_repo_remote():
    """End-to-end against a real git repo — no stub, exercises _git_remote_url."""
    import subprocess
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init", "-q"], cwd=d, check=True)
        subprocess.run(
            ["git", "remote", "add", "origin", "https://github.com/acme/widgets.git"],
            cwd=d, check=True,
        )
        assert verify_origin_remote(d, "acme/widgets")["ok"] is True
        assert verify_origin_remote(d, "other/repo")["reason"] == "remote_mismatch"


def test_verify_fails_on_repo_without_origin():
    import subprocess
    with tempfile.TemporaryDirectory() as d:
        subprocess.run(["git", "init", "-q"], cwd=d, check=True)
        out = verify_origin_remote(d, "acme/widgets")
        assert out["ok"] is False
        assert out["reason"] == "no_origin_remote"


# ---------------------------------------------------------------------------
# Graph node: wrong remote aborts the business task
# ---------------------------------------------------------------------------

def _state(task):
    return RunnerState(current_task_id=task.get("id", "t1"), current_task=task)


def _run_node_with_remote(verify_result):
    original_fetch = graph.lookup_business
    original_prepare = graph.prepare_business_repo
    original_verify = graph.verify_origin_remote
    original_failed = graph.mark_task_failed
    failed = []
    graph.mark_task_failed = lambda task_id, reason: failed.append((task_id, reason))
    graph.lookup_business = lambda bid: {"status": "found", "business": {"id": bid}}
    graph.prepare_business_repo = lambda task, business: {
        "success": True,
        "repo_path": "/tmp/.workspaces/biz-x",
        "repo_full_name": "acme/widgets",
        "github_token_secret_name": "ACME_TOKEN",
    }
    graph.verify_origin_remote = lambda path, expected: verify_result
    try:
        out = graph.resolve_business_repo_if_needed(
            _state({"id": "t1", "business_id": "biz-x", "runner_target": "business"})
        )
    finally:
        graph.lookup_business = original_fetch
        graph.prepare_business_repo = original_prepare
        graph.verify_origin_remote = original_verify
        graph.mark_task_failed = original_failed
    return out, failed


def test_node_aborts_on_wrong_remote():
    out, failed = _run_node_with_remote({
        "ok": False, "reason": "remote_mismatch",
        "expected": "acme/widgets", "actual": "someone-else/other",
    })
    assert out.stop_reason == "business_repo_remote_mismatch"
    # repo_path must NOT be applied — no work may proceed against this workspace.
    assert out.current_task.get("repo_path") is None
    assert failed and failed[0][0] == "t1"
    assert "someone-else/other" in failed[0][1]


def test_node_proceeds_on_matching_remote():
    out, failed = _run_node_with_remote({
        "ok": True, "reason": "", "expected": "acme/widgets", "actual": "acme/widgets",
    })
    assert out.stop_reason is None
    assert out.current_task["repo_path"] == "/tmp/.workspaces/biz-x"
    assert not failed


# ---------------------------------------------------------------------------
# Loop start preconditions
# ---------------------------------------------------------------------------

def test_loop_starts_on_clean_main():
    out = check_loop_start_preconditions("main", dirty=False)
    assert out["ok"] is True


def test_loop_refuses_non_main_branch():
    out = check_loop_start_preconditions("fix/sandbox-config-edit", dirty=False)
    assert out["ok"] is False
    assert out["reason"] == "non_main_branch"
    assert "fix/sandbox-config-edit" in out["message"]


def test_loop_refuses_dirty_tree():
    out = check_loop_start_preconditions("main", dirty=True)
    assert out["ok"] is False
    assert out["reason"] == "dirty_working_tree"


def test_loop_reports_branch_before_dirtiness():
    """Both wrong (the exact M4b launch state) — branch is the deeper problem."""
    out = check_loop_start_preconditions("fix/sandbox-config-edit", dirty=True)
    assert out["reason"] == "non_main_branch"


def test_loop_refuses_unknown_branch():
    out = check_loop_start_preconditions("", dirty=False)
    assert out["ok"] is False
    assert out["reason"] == "non_main_branch"


def test_loop_honours_custom_allowed_branches():
    out = check_loop_start_preconditions("trunk", dirty=False, allowed_branches=("trunk",))
    assert out["ok"] is True


# ---------------------------------------------------------------------------
# evaluate_loop_start — git status parsing
# ---------------------------------------------------------------------------

def _evaluate(branch, status_output):
    return evaluate_loop_start(
        "/repo",
        branch_fn=lambda p: branch,
        status_fn=lambda p: {"output": status_output, "success": True},
    )


def test_evaluate_clean_main_passes():
    assert _evaluate("main", "## main...origin/main")["ok"] is True


def test_evaluate_treats_modified_file_as_dirty():
    out = _evaluate("main", "## main...origin/main\n M runner/langgraph/config.py")
    assert out["ok"] is False
    assert out["reason"] == "dirty_working_tree"


def test_evaluate_treats_untracked_file_as_dirty():
    out = _evaluate("main", "## main...origin/main\n?? scratch.txt")
    assert out["reason"] == "dirty_working_tree"


def test_evaluate_ignores_ahead_behind_marker_on_branch_line():
    """'## main...origin/main [ahead 2]' is not a dirty tree."""
    assert _evaluate("main", "## main...origin/main [ahead 2]")["ok"] is True


def test_evaluate_refuses_feature_branch():
    out = _evaluate("feature/m4c/worker-dispatch-fix", "## feature/m4c/worker-dispatch-fix")
    assert out["reason"] == "non_main_branch"


# ---------------------------------------------------------------------------
# Claude worker dispatch: instruction on stdin, cwd at the business workspace
# ---------------------------------------------------------------------------

def _capture_claude_dispatch(task, prompt="Do the thing."):
    """Run ClaudeWorker._run_cli with the CLI stubbed out; return the call."""
    import workers.claude_worker as cw
    from state import ToolResult

    calls = {}

    def fake_run_command(cmd, cwd=None, timeout=None, env=None, stdin_data=None):
        calls["cmd"] = cmd
        calls["cwd"] = cwd
        calls["stdin_data"] = stdin_data
        return ToolResult(tool="shell", success=True, output='{"type": "result", "result": "done"}')

    original_run = cw.run_command
    original_log = cw.log_event
    original_write_hooks = cw.write_hooks
    original_validate_hooks = cw.validate_hooks
    cw.run_command = fake_run_command
    cw.log_event = lambda *a, **k: None
    # The hooks safety pack writes .claude/settings.json into repo_path; these
    # tests only care about how the CLI is invoked, and must not touch disk.
    cw.write_hooks = lambda path: {"merged": False, "path": path}
    cw.validate_hooks = lambda path: {"valid": True, "reason": "", "path": path}
    try:
        worker = cw.ClaudeWorker()
        worker._write_outbox = lambda task_id, p: "/tmp/outbox_stub.txt"
        worker._run_cli(prompt, task["id"], repo_path=task.get("repo_path"))
    finally:
        cw.run_command = original_run
        cw.log_event = original_log
        cw.write_hooks = original_write_hooks
        cw.validate_hooks = original_validate_hooks
    return calls


def test_claude_receives_prompt_as_instruction_not_file_reference():
    calls = _capture_claude_dispatch({"id": "t1", "repo_path": "/repo"}, prompt="Deploy the app.")
    assert calls["stdin_data"] == "Deploy the app."
    # No argv entry may be an @file mention — that is what made workers treat
    # the task as "a file describing work" rather than the work itself.
    assert not any(str(a).startswith("@") for a in calls["cmd"]), calls["cmd"]


def test_business_task_dispatches_with_workspace_cwd():
    ws = "/home/arnav/bucks-ai/runner/langgraph/.workspaces/biz-x"
    calls = _capture_claude_dispatch({"id": "t1", "repo_path": ws})
    assert calls["cwd"] == ws


def test_self_task_dispatches_with_repo_path_cwd():
    calls = _capture_claude_dispatch({"id": "t1", "repo_path": "/home/arnav/bucks-ai"})
    assert calls["cwd"] == "/home/arnav/bucks-ai"


def test_dispatch_cwd_is_never_none():
    """A None cwd means the worker inherits the runner's process directory —
    the M4b failure mode where a business task ran inside bucks-ai."""
    calls = _capture_claude_dispatch({"id": "t1"})
    assert calls["cwd"] is not None


def test_run_worker_prompt_passes_business_repo_path_through():
    """The repo_path override set by resolve_business_repo_if_needed must reach
    the CLI invocation, not be dropped between node and worker."""
    import workers.claude_worker as cw
    ws = "/tmp/.workspaces/biz-x"
    seen = {}

    original_run_cli = cw.ClaudeWorker._run_cli
    original_log = cw.log_event
    cw.log_event = lambda *a, **k: None

    def fake_run_cli(self, prompt, task_id, model=None, auth_mode="api_key", repo_path=None):
        seen["repo_path"] = repo_path
        seen["prompt"] = prompt
        from state import WorkerResult
        return WorkerResult(worker="claude", mode="cli", success=True, output="ok")

    cw.ClaudeWorker._run_cli = fake_run_cli
    original_which = cw.shutil.which
    cw.shutil.which = lambda name: "/usr/bin/claude"
    try:
        cw.ClaudeWorker().run_worker_prompt("Ship it.", {"id": "t1", "repo_path": ws})
    finally:
        cw.ClaudeWorker._run_cli = original_run_cli
        cw.shutil.which = original_which
        cw.log_event = original_log

    assert seen["repo_path"] == ws
    assert "Ship it." in seen["prompt"]


# ---------------------------------------------------------------------------
# Config wiring + the run-loop gate itself
# ---------------------------------------------------------------------------

def _config_with(value):
    from config import RunnerConfig
    original = os.environ.get("LOOP_START_PREFLIGHT")
    if value is None:
        os.environ.pop("LOOP_START_PREFLIGHT", None)
    else:
        os.environ["LOOP_START_PREFLIGHT"] = value
    try:
        return RunnerConfig()
    finally:
        if original is None:
            os.environ.pop("LOOP_START_PREFLIGHT", None)
        else:
            os.environ["LOOP_START_PREFLIGHT"] = original


def test_preflight_config_defaults_on():
    assert _config_with(None).loop_start_preflight_enabled is True


def test_preflight_config_can_be_disabled():
    assert _config_with("false").loop_start_preflight_enabled is False


def test_preflight_config_appears_in_report():
    assert "loop_start_preflight_enabled" in _config_with(None).report()


def _run_gate(verdict, enabled=True):
    """Invoke main.preflight_or_exit with a stubbed verdict; return exit code."""
    import main
    import config as config_mod
    import tools.dispatch_preflight as dp

    original_eval = dp.evaluate_loop_start
    original_get = config_mod.get_config
    dp.evaluate_loop_start = lambda repo_path: verdict

    class _Cfg:
        loop_start_preflight_enabled = enabled
        repo_path = "/repo"

    config_mod.get_config = lambda: _Cfg()
    try:
        main.preflight_or_exit("run-loop")
        return 0
    except SystemExit as e:
        return e.code
    finally:
        dp.evaluate_loop_start = original_eval
        config_mod.get_config = original_get


_OK = {"ok": True, "reason": "", "branch": "main", "dirty": False, "message": ""}
_DIRTY = {"ok": False, "reason": "dirty_working_tree", "branch": "main", "dirty": True, "message": "dirty"}
_BRANCH = {"ok": False, "reason": "non_main_branch", "branch": "fix/x", "dirty": False, "message": "wrong branch"}


def test_gate_allows_clean_main():
    assert _run_gate(_OK) == 0


def test_gate_exits_on_dirty_tree():
    assert _run_gate(_DIRTY) == 1


def test_gate_exits_on_non_main_branch():
    assert _run_gate(_BRANCH) == 1


def test_gate_can_be_disabled_by_config():
    assert _run_gate(_BRANCH, enabled=False) == 0


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    passed = failed = 0
    for t in tests:
        try:
            t()
            print(f"  PASS  {t.__name__}")
            passed += 1
        except Exception as e:
            print(f"  FAIL  {t.__name__}: {e}")
            traceback.print_exc()
            failed += 1
    print(f"\n{passed} passed, {failed} failed")
    sys.exit(1 if failed else 0)
