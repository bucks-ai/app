"""Tests for tools/mission_planner.py — pure functions only, no LLM calls."""
import json
import os
import pytest
from pathlib import Path
from unittest.mock import MagicMock, patch


# ── Helpers ───────────────────────────────────────────────────────────────────

def _task(task_id: str, title: str = "", branch: str = "feature/test") -> dict:
    return {"id": task_id, "title": title or task_id, "branch": branch, "status": "queued"}


def _plan(expected_files: list, *, deliverable_exists: bool = False, deliverable_path=None, depends_on=None) -> dict:
    return {
        "expected_files": expected_files,
        "approach": "Test approach.",
        "deliverable_exists": deliverable_exists,
        "deliverable_path": deliverable_path,
        "depends_on": depends_on or [],
    }


# ── detect_conflicts ──────────────────────────────────────────────────────────

class TestDetectConflicts:
    def test_intersecting_file_sets_produce_conflict(self):
        from tools.mission_planner import detect_conflicts

        tasks = [_task("a"), _task("b")]
        plans = {
            "a": _plan(["runner/langgraph/config.py", "runner/langgraph/graph.py"]),
            "b": _plan(["runner/langgraph/config.py"]),
        }
        conflicts = detect_conflicts(tasks, plans)

        assert len(conflicts) == 1
        assert conflicts[0]["task_ids"] == ["a", "b"]
        assert "runner/langgraph/config.py" in conflicts[0]["shared_files"]

    def test_disjoint_file_sets_produce_no_conflict(self):
        from tools.mission_planner import detect_conflicts

        tasks = [_task("a"), _task("b")]
        plans = {
            "a": _plan(["runner/langgraph/config.py"]),
            "b": _plan(["runner/langgraph/tools/new_tool.py"]),
        }
        conflicts = detect_conflicts(tasks, plans)

        assert conflicts == []

    def test_three_tasks_two_pairs_conflicting(self):
        from tools.mission_planner import detect_conflicts

        tasks = [_task("a"), _task("b"), _task("c")]
        plans = {
            "a": _plan(["shared.py", "a_only.py"]),
            "b": _plan(["shared.py", "b_only.py"]),
            "c": _plan(["a_only.py", "c_only.py"]),
        }
        conflicts = detect_conflicts(tasks, plans)

        conflict_pairs = [tuple(c["task_ids"]) for c in conflicts]
        assert ("a", "b") in conflict_pairs
        assert ("a", "c") in conflict_pairs
        assert ("b", "c") not in conflict_pairs

    def test_task_with_no_plan_is_skipped(self):
        from tools.mission_planner import detect_conflicts

        tasks = [_task("a"), _task("b")]
        plans = {"a": _plan(["shared.py"])}  # b has no plan

        conflicts = detect_conflicts(tasks, plans)
        assert conflicts == []

    def test_task_with_empty_file_list_is_skipped(self):
        from tools.mission_planner import detect_conflicts

        tasks = [_task("a"), _task("b")]
        plans = {
            "a": _plan(["shared.py"]),
            "b": _plan([]),  # empty list
        }
        conflicts = detect_conflicts(tasks, plans)
        assert conflicts == []

    def test_no_duplicate_pairs_reported(self):
        from tools.mission_planner import detect_conflicts

        tasks = [_task("a"), _task("b")]
        plans = {
            "a": _plan(["f1.py", "f2.py"]),
            "b": _plan(["f1.py", "f2.py"]),
        }
        conflicts = detect_conflicts(tasks, plans)
        # Should be exactly 1 conflict record, not 2
        assert len(conflicts) == 1


# ── detect_duplicates ─────────────────────────────────────────────────────────

