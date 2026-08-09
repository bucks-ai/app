"""M4c.0: one blocked task must not stop nine healthy ones.

Runs standalone (no pytest dependency):

    python tests/test_gate_skip_and_continue.py

Each task-judging gate is driven to its blocking verdict and asserted to leave
``stop_reason`` clear — the task is marked failed/blocked and the loop moves on.
The gates that judge the *run* (strategic pause, session spend cap, stale run,
repeated failures) still halt, and are asserted to keep doing so.
"""
import os
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import graph
from state import RunnerState
from tools import task_tools

# Captured per-test — see the note in test_gate_authority.py on why the stub
# is not installed at import time.
_EVENTS = []


def _with_stubs(fn, **cfg_overrides):
    """Run fn(marks) with task-queue writes captured and cfg overridden."""
    marks = {"failed": [], "blocked": []}
    originals = {
        "mark_task_failed": graph.mark_task_failed,
        "mark_task_blocked": graph.mark_task_blocked,
        "get_diff_text": graph.get_diff_text,
        "log_event": graph.log_event,
        "update_state": graph.update_state,
    }
    graph.mark_task_failed = lambda tid, err: marks["failed"].append((tid, err))
    graph.mark_task_blocked = lambda tid, reason: marks["blocked"].append((tid, reason))
    graph.get_diff_text = lambda *a, **k: ""
    graph.log_event = lambda event, payload=None, **k: _EVENTS.append((event, payload or {}))
    graph.update_state = lambda *a, **k: None
    saved_cfg = {k: getattr(graph.cfg, k) for k in cfg_overrides}
    for k, v in cfg_overrides.items():
        setattr(graph.cfg, k, v)
    _EVENTS.clear()
    try:
        return fn(marks)
    finally:
        for name, value in originals.items():
            setattr(graph, name, value)
        for k, v in saved_cfg.items():
            setattr(graph.cfg, k, v)


def _blocked_events():
    return [p for e, p in _EVENTS if e == "gate_block_task_scoped"]


# ---------------------------------------------------------------------------
# Task-judging gates: skip the task, keep the loop alive
# ---------------------------------------------------------------------------

def test_acceptance_criteria_strict_skips_the_task_only():
    def body(marks):
        state = RunnerState(current_task_id="t1", current_task={"id": "t1", "title": "x"})
        out = graph.check_acceptance_criteria(state)
        assert out.acceptance_criteria_status == "failed", out.acceptance_criteria_status
        assert out.stop_reason is None, out.stop_reason
        assert marks["failed"] and marks["failed"][0][0] == "t1"
        assert out.gate_skipped_task_count == 1
        assert _blocked_events()[0]["authority"] == "task_record"
    _with_stubs(
        body,
        acceptance_criteria_gate_enabled=True,
        acceptance_criteria_strict_mode=True,
        gate_block_scope="proportionate",
    )


def test_definition_of_done_strict_skips_the_task_only():
    def body(marks):
        state = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1", "title": "x"},
            worker_result={"success": True, "output": ""},
            worker_summary={},
        )
        out = graph.check_definition_of_done(state)
        assert out.definition_of_done_status == "failed", out.definition_of_done_status
        assert out.stop_reason is None, out.stop_reason
        assert marks["failed"] and marks["failed"][0][0] == "t1"
        assert _blocked_events()[0]["authority"] == "check_script"
    _with_stubs(
        body,
        definition_of_done_gate_enabled=True,
        definition_of_done_strict_mode=True,
        gate_block_scope="proportionate",
    )


def test_merge_approval_pending_skips_the_task_only():
    original_dir = graph._RUNNER_DIR

    def body(marks):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "outbox").mkdir()
            (root / "inbox").mkdir()
            graph._RUNNER_DIR = root
            try:
                state = RunnerState(
                    current_task_id="t1",
                    current_task={"id": "t1", "title": "migrate the payments schema"},
                    worker_result={"success": True},
                    worker_summary={},
                    check_passed=True,
                )
                out = graph.check_merge_approval_if_needed(state)
            finally:
                graph._RUNNER_DIR = original_dir
        assert out.merge_approval_status == "pending", out.merge_approval_status
        assert out.stop_reason is None, out.stop_reason
        # The task must leave the "running" state, or it is stranded forever.
        assert marks["blocked"] and marks["blocked"][0][0] == "t1", marks
        assert _blocked_events()[0]["authority"] == "human_approval_file"
    _with_stubs(
        body,
        risk_based_merge_approval_enabled=True,
        merge_approval_policy="require_approval_on_high",
        gate_block_scope="proportionate",
        auto_approve_enabled=False,
    )


