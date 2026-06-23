"""Tests for batch stability fixes.

Covers:
- ask_chatgpt_next_task skips the planner when queued tasks already exist.
- update_logs_and_state resets all per-task state fields so stale status from
  one task cannot bleed into routing decisions for the next task.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import graph
from state import RunnerState

# Silence I/O during tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None


# ---------------------------------------------------------------------------
# ask_chatgpt_next_task — skips when queue has tasks
# ---------------------------------------------------------------------------

def _base_state() -> RunnerState:
    return RunnerState(status="running")


def test_ask_next_skips_when_queued_task_exists(monkeypatch):
    """Planner must NOT be called when a queued task is already in the queue."""
    planner_called = []

    monkeypatch.setattr(graph, "get_next_queued_task", lambda: {"id": "queued-task"})

    class _FakePlanner:
        def ask_for_next_task(self, *a, **kw):
            planner_called.append(True)
            return None

    monkeypatch.setattr(graph, "ChatGPTWorker", lambda: _FakePlanner())

    state = graph.ask_chatgpt_next_task(_base_state())

    assert planner_called == [], "planner must not be consulted when queue is non-empty"


def test_ask_next_calls_planner_when_queue_empty(monkeypatch):
    """Planner IS called when the queue is empty."""
    planner_called = []

    monkeypatch.setattr(graph, "get_next_queued_task", lambda: None)
    monkeypatch.setattr(graph, "_completed_tasks", lambda: [])
    monkeypatch.setattr(graph, "add_task", lambda t: None)
    # Ensure strict seeded-queue mode does not short-circuit the planner call,
    # regardless of what the runtime env has configured.
    monkeypatch.setattr(graph.cfg, "seeded_mission_queue_strict", False)

    class _FakePlanner:
        def ask_for_next_task(self, *a, **kw):
            planner_called.append(True)
            return None

    monkeypatch.setattr(graph, "ChatGPTWorker", lambda: _FakePlanner())

    graph.ask_chatgpt_next_task(_base_state())

    assert planner_called == [True], "planner must be called when queue is empty"


def test_ask_next_skips_on_stop_reason(monkeypatch):
    planner_called = []

    class _FakePlanner:
        def ask_for_next_task(self, *a, **kw):
            planner_called.append(True)
            return None

    monkeypatch.setattr(graph, "ChatGPTWorker", lambda: _FakePlanner())

    s = _base_state()
    s.stop_reason = "deploy_failed"
    graph.ask_chatgpt_next_task(s)

    assert planner_called == [], "planner must not be called when stop_reason is set"


def test_ask_next_skips_on_retry_pending(monkeypatch):
    planner_called = []

    class _FakePlanner:
        def ask_for_next_task(self, *a, **kw):
            planner_called.append(True)
            return None

    monkeypatch.setattr(graph, "ChatGPTWorker", lambda: _FakePlanner())

    s = _base_state()
    s.retry_pending = True
    graph.ask_chatgpt_next_task(s)

    assert planner_called == [], "planner must not be called when retry_pending"


# ---------------------------------------------------------------------------
# update_logs_and_state — per-task state reset
# ---------------------------------------------------------------------------

def _done_state_with_task(task_id: str = "t1") -> RunnerState:
    return RunnerState(
        current_task_id=task_id,
        current_task={"id": task_id, "title": "Demo task", "branch": f"feature/{task_id}"},
        current_worker="claude",
        current_branch=f"feature/{task_id}",
        worker_result={"success": True, "worker": "claude"},
        check_passed=True,
        acceptance_criteria_status="warned",
        definition_of_done_status="warned",
        code_review_status="passed",
        merge_approval_status="skipped",
        merge_risk_level="low",
        worker_summary={"check_result": True},
    )


def test_update_resets_acceptance_criteria_status(monkeypatch):
    monkeypatch.setattr(graph, "mark_task_complete", lambda tid, s: None)
    monkeypatch.setattr(graph, "evaluate_task_repetition", lambda *a, **k: {"attempt_count": 1, "blocked": False, "stop_reason": None})
    monkeypatch.setattr(graph, "evaluate_error_repetition", lambda *a, **k: {"blocked": False})
    monkeypatch.setattr(graph, "evaluate_cost_budget", lambda **k: {"session_cost": 0.0, "task_cost": 0.0, "blocked": False})

    s = _done_state_with_task()
    s.acceptance_criteria_status = "warned"
    out = graph.update_logs_and_state(s)
    assert out.acceptance_criteria_status is None


def test_update_resets_definition_of_done_status(monkeypatch):
    monkeypatch.setattr(graph, "mark_task_complete", lambda tid, s: None)
    monkeypatch.setattr(graph, "evaluate_task_repetition", lambda *a, **k: {"attempt_count": 1, "blocked": False, "stop_reason": None})
    monkeypatch.setattr(graph, "evaluate_error_repetition", lambda *a, **k: {"blocked": False})
    monkeypatch.setattr(graph, "evaluate_cost_budget", lambda **k: {"session_cost": 0.0, "task_cost": 0.0, "blocked": False})

    s = _done_state_with_task()
    s.definition_of_done_status = "passed"
    out = graph.update_logs_and_state(s)
    assert out.definition_of_done_status is None


def test_update_resets_current_task_and_worker(monkeypatch):
    monkeypatch.setattr(graph, "mark_task_complete", lambda tid, s: None)
    monkeypatch.setattr(graph, "evaluate_task_repetition", lambda *a, **k: {"attempt_count": 1, "blocked": False, "stop_reason": None})
    monkeypatch.setattr(graph, "evaluate_error_repetition", lambda *a, **k: {"blocked": False})
    monkeypatch.setattr(graph, "evaluate_cost_budget", lambda **k: {"session_cost": 0.0, "task_cost": 0.0, "blocked": False})

    s = _done_state_with_task()
    out = graph.update_logs_and_state(s)

    assert out.current_task is None
    assert out.current_task_id is None
    assert out.current_worker is None
    assert out.current_branch is None


def test_update_resets_worker_summary(monkeypatch):
    monkeypatch.setattr(graph, "mark_task_complete", lambda tid, s: None)
    monkeypatch.setattr(graph, "evaluate_task_repetition", lambda *a, **k: {"attempt_count": 1, "blocked": False, "stop_reason": None})
    monkeypatch.setattr(graph, "evaluate_error_repetition", lambda *a, **k: {"blocked": False})
    monkeypatch.setattr(graph, "evaluate_cost_budget", lambda **k: {"session_cost": 0.0, "task_cost": 0.0, "blocked": False})

    s = _done_state_with_task()
    out = graph.update_logs_and_state(s)
    assert out.worker_summary is None


# ---------------------------------------------------------------------------
# Stale DoD status must not corrupt routing for the next task's failed worker
# ---------------------------------------------------------------------------

def test_stale_dod_failed_does_not_block_next_task_route():
    """If DoD gate is skipped (worker failed) stale 'failed' status from prior
    task must not route the loop to decide_continue_or_stop."""
    s = RunnerState()
    # Worker failed this task — DoD gate skips without touching status.
    # Simulate stale "failed" coming from the *previous* task being gone (reset).
    s.definition_of_done_status = None  # should be cleared by update_logs_and_state
    route = graph._route_after_definition_of_done(s)
    assert route == "request_resources_if_needed"


if __name__ == "__main__":
    import traceback
    tests = [
        test_ask_next_skips_when_queued_task_exists,
        test_ask_next_calls_planner_when_queue_empty,
        test_ask_next_skips_on_stop_reason,
        test_ask_next_skips_on_retry_pending,
        test_update_resets_acceptance_criteria_status,
        test_update_resets_definition_of_done_status,
        test_update_resets_current_task_and_worker,
        test_update_resets_worker_summary,
        test_stale_dod_failed_does_not_block_next_task_route,
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