class TestDetectDuplicates:
    def test_plan_reported_duplicate(self):
        from tools.mission_planner import detect_duplicates

        tasks = [_task("a")]
        plans = {"a": _plan([], deliverable_exists=True, deliverable_path="runner/langgraph/tools/foo.py")}

        dups = detect_duplicates(tasks, plans, "/some/repo")

        assert len(dups) == 1
        assert dups[0]["task_id"] == "a"
        assert dups[0]["evidence"] == "plan_reported"

    def test_filesystem_check_duplicate(self, tmp_path):
        from tools.mission_planner import detect_duplicates

        # Create a file that "already exists"
        existing = tmp_path / "runner" / "langgraph" / "tools" / "existing.py"
        existing.parent.mkdir(parents=True)
        existing.write_text("# exists")

        tasks = [_task("a")]
        plans = {"a": _plan([], deliverable_exists=False,
                             deliverable_path="runner/langgraph/tools/existing.py")}

        dups = detect_duplicates(tasks, plans, str(tmp_path))

        assert len(dups) == 1
        assert dups[0]["evidence"] == "filesystem_check"

    def test_no_duplicate_when_file_absent(self, tmp_path):
        from tools.mission_planner import detect_duplicates

        tasks = [_task("a")]
        plans = {"a": _plan([], deliverable_exists=False,
                             deliverable_path="runner/langgraph/tools/new_thing.py")}

        dups = detect_duplicates(tasks, plans, str(tmp_path))
        assert dups == []

    def test_task_without_plan_not_flagged(self, tmp_path):
        from tools.mission_planner import detect_duplicates

        tasks = [_task("a")]
        plans = {}

        dups = detect_duplicates(tasks, plans, str(tmp_path))
        assert dups == []


# ── detect_oversized ─────────────────────────────────────────────────────────

class TestDetectOversized:
    def test_plan_above_threshold_flagged(self):
        from tools.mission_planner import detect_oversized

        plans = {
            "a": _plan([f"file{i}.py" for i in range(12)]),
        }
        oversized = detect_oversized(plans, max_files=10)

        assert len(oversized) == 1
        assert oversized[0]["task_id"] == "a"
        assert oversized[0]["file_count"] == 12

    def test_plan_at_threshold_not_flagged(self):
        from tools.mission_planner import detect_oversized

        plans = {
            "a": _plan([f"file{i}.py" for i in range(10)]),
        }
        oversized = detect_oversized(plans, max_files=10)
        assert oversized == []

    def test_plan_below_threshold_not_flagged(self):
        from tools.mission_planner import detect_oversized

        plans = {"a": _plan(["f.py", "g.py"])}
        oversized = detect_oversized(plans, max_files=10)
        assert oversized == []

    def test_empty_plans_no_oversized(self):
        from tools.mission_planner import detect_oversized

        assert detect_oversized({}, 10) == []


# ── compute_sequential_order ──────────────────────────────────────────────────

class TestComputeSequentialOrder:
    def test_conflicting_tasks_ordered_sequentially(self):
        from tools.mission_planner import compute_sequential_order

        tasks = [_task("a"), _task("b")]
        plans = {
            "a": _plan(["config.py"]),
            "b": _plan(["config.py"]),
        }
        ordered = compute_sequential_order(tasks, plans)

        ids = [t["id"] for t in ordered]
        # a claims config.py first, b depends on a
        assert ids.index("a") < ids.index("b")

    def test_disjoint_tasks_preserve_original_order(self):
        from tools.mission_planner import compute_sequential_order

        tasks = [_task("a"), _task("b"), _task("c")]
        plans = {
            "a": _plan(["a.py"]),
            "b": _plan(["b.py"]),
            "c": _plan(["c.py"]),
        }
        ordered = compute_sequential_order(tasks, plans)
        ids = [t["id"] for t in ordered]
        assert ids == ["a", "b", "c"]

    def test_empty_task_list(self):
        from tools.mission_planner import compute_sequential_order

        assert compute_sequential_order([], {}) == []

    def test_single_task(self):
        from tools.mission_planner import compute_sequential_order

        tasks = [_task("a")]
        plans = {"a": _plan(["f.py"])}
        ordered = compute_sequential_order(tasks, plans)
        assert [t["id"] for t in ordered] == ["a"]

    def test_chain_ordering(self):
        """a→b→c chain: a owns f1, b owns f1+f2, c owns f2."""
        from tools.mission_planner import compute_sequential_order

        tasks = [_task("a"), _task("b"), _task("c")]
        plans = {
            "a": _plan(["f1.py"]),
            "b": _plan(["f1.py", "f2.py"]),  # b depends on a (shares f1)
            "c": _plan(["f2.py"]),             # c depends on b (shares f2)
        }
        ordered = compute_sequential_order(tasks, plans)
        ids = [t["id"] for t in ordered]
        assert ids.index("a") < ids.index("b")
        assert ids.index("b") < ids.index("c")

    def test_reordering_when_later_task_has_priority_file(self):
        """If b appears before a but a should run first (it owns the file),
        the topological sort should still put a before b."""
        from tools.mission_planner import compute_sequential_order

        # b is listed first in original order but claims a file that a also wants
        # Actually: the FIRST task to claim a file owns it. So b owns it, a depends on b.
        tasks = [_task("b"), _task("a")]
        plans = {
            "b": _plan(["shared.py"]),
            "a": _plan(["shared.py"]),
        }
        ordered = compute_sequential_order(tasks, plans)
        ids = [t["id"] for t in ordered]
        # b came first in the input, owns "shared.py"; a depends on b
        assert ids.index("b") < ids.index("a")


