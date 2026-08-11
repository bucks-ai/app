"""Tests for tools/mission_briefing.py.

Covers:
  PART 1 — build_mission_briefing:
    - mid-mission task: ALREADY DONE and STILL TO COME both populated
    - first task: ALREADY DONE is empty
    - no-mission task: block omitted entirely (empty string returned)
    - 5-entry cap: only the 5 most recent completed tasks are shown

  PART 2 — extract_file_paths / check_artifacts_present / should_precheck_task:
    - skips when all named artifacts exist
    - dispatches when any artifact is missing
    - dispatches when no concrete artifacts are named
    - dispatches when the force_dispatch override is set

All tests are pure — no worker invocation, no disk writes, no network calls.
Filesystem tests use tmp_path (pytest) to create real files.
"""
import pytest
from tools.mission_briefing import (
    build_mission_briefing,
    extract_file_paths,
    check_artifacts_present,
    should_precheck_task,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_task(
    task_id: str,
    title: str,
    status: str = "queued",
    mission: str = "Test Mission",
    summary: str = "",
) -> dict:
    t: dict = {
        "id": task_id,
        "title": title,
        "status": status,
        "mission": mission,
    }
    if summary:
        t["summary"] = summary
    return t


_SUMMARY_WITH_FILES = """\
Files Created:
- runner/langgraph/tools/foo.py
Files Modified:
- runner/langgraph/graph.py
- Check Result: pass
- Commit Result: abc1234
- Push Result: done
- SQL Required: no
- SQL File Path: N/A
- Credentials Needed: none
- Resources Needed: none
- Known Limitations: none
- Next Task: none
"""


# ---------------------------------------------------------------------------
# PART 1 — build_mission_briefing
# ---------------------------------------------------------------------------

class TestMidMissionTask:
    """A task in the middle of a mission: some done, some to come."""

    def _make_queue(self) -> tuple[dict, list[dict]]:
        completed_1 = _make_task("t1", "Setup database schema", status="complete", summary=_SUMMARY_WITH_FILES)
        completed_2 = _make_task("t2", "Add API endpoints", status="complete")
        current = _make_task("t3", "Add frontend components", status="queued")
        future_1 = _make_task("t4", "Write integration tests", status="queued")
        future_2 = _make_task("t5", "Deploy to production", status="queued")
        queue = [completed_1, completed_2, current, future_1, future_2]
        return current, queue

    def test_briefing_includes_mission_name(self):
        current, queue = self._make_queue()
        block = build_mission_briefing(current, queue)
        assert "Test Mission" in block

    def test_briefing_includes_position(self):
        current, queue = self._make_queue()
        block = build_mission_briefing(current, queue)
        assert "task 3 of 5" in block

    def test_briefing_includes_already_done_section(self):
        current, queue = self._make_queue()
        block = build_mission_briefing(current, queue)
        assert "ALREADY DONE" in block
        assert "Setup database schema" in block
        assert "Add API endpoints" in block

    def test_briefing_includes_still_to_come_section(self):
        current, queue = self._make_queue()
        block = build_mission_briefing(current, queue)
        assert "STILL TO COME" in block
        assert "Write integration tests" in block
        assert "Deploy to production" in block

    def test_current_task_not_in_still_to_come(self):
        current, queue = self._make_queue()
        block = build_mission_briefing(current, queue)
        # The current task's title must not appear in still-to-come
        still_section = block.split("STILL TO COME")[-1]
        assert "Add frontend components" not in still_section

    def test_already_done_labels_worker_reported(self):
        current, queue = self._make_queue()
        block = build_mission_briefing(current, queue)
        assert "REPORTED BY THE WORKER" in block

    def test_already_done_includes_file_list(self):
        current, queue = self._make_queue()
        block = build_mission_briefing(current, queue)
        assert "runner/langgraph/tools/foo.py" in block

    def test_preauthorised_line_present(self):
        current, queue = self._make_queue()
        block = build_mission_briefing(current, queue)
        assert "pre-authorised" in block


class TestFirstTask:
    """The first task in a mission: ALREADY DONE should be empty."""

    def test_already_done_is_empty_for_first_task(self):
        current = _make_task("t1", "Setup database schema", status="queued")
        future_1 = _make_task("t2", "Add API endpoints", status="queued")
        queue = [current, future_1]
        block = build_mission_briefing(current, queue)
        assert "ALREADY DONE" in block
        assert "none — you are the first task" in block

    def test_position_is_1(self):
        current = _make_task("t1", "Setup database schema", status="queued")
        future_1 = _make_task("t2", "Add API endpoints", status="queued")
        queue = [current, future_1]
        block = build_mission_briefing(current, queue)
        assert "task 1 of 2" in block


class TestNoMissionTask:
    """Tasks with no mission field: the briefing block is omitted entirely."""

    def test_no_mission_field_returns_empty_string(self):
        task = {"id": "t1", "title": "Some task", "status": "queued"}
        queue = [task]
        block = build_mission_briefing(task, queue)
        assert block == ""

    def test_empty_mission_field_returns_empty_string(self):
        task = {"id": "t1", "title": "Some task", "status": "queued", "mission": ""}
        queue = [task]
        block = build_mission_briefing(task, queue)
        assert block == ""

    def test_no_mission_does_not_contaminate_prompt(self):
        task = {"id": "t1", "title": "Some task", "status": "queued"}
        block = build_mission_briefing(task, [])
        # A non-mission prompt must be byte-identical — the block must add nothing.
        assert block == ""


class TestFiveEntryCap:
    """When more than 5 tasks are complete, only the 5 most recent are shown."""

    def test_cap_at_five_completed(self):
        completed = [
            _make_task(f"t{i}", f"Task {i}", status="complete")
            for i in range(1, 8)  # 7 completed tasks
        ]
        current = _make_task("t8", "Current task", status="queued")
        queue = completed + [current]
        block = build_mission_briefing(current, queue)

        # Only 5 shown
        assert "Task 3" in block  # 3rd from start, but we show LAST 5
        assert "Task 4" in block
        assert "Task 5" in block
        assert "Task 6" in block
        assert "Task 7" in block
        # Task 1 and 2 are NOT shown (too old)
        assert "[t1]" not in block
        assert "[t2]" not in block

    def test_rest_count_reported(self):
        completed = [
            _make_task(f"t{i}", f"Task {i}", status="complete")
            for i in range(1, 9)  # 8 completed tasks
        ]
        current = _make_task("t9", "Current task", status="queued")
        queue = completed + [current]
        block = build_mission_briefing(current, queue)
        assert "3 earlier task(s) also complete" in block

    def test_no_rest_count_when_five_or_fewer(self):
        completed = [
            _make_task(f"t{i}", f"Task {i}", status="complete")
            for i in range(1, 6)  # exactly 5
        ]
        current = _make_task("t6", "Current task", status="queued")
        queue = completed + [current]
        block = build_mission_briefing(current, queue)
        assert "earlier task(s) also complete" not in block


# ---------------------------------------------------------------------------
# PART 2 — precheck: extract_file_paths / check_artifacts_present
# ---------------------------------------------------------------------------

class TestExtractFilePaths:
    def test_extracts_simple_path(self):
        desc = "Add a new module at tools/mission_briefing.py"
        assert "tools/mission_briefing.py" in extract_file_paths(desc)

    def test_extracts_multiple_paths(self):
        desc = "Create tools/foo.py and tests/test_foo.py"
        paths = extract_file_paths(desc)
        assert "tools/foo.py" in paths
        assert "tests/test_foo.py" in paths

    def test_empty_description_returns_empty_list(self):
        assert extract_file_paths("") == []

    def test_no_paths_in_description_returns_empty(self):
        desc = "Implement the login page with username and password fields."
        assert extract_file_paths(desc) == []

    def test_url_not_extracted(self):
        desc = "See https://example.com/docs/guide.html for more details."
        paths = extract_file_paths(desc)
        # The URL fragment should not be captured as a path
        assert not any("example.com" in p for p in paths)

    def test_unknown_extension_not_extracted(self):
        desc = "Read the runner/langgraph/docs/notes.xyz file"
        paths = extract_file_paths(desc)
        assert not any("notes.xyz" in p for p in paths)


class TestCheckArtifactsPresent:
    def test_all_present_returns_true(self, tmp_path):
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "foo.py").write_text("# hello")
        (tmp_path / "tests").mkdir()
        (tmp_path / "tests" / "test_foo.py").write_text("# hello")

        result = check_artifacts_present(
            ["tools/foo.py", "tests/test_foo.py"], str(tmp_path)
        )
        assert result["all_present"] is True
        assert result["missing"] == []

    def test_any_missing_returns_false(self, tmp_path):
        (tmp_path / "tools").mkdir()
        (tmp_path / "tools" / "foo.py").write_text("# hello")
        # tests/test_foo.py does NOT exist

        result = check_artifacts_present(
            ["tools/foo.py", "tests/test_foo.py"], str(tmp_path)
        )
        assert result["all_present"] is False
        assert "tests/test_foo.py" in result["missing"]
        assert "tools/foo.py" in result["present"]

    def test_empty_file_list_returns_all_present_false(self, tmp_path):
        result = check_artifacts_present([], str(tmp_path))
        assert result["all_present"] is False

    def test_extra_search_dirs_checked(self, tmp_path):
        # File lives in a second search root
        extra = tmp_path / "extra"
        extra.mkdir()
        (extra / "tools").mkdir()
        (extra / "tools" / "bar.py").write_text("# bar")

        result = check_artifacts_present(
            ["tools/bar.py"], str(tmp_path),
            extra_search_dirs=[str(extra)]
        )
        assert result["all_present"] is True


class TestNoneNamed:
    """When no concrete artifacts are named, always dispatch (all_present=False)."""

    def test_no_named_artifacts_returns_all_present_false(self, tmp_path):
        paths = extract_file_paths("Add authentication logic to the login form")
        result = check_artifacts_present(paths, str(tmp_path))
        assert result["all_present"] is False

    def test_description_with_no_paths_extracts_nothing(self):
        paths = extract_file_paths("Implement a retry mechanism with exponential backoff.")
        assert paths == []


class TestForceDispatchOverride:
    """When force_dispatch is set on the task, should_precheck_task returns False."""

    def test_force_dispatch_disables_precheck(self):
        task = {"id": "t1", "force_dispatch": True, "description": "Create tools/foo.py"}
        assert should_precheck_task(task) is False

    def test_no_force_dispatch_enables_precheck(self):
        task = {"id": "t1", "description": "Create tools/foo.py"}
        assert should_precheck_task(task) is True

    def test_force_dispatch_false_enables_precheck(self):
        task = {"id": "t1", "force_dispatch": False, "description": "Create tools/foo.py"}
        assert should_precheck_task(task) is True