# ---------------------------------------------------------------------------
# Run-judging gates: still halt
# ---------------------------------------------------------------------------

def test_strategic_gate_still_halts_the_whole_run():
    original_dir = graph._RUNNER_DIR

    def body(marks):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "outbox").mkdir()
            (root / "inbox").mkdir()
            graph._RUNNER_DIR = root
            try:
                state = RunnerState(strategic_gate_status="pending", strategic_gate_at_loop=5)
                out = graph.run_strategic_gate(state)
            finally:
                graph._RUNNER_DIR = original_dir
        assert out.stop_reason == graph.STRATEGIC_GATE_STOP, out.stop_reason
        payloads = [p for e, p in _EVENTS if e == "loop_blocked_on_strategic_gate"]
        assert payloads and payloads[0]["authority"] == "human_approval_file", payloads
    _with_stubs(body, strategic_gate_enabled=True, strategic_pause_interval=5)


def test_legacy_policy_restores_the_whole_run_halt():
    def body(marks):
        state = RunnerState(current_task_id="t1", current_task={"id": "t1", "title": "x"})
        out = graph.check_acceptance_criteria(state)
        assert out.stop_reason == "missing_acceptance_criteria", out.stop_reason
    _with_stubs(
        body,
        acceptance_criteria_gate_enabled=True,
        acceptance_criteria_strict_mode=True,
        gate_block_scope="loop",
    )


# ---------------------------------------------------------------------------
# Requeue safety — a consumed unblock signal must not spin the loop
# ---------------------------------------------------------------------------

def _with_temp_tasks(tasks, fn):
    saved = (task_tools.load_tasks, task_tools.save_tasks)
    store = {"tasks": tasks}
    task_tools.load_tasks = lambda: store["tasks"]
    task_tools.save_tasks = lambda t: store.update(tasks=t)
    try:
        return fn(store)
    finally:
        task_tools.load_tasks, task_tools.save_tasks = saved


def test_resource_fulfillment_requeues_a_blocked_task():
    def body(store):
        with tempfile.TemporaryDirectory() as d:
            inbox = Path(d)
            (inbox / "t1_resources_provided.txt").write_text("ok")
            assert task_tools.requeue_fulfilled_blocked_tasks(inbox) == ["t1"]
        assert store["tasks"][0]["status"] == "queued"
    _with_temp_tasks([{"id": "t1", "status": "blocked"}], body)


def test_merge_approval_file_also_requeues_a_blocked_task():
    """The merge gate now blocks its task, so its approval file must unblock it."""
    def body(store):
        with tempfile.TemporaryDirectory() as d:
            inbox = Path(d)
            (inbox / "t1_merge_approved.txt").write_text("ok")
            assert task_tools.requeue_fulfilled_blocked_tasks(inbox) == ["t1"]
        assert store["tasks"][0]["status"] == "queued"
    _with_temp_tasks([{"id": "t1", "status": "blocked"}], body)


def test_an_unblock_signal_is_consumed_only_once():
    """Without this, a task that blocks again for the same reason would be
    requeued, re-run and re-blocked forever now that the loop no longer stops."""
    def body(store):
        with tempfile.TemporaryDirectory() as d:
            inbox = Path(d)
            (inbox / "t1_resources_provided.txt").write_text("ok")
            assert task_tools.requeue_fulfilled_blocked_tasks(inbox) == ["t1"]
            # The task blocks again on the next pass; the file is still there.
            store["tasks"][0]["status"] = "blocked"
            assert task_tools.requeue_fulfilled_blocked_tasks(inbox) == []
    _with_temp_tasks([{"id": "t1", "status": "blocked"}], body)


if __name__ == "__main__":
    tests = [
        test_acceptance_criteria_strict_skips_the_task_only,
        test_definition_of_done_strict_skips_the_task_only,
        test_merge_approval_pending_skips_the_task_only,
        test_strategic_gate_still_halts_the_whole_run,
        test_legacy_policy_restores_the_whole_run_halt,
        test_resource_fulfillment_requeues_a_blocked_task,
        test_merge_approval_file_also_requeues_a_blocked_task,
        test_an_unblock_signal_is_consumed_only_once,
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
