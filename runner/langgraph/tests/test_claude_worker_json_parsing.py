"""Unit tests for Claude CLI JSON output parsing and cost/token wiring.

Covers `workers.claude_worker.parse_claude_cli_json` (pure parser, tested
against realistic `--output-format json` fixtures) and `ClaudeWorker._run_cli`
(wiring the parsed cost/tokens into WorkerResult, with run_command mocked so
no real CLI is invoked).

Runs standalone:

    python tests/test_claude_worker_json_parsing.py
"""
import os
import sys
import traceback
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import RunnerConfig
from workers.claude_worker import ClaudeWorker, parse_claude_cli_json

# A realistic `claude --print --output-format json` success envelope.
CLAUDE_JSON_SUCCESS = """{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "duration_ms": 45210,
  "duration_api_ms": 41890,
  "num_turns": 4,
  "result": "- Files Created: none\\n- Files Modified: src/foo.ts\\n- Check Result: pass\\n- Commit Result: abc1234\\n- Push Result: done\\n- SQL Required: no\\n- SQL File Path: N/A\\n- Credentials Needed: none\\n- Resources Needed: none\\n- Known Limitations: none\\n- Next Task: none",
  "session_id": "b1f7e6b0-1234-4c56-9abc-1234567890ab",
  "total_cost_usd": 0.084231,
  "usage": {
    "input_tokens": 1200,
    "cache_creation_input_tokens": 300,
    "cache_read_input_tokens": 8400,
    "output_tokens": 640
  }
}"""

# Envelope with no cache usage at all (short task, nothing cached).
CLAUDE_JSON_NO_CACHE = """{
  "type": "result",
  "subtype": "success",
  "is_error": false,
  "result": "- Files Created: none\\n- Files Modified: none\\n- Check Result: pass\\n- Commit Result: skipped\\n- Push Result: skipped\\n- SQL Required: no\\n- SQL File Path: N/A\\n- Credentials Needed: none\\n- Resources Needed: none\\n- Known Limitations: none\\n- Next Task: none",
  "session_id": "abc",
  "total_cost_usd": 0.002,
  "usage": {"input_tokens": 50, "output_tokens": 20}
}"""

# CLI emitted a warning to stderr before the JSON; shell_tools concatenates
# stdout+stderr so the parser must recover the JSON from inside the noise.
CLAUDE_JSON_WITH_STDERR_NOISE = (
    "Warning: some deprecation notice\n" + CLAUDE_JSON_SUCCESS + "\n"
)


# ── parse_claude_cli_json — pure parser ──────────────────────────────────

def test_parses_success_envelope():
    parsed = parse_claude_cli_json(CLAUDE_JSON_SUCCESS)
    assert parsed is not None
    assert parsed["total_cost_usd"] == 0.084231
    assert parsed["tokens_used"] == 1200 + 300 + 8400 + 640
    assert parsed["result_text"].startswith("- Files Created:")


def test_parses_envelope_without_cache_fields():
    parsed = parse_claude_cli_json(CLAUDE_JSON_NO_CACHE)
    assert parsed is not None
    assert parsed["tokens_used"] == 70
    assert parsed["total_cost_usd"] == 0.002


def test_recovers_json_from_stderr_noise():
    parsed = parse_claude_cli_json(CLAUDE_JSON_WITH_STDERR_NOISE)
    assert parsed is not None
    assert parsed["total_cost_usd"] == 0.084231


def test_returns_none_for_plain_text_output():
    parsed = parse_claude_cli_json("- Files Created: none\n- Check Result: pass\n")
    assert parsed is None


def test_returns_none_for_empty_output():
    assert parse_claude_cli_json("") is None
    assert parse_claude_cli_json(None) is None


def test_returns_none_for_wrong_envelope_type():
    parsed = parse_claude_cli_json('{"type": "system", "subtype": "init"}')
    assert parsed is None


def test_returns_none_for_malformed_json():
    parsed = parse_claude_cli_json('{"type": "result", "result": "oops"')  # truncated
    assert parsed is None


# ── ClaudeWorker._run_cli — wiring into WorkerResult ─────────────────────

def _fake_run_command(output, success=True):
    def _run(cmd, timeout=120, env=None, **kwargs):
        from state import ToolResult
        return ToolResult(tool="shell", success=success, output=output)
    return _run


def test_run_cli_api_key_mode_uses_real_cost_and_tokens():
    worker = ClaudeWorker()
    with mock.patch("workers.claude_worker.run_command", side_effect=_fake_run_command(CLAUDE_JSON_SUCCESS)), \
         mock.patch("workers.claude_worker.get_config") as mock_cfg:
        mock_cfg.return_value = RunnerConfig(claude_hooks_safety_pack_enabled=False)
        result = worker._run_cli("do the thing", "t1", auth_mode="api_key")

    assert result.success is True
    assert result.api_cost == 0.084231
    assert result.tokens_used == 1200 + 300 + 8400 + 640
    assert result.output.startswith("- Files Created:")


def test_run_cli_subscription_mode_zeroes_cost_but_keeps_tokens():
    worker = ClaudeWorker()
    with mock.patch("workers.claude_worker.run_command", side_effect=_fake_run_command(CLAUDE_JSON_SUCCESS)), \
         mock.patch("workers.claude_worker.get_config") as mock_cfg:
        mock_cfg.return_value = RunnerConfig(claude_hooks_safety_pack_enabled=False)
        result = worker._run_cli("do the thing", "t2", auth_mode="subscription")

    assert result.success is True
    assert result.api_cost == 0.0
    assert result.tokens_used == 1200 + 300 + 8400 + 640


def test_run_cli_unparseable_json_leaves_fields_none():
    """Per spec: if JSON output isn't available, parse nothing rather than
    guessing — leave api_cost/tokens_used None and fall back to raw output."""
    worker = ClaudeWorker()
    logged = []
    with mock.patch("workers.claude_worker.run_command", side_effect=_fake_run_command("not json at all")), \
         mock.patch("workers.claude_worker.get_config") as mock_cfg, \
         mock.patch("workers.claude_worker.log_event", side_effect=lambda ev, data, **k: logged.append(ev)):
        mock_cfg.return_value = RunnerConfig(claude_hooks_safety_pack_enabled=False)
        result = worker._run_cli("do the thing", "t3", auth_mode="api_key")

    assert result.api_cost is None
    assert result.tokens_used is None
    assert result.output == "not json at all"
    assert "claude_cli_json_parse_failed" in logged


def test_run_cli_failed_command_skips_parsing():
    worker = ClaudeWorker()
    with mock.patch("workers.claude_worker.run_command", side_effect=_fake_run_command("some error text", success=False)), \
         mock.patch("workers.claude_worker.get_config") as mock_cfg:
        mock_cfg.return_value = RunnerConfig(claude_hooks_safety_pack_enabled=False)
        result = worker._run_cli("do the thing", "t4", auth_mode="api_key")

    assert result.success is False
    assert result.api_cost is None
    assert result.tokens_used is None
    assert result.output == "some error text"


if __name__ == "__main__":
    tests = [
        test_parses_success_envelope,
        test_parses_envelope_without_cache_fields,
        test_recovers_json_from_stderr_noise,
        test_returns_none_for_plain_text_output,
        test_returns_none_for_empty_output,
        test_returns_none_for_wrong_envelope_type,
        test_returns_none_for_malformed_json,
        test_run_cli_api_key_mode_uses_real_cost_and_tokens,
        test_run_cli_subscription_mode_zeroes_cost_but_keeps_tokens,
        test_run_cli_unparseable_json_leaves_fields_none,
        test_run_cli_failed_command_skips_parsing,
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
