"""Tests for planner drift prevention.

Covers:
- ask_for_next_task includes completed task titles in the prompt.
- Prompt is unchanged when completed_tasks is None or empty.
- Completed task list is capped at 10 entries to avoid bloat.
- _completed_tasks() helper returns only complete-status tasks.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

# Silence log_event during tests.
import tools.log_tools as _lt
_lt.log_event = lambda *a, **k: None

from workers.chatgpt_worker import ChatGPTWorker, _NEXT_TASK_PROMPT
from state import WorkerResult


# ---------------------------------------------------------------------------
# ask_for_next_task prompt content
# ---------------------------------------------------------------------------

def _captured_prompt(completed_tasks=None) -> str:
    """Run ask_for_next_task with a stub that captures the prompt."""
    captured = []

    class _FakeWorker(ChatGPTWorker):
        def run_worker_prompt(self, prompt: str, task: dict) -> WorkerResult:
            captured.append(prompt)
            # Return a valid task JSON so json.loads succeeds.
            return WorkerResult(
                worker="chatgpt", mode="api", success=True,
                output='{"id": "t1", "title": "Build something", "type": "backend", "branch": "feature/t1", "status": "queued"}',
            )

    worker = _FakeWorker()
    worker.ask_for_next_task("latest summary", completed_tasks=completed_tasks)
    return captured[0] if captured else ""


def test_prompt_contains_completed_task_titles():
    completed = [
        {"id": "task-001", "title": "Build login page"},
        {"id": "task-002", "title": "Add stripe webhook"},
    ]
    prompt = _captured_prompt(completed_tasks=completed)
    assert "Build login page" in prompt
    assert "Add stripe webhook" in prompt


def test_prompt_contains_do_not_repropose_instruction():
    completed = [{"id": "task-001", "title": "Build login page"}]
    prompt = _captured_prompt(completed_tasks=completed)
    assert "do not" in prompt.lower() or "NOT" in prompt


def test_prompt_unchanged_when_no_completed_tasks():
    prompt_no_completed = _captured_prompt(completed_tasks=None)
    prompt_empty = _captured_prompt(completed_tasks=[])
    # Neither should contain a "completed tasks" section
    assert "already completed" not in prompt_no_completed.lower()
    assert "already completed" not in prompt_empty.lower()


def test_prompt_caps_completed_tasks_at_10():
    completed = [{"id": f"task-{i}", "title": f"Task {i}"} for i in range(20)]
    prompt = _captured_prompt(completed_tasks=completed)
    # Only the last 10 tasks should appear; earlier ones should not
    assert "Task 19" in prompt   # last
    assert "Task 10" in prompt   # 10th from end
    assert "Task 9" not in prompt  # 11th from end — capped out


# ---------------------------------------------------------------------------
# _completed_tasks helper in graph.py
# ---------------------------------------------------------------------------

def test_completed_tasks_returns_only_complete_status(monkeypatch):
    import graph
    monkeypatch.setattr(graph, "load_tasks", lambda: [
        {"id": "a", "title": "Done task", "status": "complete"},
        {"id": "b", "title": "Running task", "status": "running"},
        {"id": "c", "title": "Failed task", "status": "failed"},
        {"id": "d", "title": "Queued task", "status": "queued"},
    ])
    result = graph._completed_tasks()
    assert len(result) == 1
    assert result[0]["id"] == "a"


def test_completed_tasks_returns_id_and_title(monkeypatch):
    import graph
    monkeypatch.setattr(graph, "load_tasks", lambda: [
        {"id": "x1", "title": "My task", "status": "complete", "extra": "ignored"},
    ])
    result = graph._completed_tasks()
    assert result == [{"id": "x1", "title": "My task"}]


def test_completed_tasks_empty_when_none_complete(monkeypatch):
    import graph
    monkeypatch.setattr(graph, "load_tasks", lambda: [
        {"id": "a", "title": "Queued", "status": "queued"},
    ])
    assert graph._completed_tasks() == []


if __name__ == "__main__":
    import traceback
    tests = [
        test_prompt_contains_completed_task_titles,
        test_prompt_contains_do_not_repropose_instruction,
        test_prompt_unchanged_when_no_completed_tasks,
        test_prompt_caps_completed_tasks_at_10,
        test_completed_tasks_returns_only_complete_status,
        test_completed_tasks_returns_id_and_title,
        test_completed_tasks_empty_when_none_complete,
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
