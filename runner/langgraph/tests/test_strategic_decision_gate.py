"""Unit tests for the strategic decision gate.

Runs standalone (no pytest dependency), mirroring test_resource_gate.py:

    python tests/test_strategic_decision_gate.py

Covers the pure decision helper in tools/strategic_decision_gate.py and the
graph.run_strategic_gate node. The node is exercised against a temporary
outbox/inbox so no real disk state under the runner is touched, and
log_event / update_state are stubbed.
"""
import os
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.strategic_decision_gate import (
    evaluate_strategic_gate,
    format_review_file,
    STRATEGIC_GATE_STOP,
)
import graph
from state import RunnerState

# Silence the flight recorder and disk persistence during tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None


# ---------------------------------------------------------------------------
# Pure helper: evaluate_strategic_gate
# ---------------------------------------------------------------------------

def test_interval_zero_never_triggers():
    r = evaluate_strategic_gate(tasks_since_gate=99, strategic_pause_interval=0)
    assert r["triggered"] is False
    assert r["blocked"] is False
    assert r["stop_reason"] is None
    assert r["tasks_since_gate"] == 100


def test_interval_negative_never_triggers():
    r = evaluate_strategic_gate(tasks_since_gate=5, strategic_pause_interval=-1)
    assert r["triggered"] is False
    assert r["tasks_since_gate"] == 6


def test_count_increments_before_interval():
    r = evaluate_strategic_gate(tasks_since_gate=3, strategic_pause_interval=5)
    assert r["triggered"] is False
    assert r["blocked"] is False
    assert r["stop_reason"] is None
    assert r["tasks_since_gate"] == 4


def test_triggers_exactly_at_interval():
    r = evaluate_strategic_gate(tasks_since_gate=4, strategic_pause_interval=5)
    assert r["triggered"] is True
    assert r["blocked"] is True
    assert r["stop_reason"] == STRATEGIC_GATE_STOP
    assert r["tasks_since_gate"] == 0


def test_triggers_past_interval():
    r = evaluate_strategic_gate(tasks_since_gate=10, strategic_pause_interval=5)
    assert r["triggered"] is True
    assert r["stop_reason"] == STRATEGIC_GATE_STOP
    assert r["tasks_since_gate"] == 0


def test_interval_one_triggers_every_task():
    r = evaluate_strategic_gate(tasks_since_gate=0, strategic_pause_interval=1)
    assert r["triggered"] is True
    assert r["tasks_since_gate"] == 0


def test_counter_resets_to_zero_on_trigger():
    r = evaluate_strategic_gate(tasks_since_gate=9, strategic_pause_interval=10)
    assert r["triggered"] is True
    assert r["tasks_since_gate"] == 0


def test_stop_reason_constant():
    assert STRATEGIC_GATE_STOP == "awaiting_strategic_review"


# ---------------------------------------------------------------------------
# Pure helper: format_review_file
# ---------------------------------------------------------------------------

def test_format_review_file_contains_loop_count():
    text = format_review_file(42, 10, "last task done things", "strategic_review_42_approved.txt")
    assert "loop: 42" in text
    assert "10 task(s)" in text
    assert "strategic_review_42_approved.txt" in text
    assert "last task done things" in text


def test_format_review_file_no_digest():
    text = format_review_file(1, 5, "", "strategic_review_1_approved.txt")
    assert "Last task summary" not in text
    assert "strategic_review_1_approved.txt" in text


# ---------------------------------------------------------------------------
# Node behavior — exercised against a temp outbox/inbox
# ---------------------------------------------------------------------------

def _state(loop_count=0, tasks_since_gate=0, gate_status=None, gate_at_loop=None, digest=""):
    return RunnerState(
        loop_count=loop_count,
        strategic_tasks_since_gate=tasks_since_gate,
        strategic_gate_status=gate_status,
        strategic_gate_at_loop=gate_at_loop,
        worker_summary_digest=digest,
    )


def _with_temp_runner_dir(fn):
    """Run fn(outbox, inbox) with graph._RUNNER_DIR pointed at a temp dir."""
    original = graph._RUNNER_DIR
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        (root / "outbox").mkdir()
        (root / "inbox").mkdir()
        graph._RUNNER_DIR = root
        try:
            return fn(root / "outbox", root / "inbox")
        finally:
            graph._RUNNER_DIR = original


def test_node_disabled_when_interval_zero():
    def body(outbox, inbox):
        graph.cfg.strategic_gate_enabled = True
        graph.cfg.strategic_pause_interval = 0
        out = graph.run_strategic_gate(_state(tasks_since_gate=99))
        assert out.stop_reason is None, out.stop_reason
        assert out.strategic_gate_status is None, out.strategic_gate_status
        assert list(outbox.iterdir()) == [], "no outbox file when disabled"
    _with_temp_runner_dir(body)


def test_node_disabled_when_flag_off():
    def body(outbox, inbox):
        graph.cfg.strategic_gate_enabled = False
        graph.cfg.strategic_pause_interval = 5
        out = graph.run_strategic_gate(_state(tasks_since_gate=4))
        assert out.stop_reason is None, out.stop_reason
        assert list(outbox.iterdir()) == []
    _with_temp_runner_dir(body)


