"""Unit tests for Codex CLI JSONL output parsing and token wiring.

Covers `workers.codex_worker.parse_codex_cli_jsonl` (pure parser, tested
against realistic `codex exec --json` fixtures) and `CodexWorker._run_cli`
(wiring parsed tokens into WorkerResult; run_command is mocked so no real CLI
is invoked). Codex CLI reports no dollar cost, so api_cost must always stay
None here — cost_budget_guard's estimate fallback (see
tests/test_cost_budget_guard.py) is what covers Codex spend tracking.

Runs standalone:

    python tests/test_codex_worker_json_parsing.py
"""
import os
import sys
import traceback
import unittest.mock as mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import RunnerConfig
from workers.codex_worker import CodexWorker, parse_codex_cli_jsonl

_SUMMARY = (
    "- Files Created: none\n- Files Modified: src/Button.tsx\n"
    "- Check Result: pass\n- Commit Result: def5678\n- Push Result: done\n"
    "- SQL Required: no\n- SQL File Path: N/A\n- Credentials Needed: none\n"
    "- Resources Needed: none\n- Known Limitations: none\n- Next Task: none"
)

# A realistic `codex exec --json` single-turn JSONL stream.
CODEX_JSONL_SINGLE_TURN = "\n".join([
    '{"type":"thread.started","thread_id":"0199a213-81c0-7800-8aa1-bbab2a035a53"}',
    '{"type":"turn.started"}',
    '{"type":"item.started","item":{"id":"item_1","type":"command_execution","command":"bash -lc ls","status":"in_progress"}}',
    '{"type":"item.completed","item":{"id":"item_1","type":"command_execution","command":"bash -lc ls","status":"completed"}}',
    '{"type":"item.completed","item":{"id":"item_3","type":"agent_message","text":"%s"}}' % _SUMMARY.replace("\n", "\\n"),
    '{"type":"turn.completed","usage":{"input_tokens":24763,"cached_input_tokens":24448,"output_tokens":122,"reasoning_output_tokens":0}}',
])

# Multi-turn stream — the final turn.completed's usage should win, not the sum.
CODEX_JSONL_MULTI_TURN = "\n".join([
    '{"type":"thread.started","thread_id":"t1"}',
    '{"type":"turn.started"}',
    '{"type":"item.completed","item":{"id":"item_1","type":"agent_message","text":"intermediate note"}}',
    '{"type":"turn.completed","usage":{"input_tokens":1000,"output_tokens":50}}',
    '{"type":"turn.started"}',
    '{"type":"item.completed","item":{"id":"item_2","type":"agent_message","text":"%s"}}' % _SUMMARY.replace("\n", "\\n"),
    '{"type":"turn.completed","usage":{"input_tokens":1400,"output_tokens":80}}',
])


# ── parse_codex_cli_jsonl — pure parser ──────────────────────────────────

def test_parses_single_turn_stream():
    parsed = parse_codex_cli_jsonl(CODEX_JSONL_SINGLE_TURN)
    assert parsed is not None
    assert parsed["tokens_used"] == 24763 + 122
    assert parsed["result_text"] == _SUMMARY


def test_multi_turn_uses_final_turn_usage_not_sum():
    parsed = parse_codex_cli_jsonl(CODEX_JSONL_MULTI_TURN)
    assert parsed is not None
    assert parsed["tokens_used"] == 1400 + 80
    assert parsed["result_text"] == _SUMMARY


def test_returns_result_text_none_when_no_agent_message():
    stream = '{"type":"thread.started","thread_id":"t1"}\n{"type":"turn.completed","usage":{"input_tokens":10,"output_tokens":5}}'
    parsed = parse_codex_cli_jsonl(stream)
    assert parsed is not None
    assert parsed["result_text"] is None
    assert parsed["tokens_used"] == 15


def test_returns_tokens_none_when_no_usage_event():
    stream = '{"type":"item.completed","item":{"type":"agent_message","text":"hello"}}'
    parsed = parse_codex_cli_jsonl(stream)
    assert parsed is not None
    assert parsed["tokens_used"] is None
    assert parsed["result_text"] == "hello"


def test_returns_none_for_empty_output():
    assert parse_codex_cli_jsonl("") is None
    assert parse_codex_cli_jsonl(None) is None


def test_returns_none_for_non_json_output():
    assert parse_codex_cli_jsonl("plain text, not JSONL at all") is None


def test_skips_malformed_lines_without_crashing():
    stream = "\n".join([
        '{"type":"thread.started","thread_id":"t1"}',
        "not valid json {{{",
        '{"type":"turn.completed","usage":{"input_tokens":5,"output_tokens":5}}',
    ])
    parsed = parse_codex_cli_jsonl(stream)
    assert parsed is not None
    assert parsed["tokens_used"] == 10


# ── CodexWorker._run_cli — wiring into WorkerResult ──────────────────────

def _fake_run_command(output, success=True):
    def _run(cmd, stdin_data=None, timeout=120, **kwargs):
        from state import ToolResult
        return ToolResult(tool="shell", success=success, output=output)
    return _run


def test_run_cli_captures_tokens_never_guesses_cost():
    worker = CodexWorker()
    with mock.patch("workers.codex_worker.run_command", side_effect=_fake_run_command(CODEX_JSONL_SINGLE_TURN)), \
         mock.patch("workers.codex_worker.get_config") as mock_cfg:
        mock_cfg.return_value = RunnerConfig()
        result = worker._run_cli("do the thing", "t1")

    assert result.success is True
    assert result.tokens_used == 24763 + 122
    assert result.api_cost is None  # Codex CLI never reports cost — must not be guessed
    assert result.output == _SUMMARY


def test_run_cli_unparseable_output_leaves_tokens_none():
    worker = CodexWorker()
    logged = []
    with mock.patch("workers.codex_worker.run_command", side_effect=_fake_run_command("plain text output")), \
         mock.patch("workers.codex_worker.get_config") as mock_cfg, \
         mock.patch("workers.codex_worker.log_event", side_effect=lambda ev, data, **k: logged.append(ev)):
        mock_cfg.return_value = RunnerConfig()
        result = worker._run_cli("do the thing", "t2")

    assert result.tokens_used is None
    assert result.api_cost is None
    assert result.output == "plain text output"
    assert "codex_cli_json_parse_failed" in logged


def test_run_cli_failed_command_skips_parsing():
    worker = CodexWorker()
    with mock.patch("workers.codex_worker.run_command", side_effect=_fake_run_command("error text", success=False)), \
         mock.patch("workers.codex_worker.get_config") as mock_cfg:
        mock_cfg.return_value = RunnerConfig()
        result = worker._run_cli("do the thing", "t3")

    assert result.success is False
    assert result.tokens_used is None
    assert result.api_cost is None
    assert result.output == "error text"


if __name__ == "__main__":
    tests = [
        test_parses_single_turn_stream,
        test_multi_turn_uses_final_turn_usage_not_sum,
        test_returns_result_text_none_when_no_agent_message,
        test_returns_tokens_none_when_no_usage_event,
        test_returns_none_for_empty_output,
        test_returns_none_for_non_json_output,
        test_skips_malformed_lines_without_crashing,
        test_run_cli_captures_tokens_never_guesses_cost,
        test_run_cli_unparseable_output_leaves_tokens_none,
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
