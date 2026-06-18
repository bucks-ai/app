"""Unit tests for Claude subscription auth mode.

Runs standalone:

    python tests/test_claude_subscription_auth_mode.py
"""
import os
import sys
import traceback
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import RunnerConfig


# ── Config field and property tests ──────────────────────────────────────────

def test_default_auth_mode_is_api_key():
    cfg = RunnerConfig(anthropic_api_key=None)
    assert cfg.claude_auth_mode == "api_key"


def test_subscription_auth_mode_from_env():
    with mock.patch.dict(os.environ, {"CLAUDE_AUTH_MODE": "subscription"}):
        from config import RunnerConfig as _Cfg
        cfg = _Cfg()
        assert cfg.claude_auth_mode == "subscription"


def test_has_claude_true_with_api_key():
    cfg = RunnerConfig(anthropic_api_key="sk-ant-test", claude_auth_mode="api_key")
    assert cfg.has_claude is True


def test_has_claude_true_with_subscription_no_api_key():
    cfg = RunnerConfig(anthropic_api_key=None, claude_auth_mode="subscription")
    assert cfg.has_claude is True


def test_has_claude_false_without_either():
    cfg = RunnerConfig(anthropic_api_key=None, claude_auth_mode="api_key")
    assert cfg.has_claude is False


def test_has_anthropic_unchanged():
    cfg = RunnerConfig(anthropic_api_key="sk-ant-test")
    assert cfg.has_anthropic is True
    cfg2 = RunnerConfig(anthropic_api_key=None)
    assert cfg2.has_anthropic is False


def test_report_includes_claude_auth_mode():
    cfg = RunnerConfig(claude_auth_mode="subscription")
    report = cfg.report()
    assert "claude_auth_mode" in report
    assert report["claude_auth_mode"] == "subscription"


def test_report_default_claude_auth_mode():
    cfg = RunnerConfig()
    report = cfg.report()
    assert report["claude_auth_mode"] == "api_key"


# ── Worker env-stripping tests ────────────────────────────────────────────────

def test_subscription_mode_strips_api_key_from_env():
    from workers.claude_worker import ClaudeWorker

    worker = ClaudeWorker()
    captured_env = {}

    def fake_run_command(cmd, timeout=120, env=None, **kwargs):
        captured_env["env"] = env
        from state import ToolResult
        return ToolResult(tool="shell", success=True, output="done")

    with mock.patch("workers.claude_worker.run_command", side_effect=fake_run_command), \
         mock.patch("workers.claude_worker.get_config") as mock_cfg, \
         mock.patch.dict(os.environ, {"ANTHROPIC_API_KEY": "sk-ant-test", "PATH": "/usr/bin"}):

        cfg = RunnerConfig(anthropic_api_key="sk-ant-test", claude_auth_mode="subscription")
        mock_cfg.return_value = cfg

        worker._run_cli("hello", "t1", auth_mode="subscription")

    assert captured_env["env"] is not None
    assert "ANTHROPIC_API_KEY" not in captured_env["env"]
    assert "PATH" in captured_env["env"]


def test_api_key_mode_passes_env_none():
    from workers.claude_worker import ClaudeWorker

    worker = ClaudeWorker()
    captured_env = {}

    def fake_run_command(cmd, timeout=120, env=None, **kwargs):
        captured_env["env"] = env
        from state import ToolResult
        return ToolResult(tool="shell", success=True, output="done")

    with mock.patch("workers.claude_worker.run_command", side_effect=fake_run_command):
        worker._run_cli("hello", "t2", auth_mode="api_key")

    assert captured_env["env"] is None


def test_default_auth_mode_passes_env_none():
    from workers.claude_worker import ClaudeWorker

    worker = ClaudeWorker()
    captured_env = {}

    def fake_run_command(cmd, timeout=120, env=None, **kwargs):
        captured_env["env"] = env
        from state import ToolResult
        return ToolResult(tool="shell", success=True, output="done")

    with mock.patch("workers.claude_worker.run_command", side_effect=fake_run_command):
        worker._run_cli("hello", "t3")

    assert captured_env["env"] is None


def test_subscription_mode_logged_in_worker_started():
    from workers.claude_worker import ClaudeWorker

    worker = ClaudeWorker()
    logged = []

    def fake_log(event, data, **kwargs):
        logged.append((event, data))

    def fake_run_command(cmd, timeout=120, env=None, **kwargs):
        from state import ToolResult
        return ToolResult(tool="shell", success=True, output="ok")

    with mock.patch("workers.claude_worker.log_event", side_effect=fake_log), \
         mock.patch("workers.claude_worker.run_command", side_effect=fake_run_command), \
         mock.patch("workers.claude_worker.shutil.which", return_value="/usr/bin/claude"), \
         mock.patch("workers.claude_worker.get_config") as mock_cfg:

        cfg = RunnerConfig(anthropic_api_key=None, claude_auth_mode="subscription")
        mock_cfg.return_value = cfg

        worker.run_worker_prompt("do something", {"id": "t4"})

    started = next((d for ev, d in logged if ev == "worker_started"), None)
    assert started is not None
    assert started["auth_mode"] == "subscription"


# ── shell_tools env passthrough ───────────────────────────────────────────────

def test_run_command_passes_env_to_subprocess():
    from tools.shell_tools import run_command
    import subprocess

    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")
        run_command(["echo", "hi"], env={"MY_VAR": "1"})
        _, kwargs = mock_run.call_args
        assert kwargs["env"] == {"MY_VAR": "1"}


def test_run_command_env_none_by_default():
    from tools.shell_tools import run_command
    import subprocess

    with mock.patch("subprocess.run") as mock_run:
        mock_run.return_value = mock.Mock(returncode=0, stdout="ok", stderr="")
        run_command(["echo", "hi"])
        _, kwargs = mock_run.call_args
        assert kwargs["env"] is None


if __name__ == "__main__":
    tests = [
        test_default_auth_mode_is_api_key,
        test_subscription_auth_mode_from_env,
        test_has_claude_true_with_api_key,
        test_has_claude_true_with_subscription_no_api_key,
        test_has_claude_false_without_either,
        test_has_anthropic_unchanged,
        test_report_includes_claude_auth_mode,
        test_report_default_claude_auth_mode,
        test_subscription_mode_strips_api_key_from_env,
        test_api_key_mode_passes_env_none,
        test_default_auth_mode_passes_env_none,
        test_subscription_mode_logged_in_worker_started,
        test_run_command_passes_env_to_subprocess,
        test_run_command_env_none_by_default,
    ]
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