def test_node_counts_without_triggering():
    def body(outbox, inbox):
        graph.cfg.strategic_gate_enabled = True
        graph.cfg.strategic_pause_interval = 5
        out = graph.run_strategic_gate(_state(tasks_since_gate=2))
        assert out.stop_reason is None, out.stop_reason
        assert out.strategic_tasks_since_gate == 3, out.strategic_tasks_since_gate
        assert list(outbox.iterdir()) == []
    _with_temp_runner_dir(body)


def test_node_triggers_at_interval_and_blocks():
    def body(outbox, inbox):
        graph.cfg.strategic_gate_enabled = True
        graph.cfg.strategic_pause_interval = 5
        out = graph.run_strategic_gate(_state(loop_count=7, tasks_since_gate=4))
        assert out.stop_reason == STRATEGIC_GATE_STOP, out.stop_reason
        assert out.strategic_gate_status == "pending", out.strategic_gate_status
        assert out.strategic_gate_at_loop == 7, out.strategic_gate_at_loop
        review_file = outbox / "strategic_review_7.txt"
        assert review_file.exists(), "review file should be written to outbox"
        assert "loop: 7" in review_file.read_text()
    _with_temp_runner_dir(body)


def test_node_pending_blocks_without_approval():
    def body(outbox, inbox):
        graph.cfg.strategic_gate_enabled = True
        graph.cfg.strategic_pause_interval = 5
        out = graph.run_strategic_gate(_state(gate_status="pending", gate_at_loop=3))
        assert out.stop_reason == STRATEGIC_GATE_STOP, out.stop_reason
        assert out.strategic_gate_status == "pending", out.strategic_gate_status
    _with_temp_runner_dir(body)


def test_node_pending_resumes_when_approved():
    def body(outbox, inbox):
        graph.cfg.strategic_gate_enabled = True
        graph.cfg.strategic_pause_interval = 5
        (inbox / "strategic_review_3_approved.txt").write_text("ok")
        out = graph.run_strategic_gate(_state(gate_status="pending", gate_at_loop=3))
        assert out.stop_reason is None, out.stop_reason
        assert out.strategic_gate_status is None, out.strategic_gate_status
        assert out.strategic_tasks_since_gate == 0, out.strategic_tasks_since_gate
    _with_temp_runner_dir(body)


def test_node_review_file_idempotent():
    def body(outbox, inbox):
        graph.cfg.strategic_gate_enabled = True
        graph.cfg.strategic_pause_interval = 3
        s = _state(loop_count=5, tasks_since_gate=2)
        graph.run_strategic_gate(s)
        mtime1 = (outbox / "strategic_review_5.txt").stat().st_mtime
        graph.run_strategic_gate(_state(loop_count=5, tasks_since_gate=2))
        mtime2 = (outbox / "strategic_review_5.txt").stat().st_mtime
        assert mtime1 == mtime2, "review file must not be rewritten if it exists"
    _with_temp_runner_dir(body)


def test_node_pre_approved_does_not_block():
    def body(outbox, inbox):
        graph.cfg.strategic_gate_enabled = True
        graph.cfg.strategic_pause_interval = 3
        (inbox / "strategic_review_5_approved.txt").write_text("pre-approved")
        out = graph.run_strategic_gate(_state(loop_count=5, tasks_since_gate=2))
        assert out.stop_reason is None, out.stop_reason
        assert out.strategic_gate_status is None, out.strategic_gate_status
    _with_temp_runner_dir(body)


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def test_route_pending_to_decide():
    s = RunnerState(strategic_gate_status="pending")
    assert graph._route_after_strategic_gate(s) == "decide_continue_or_stop"


def test_route_clear_to_chatgpt():
    s = RunnerState(strategic_gate_status=None)
    assert graph._route_after_strategic_gate(s) == "ask_chatgpt_next_task"


def test_stop_reason_constant_surfaces_in_decide():
    s = RunnerState(stop_reason=STRATEGIC_GATE_STOP)
    out = graph.decide_continue_or_stop(s)
    assert out.status == "stopped", out.status


def test_node_is_wired_into_graph():
    nodes = list(graph.build_graph().get_graph().nodes)
    assert "run_strategic_gate" in nodes, nodes


# ---------------------------------------------------------------------------
# Wiring
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_interval_zero_never_triggers,
        test_interval_negative_never_triggers,
        test_count_increments_before_interval,
        test_triggers_exactly_at_interval,
        test_triggers_past_interval,
        test_interval_one_triggers_every_task,
        test_counter_resets_to_zero_on_trigger,
        test_stop_reason_constant,
        test_format_review_file_contains_loop_count,
        test_format_review_file_no_digest,
        test_node_disabled_when_interval_zero,
        test_node_disabled_when_flag_off,
        test_node_counts_without_triggering,
        test_node_triggers_at_interval_and_blocks,
        test_node_pending_blocks_without_approval,
        test_node_pending_resumes_when_approved,
        test_node_review_file_idempotent,
        test_node_pre_approved_does_not_block,
        test_route_pending_to_decide,
        test_route_clear_to_chatgpt,
        test_stop_reason_constant_surfaces_in_decide,
        test_node_is_wired_into_graph,
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