# ── parse_planning_response ───────────────────────────────────────────────────

class TestParsePlanningResponse:
    def test_valid_json_parsed(self):
        from tools.mission_planner import parse_planning_response

        raw = json.dumps({
            "expected_files": ["a.py", "b.py"],
            "approach": "Do it.",
            "deliverable_exists": False,
            "deliverable_path": None,
            "depends_on": [],
        })
        result = parse_planning_response(raw)
        assert result["expected_files"] == ["a.py", "b.py"]
        assert result["deliverable_exists"] is False

    def test_markdown_fences_stripped(self):
        from tools.mission_planner import parse_planning_response

        raw = "```json\n{\"expected_files\": [\"x.py\"]}\n```"
        result = parse_planning_response(raw)
        assert result["expected_files"] == ["x.py"]

    def test_empty_response_returns_empty_dict(self):
        from tools.mission_planner import parse_planning_response

        assert parse_planning_response("") == {}
        assert parse_planning_response("   ") == {}

    def test_invalid_json_returns_empty_dict(self):
        from tools.mission_planner import parse_planning_response

        assert parse_planning_response("not json at all") == {}
        assert parse_planning_response("{broken") == {}

    def test_expected_files_capped_at_max(self):
        from tools.mission_planner import parse_planning_response, _MAX_EXPECTED_FILES

        files = [f"file{i}.py" for i in range(30)]
        raw = json.dumps({"expected_files": files, "approach": "x"})
        result = parse_planning_response(raw)
        assert len(result["expected_files"]) == _MAX_EXPECTED_FILES

    def test_non_dict_response_returns_empty(self):
        from tools.mission_planner import parse_planning_response

        assert parse_planning_response("[1, 2, 3]") == {}


# ── planning failure fallback ─────────────────────────────────────────────────

class TestPlanningFailureFallback:
    def test_api_error_logs_and_continues(self, tmp_path, monkeypatch):
        """When the LLM call fails, the task's plan is omitted but analysis runs
        on whatever plans were collected (graceful degradation)."""
        import tools.mission_planner as mp
        import config as cfg_mod
        monkeypatch.setattr(mp, "_PLANS_DIR", tmp_path / "plans")

        def _fail_call(prompt, model, api_key):
            return {"plan": {}, "error": "connection refused"}

        monkeypatch.setattr(mp, "call_planning_model", _fail_call)

        from config import RunnerConfig
        monkeypatch.setattr(cfg_mod, "get_config",
                            lambda: RunnerConfig(mission_planning_max_files=10))

        tasks = [_task("a"), _task("b")]
        result = mp.run_mission_planning_pass(
            tasks=tasks,
            repo_path=str(tmp_path),
            model="claude-haiku-4-5-20251001",
            api_key=None,
        )

        # No plans collected but structure is valid
        assert "plans" in result
        assert "conflicts" in result
        assert "reordered_task_ids" in result
        # No crash — graceful degradation
        assert result["conflicts"] == []

    def test_parse_failure_logs_and_continues(self, tmp_path, monkeypatch):
        """When the LLM returns garbage JSON, the task's plan is skipped."""
        import tools.mission_planner as mp
        import config as cfg_mod
        monkeypatch.setattr(mp, "_PLANS_DIR", tmp_path / "plans")

        def _bad_json(prompt, model, api_key):
            return {"plan": {}, "error": None}  # parse_planning_response returned {}

        monkeypatch.setattr(mp, "call_planning_model", _bad_json)

        from config import RunnerConfig
        monkeypatch.setattr(cfg_mod, "get_config",
                            lambda: RunnerConfig(mission_planning_max_files=10))

        tasks = [_task("a")]
        result = mp.run_mission_planning_pass(
            tasks=tasks, repo_path=str(tmp_path),
            model="claude-haiku-4-5-20251001", api_key=None,
        )
        assert result["plans"] == {}


