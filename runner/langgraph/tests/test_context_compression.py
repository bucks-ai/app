"""Unit tests for deterministic runner context compression."""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from state import RunnerState
from tools.context_compression import (
    compress_messages,
    estimate_tokens,
    message_token_count,
    messages_token_count,
)

import graph


def test_estimate_tokens_handles_empty_and_text():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello world") > 0


def test_message_token_count_includes_role_and_content():
    with_role = message_token_count({"role": "assistant", "content": "hello"})
    no_role = message_token_count({"content": "hello"})
    assert with_role > no_role


def test_compress_messages_noops_under_limit():
    messages = [{"role": "user", "content": "short"}]
    result = compress_messages(messages, max_tokens=100000, keep_recent=1)
    assert result["compressed"] is False
    assert result["messages"] == messages
    assert result["tokens_before"] == result["tokens_after"]


def test_compress_messages_replaces_old_messages_and_keeps_recent_tail():
    messages = [
        {"role": "user", "content": "old prompt " * 100},
        {"role": "assistant", "content": "old output " * 100},
        {"role": "user", "content": "active prompt"},
        {"role": "assistant", "content": "active output"},
    ]

    result = compress_messages(
        messages,
        max_tokens=10,
        keep_recent=2,
        summary_digest="Task: compact\nCheck: pass",
    )

    assert result["compressed"] is True
    assert result["dropped_messages"] == 2
    assert result["messages"][0]["role"] == "system"
    assert "Runner context compressed." in result["messages"][0]["content"]
    assert "Task: compact" in result["messages"][0]["content"]
    assert result["messages"][-2:] == messages[-2:]


def test_compress_messages_preserves_tail_even_if_still_over_limit():
    messages = [
        {"role": "user", "content": "old " * 200},
        {"role": "assistant", "content": "recent " * 200},
    ]
    result = compress_messages(messages, max_tokens=1, keep_recent=1)
    assert result["compressed"] is True
    assert result["messages"][-1] == messages[-1]
    assert messages_token_count(result["messages"]) >= 1


def test_graph_compresses_after_worker_summary_without_raw_content_in_event():
    events = []
    orig_log = graph.log_event
    orig_max = graph.cfg.context_compression_max_tokens
    orig_keep = graph.cfg.context_compression_keep_recent
    graph.log_event = lambda event_type, payload, task_id=None: events.append((event_type, payload, task_id))
    graph.cfg.context_compression_max_tokens = 10
    graph.cfg.context_compression_keep_recent = 1
    try:
        s = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1", "title": "Compress context"},
            messages=[
                {"role": "user", "content": "old prompt secret-ish text " * 100},
                {"role": "assistant", "content": "old output secret-ish text " * 100},
                {"role": "user", "content": "active prompt"},
            ],
            worker_result={"success": True, "output": """
- Files Created: (none)
- Files Modified:
  - runner/langgraph/tools/context_compression.py
- Check Result: pass
- Commit Result: skipped
- Push Result: skipped
- SQL Required: no
- SQL File Path: N/A
"""},
        )
        out = graph.parse_worker_summary_node(s)
        compression_events = [event for event in events if event[0] == "context_compressed"]
        assert compression_events, events
        assert out.context_compression["reason"] == "after_worker_summary"
        assert len(out.messages) == 2
        assert out.messages[0]["role"] == "system"
        assert "secret-ish" not in str(compression_events[0][1])
    finally:
        graph.log_event = orig_log
        graph.cfg.context_compression_max_tokens = orig_max
        graph.cfg.context_compression_keep_recent = orig_keep


if __name__ == "__main__":
    import traceback

    tests = [
        test_estimate_tokens_handles_empty_and_text,
        test_message_token_count_includes_role_and_content,
        test_compress_messages_noops_under_limit,
        test_compress_messages_replaces_old_messages_and_keeps_recent_tail,
        test_compress_messages_preserves_tail_even_if_still_over_limit,
        test_graph_compresses_after_worker_summary_without_raw_content_in_event,
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
