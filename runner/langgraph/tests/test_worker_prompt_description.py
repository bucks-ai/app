"""Unit tests for task description propagation into the worker prompt.

Runs standalone (no pytest dependency):

    python tests/test_worker_prompt_description.py

Covers:
  - ``generate_worker_prompt`` appends the task's ``description`` field to the
    prompt when present.
  - The prompt is unchanged (no stray "Description" section) when the task
    carries no description.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import graph
from state import RunnerState

# Silence flight recorder and disk persistence during all tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None


def _make_state(task: dict) -> RunnerState:
    return RunnerState(current_task=task, current_task_id=task.get("id"))


def test_prompt_includes_description_when_present():
    task = {
        "id": "t1",
        "title": "Add login page",
        "type": "frontend",
        "branch": "feature/t1",
        "description": "Wire up the login form to the auth API.",
    }
    out = graph.generate_worker_prompt(_make_state(task))
    prompt = out.messages[-1]["content"]
    assert "Description:" in prompt
    assert "Wire up the login form to the auth API." in prompt


def test_prompt_omits_description_section_when_absent():
    task = {
        "id": "t2",
        "title": "Add auth API",
        "type": "backend",
        "branch": "feature/t2",
    }
    out = graph.generate_worker_prompt(_make_state(task))
    prompt = out.messages[-1]["content"]
    assert "Description:" not in prompt


def test_prompt_omits_description_section_when_blank():
    task = {
        "id": "t3",
        "title": "Add auth API",
        "type": "backend",
        "branch": "feature/t3",
        "description": "   ",
    }
    out = graph.generate_worker_prompt(_make_state(task))
    prompt = out.messages[-1]["content"]
    assert "Description:" not in prompt


def test_prompt_still_includes_core_fields_with_description():
    task = {
        "id": "t4",
        "title": "Add auth API",
        "type": "backend",
        "branch": "feature/t4",
        "description": "Implement /login and /logout endpoints.",
    }
    out = graph.generate_worker_prompt(_make_state(task))
    prompt = out.messages[-1]["content"]
    assert "Task: Add auth API" in prompt
    assert "Type: backend" in prompt
    assert "Branch: feature/t4" in prompt


if __name__ == "__main__":
    tests = [
        test_prompt_includes_description_when_present,
        test_prompt_omits_description_section_when_absent,
        test_prompt_omits_description_section_when_blank,
        test_prompt_still_includes_core_fields_with_description,
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