# ── disabled pass ─────────────────────────────────────────────────────────────

class TestDisabledPass:
    def test_already_planned_tasks_skipped(self, tmp_path, monkeypatch):
        """When all tasks already have plans, no LLM call is made."""
        import tools.mission_planner as mp
        import config as cfg_mod
        monkeypatch.setattr(mp, "_PLANS_DIR", tmp_path / "plans")

        call_count = {"n": 0}

        def _count_call(prompt, model, api_key):
            call_count["n"] += 1
            return {"plan": {}, "error": None}

        monkeypatch.setattr(mp, "call_planning_model", _count_call)

        from config import RunnerConfig
        monkeypatch.setattr(cfg_mod, "get_config",
                            lambda: RunnerConfig(mission_planning_max_files=10))

        mp.save_plan("a", {"expected_files": ["x.py"], "approach": "X"})
        mp.save_plan("b", {"expected_files": ["y.py"], "approach": "Y"})

        tasks = [_task("a"), _task("b")]
        mp.run_mission_planning_pass(
            tasks=tasks, repo_path=str(tmp_path),
            model="claude-haiku-4-5-20251001", api_key=None,
        )

        assert call_count["n"] == 0


# ── save / load plans ─────────────────────────────────────────────────────────

class TestPlanPersistence:
    def test_round_trip(self, tmp_path, monkeypatch):
        import tools.mission_planner as mp
        monkeypatch.setattr(mp, "_PLANS_DIR", tmp_path / "plans")

        plan = {"expected_files": ["a.py"], "approach": "do it"}
        mp.save_plan("task-1", plan)
        loaded = mp.load_plan("task-1")
        assert loaded == plan

    def test_missing_plan_returns_none(self, tmp_path, monkeypatch):
        import tools.mission_planner as mp
        monkeypatch.setattr(mp, "_PLANS_DIR", tmp_path / "plans")

        assert mp.load_plan("nonexistent") is None

    def test_load_all_plans_returns_only_existing(self, tmp_path, monkeypatch):
        import tools.mission_planner as mp
        monkeypatch.setattr(mp, "_PLANS_DIR", tmp_path / "plans")

        mp.save_plan("x", {"expected_files": []})
        result = mp.load_all_plans(["x", "y"])
        assert "x" in result
        assert "y" not in result


# ── build_planning_prompt ─────────────────────────────────────────────────────

class TestBuildPlanningPrompt:
    def test_includes_task_fields(self):
        from tools.mission_planner import build_planning_prompt

        task = {
            "id": "t1", "title": "Add auth", "type": "backend",
            "branch": "feature/auth", "description": "implement auth"
        }
        prompt = build_planning_prompt(task, ["t2", "t3"])
        assert "t1" in prompt
        assert "Add auth" in prompt
        assert "t2" in prompt
        assert "t3" in prompt

    def test_description_truncated(self):
        from tools.mission_planner import build_planning_prompt

        long_desc = "x" * 1000
        task = {"id": "t", "title": "T", "description": long_desc}
        prompt = build_planning_prompt(task, [])
        # The description in the prompt should be at most 500 chars
        assert "x" * 501 not in prompt
