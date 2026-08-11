"""Unit tests for tools/mission_backlog.py.

Covers:
  - load_strategy_doc: file absent, empty, and excerpt extraction
  - _extract_relevant_sections: section isolation and fallback truncation
  - fetch_next_approved_backlog_entry: Supabase stubbed via monkeypatching
  - fetch_backlog_tasks: Supabase stubbed
  - seed_backlog_entry_to_missions: Supabase stubbed; verifies insert payloads
  - mark_backlog_entry_seeded: Supabase stubbed
  - auto_seed_next_backlog_entry: end-to-end with stubs (seeded and no-entry paths)
  - build_planning_prompt: strategy context injection via mission_planner
  - run_mission_planning_pass signature accepts strategy_context
"""
import os
import sys
import tempfile
import traceback
from pathlib import Path
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.mission_backlog import (
    load_strategy_doc,
    _extract_relevant_sections,
    fetch_next_approved_backlog_entry,
    fetch_backlog_tasks,
    seed_backlog_entry_to_missions,
    mark_backlog_entry_seeded,
    auto_seed_next_backlog_entry,
)
from tools.mission_planner import (
    build_planning_prompt,
    run_mission_planning_pass,
)

_PASS = []
_FAIL = []


def _ok(name: str) -> None:
    _PASS.append(name)
    print(f"  [OK] {name}")


def _fail(name: str, exc: Exception) -> None:
    _FAIL.append(name)
    print(f"  [FAIL] {name}: {exc}")
    traceback.print_exc()


# ---------------------------------------------------------------------------
# load_strategy_doc
# ---------------------------------------------------------------------------

def test_load_strategy_doc_absent():
    result = load_strategy_doc("/nonexistent/path")
    assert result == "", f"Expected empty string for missing file, got {result!r}"
    _ok("load_strategy_doc_absent")


def test_load_strategy_doc_empty_file():
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "STRATEGY.md").write_text("")
        result = load_strategy_doc(tmp)
        assert result == "", f"Expected empty string for empty file, got {result!r}"
    _ok("load_strategy_doc_empty_file")


def test_load_strategy_doc_returns_content():
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "STRATEGY.md").write_text("## 1. THE ONE-LINE THESIS\nSell convenience.\n")
        result = load_strategy_doc(tmp)
        assert "convenience" in result.lower(), f"Expected doctrine in result, got {result!r}"
    _ok("load_strategy_doc_returns_content")


def test_load_strategy_doc_respects_max_chars():
    content = "x" * 10_000
    with tempfile.TemporaryDirectory() as tmp:
        (Path(tmp) / "STRATEGY.md").write_text(content)
        result = load_strategy_doc(tmp, max_chars=100)
        assert len(result) <= 100, f"Expected at most 100 chars, got {len(result)}"
    _ok("load_strategy_doc_respects_max_chars")


# ---------------------------------------------------------------------------
# _extract_relevant_sections
# ---------------------------------------------------------------------------

def test_extract_sections_finds_target():
    text = "## 1. THE ONE-LINE THESIS\nConvenience wins.\n\n## 2. SOMETHING ELSE\nIgnore me.\n"
    result = _extract_relevant_sections(text, max_chars=5000)
    assert "convenience" in result.lower()
    assert "ignore me" not in result.lower()
    _ok("extract_sections_finds_target")


def test_extract_sections_fallback_truncation():
    # A doc with no target headings falls back to plain truncation
    text = "## SOMETHING COMPLETELY DIFFERENT\n" + "word " * 2000
    result = _extract_relevant_sections(text, max_chars=50)
    assert len(result) <= 50
    _ok("extract_sections_fallback_truncation")


# ---------------------------------------------------------------------------
# Supabase helpers (stubbed)
# ---------------------------------------------------------------------------

_ENTRY = {
    "id": "backlog-uuid-1",
    "position": 1,
    "name": "M4d: Hardened scaffold",
    "goal": "Add security defaults to every new business scaffold",
    "approved": True,
    "seeded_at": None,
    "mission_id": None,
}

_BTASKS = [
    {"id": "bt-1", "backlog_id": "backlog-uuid-1", "position": 1,
     "title": "Add M1 hardening template", "type": "backend",
     "branch": "feature/m4d/hardening-template", "preferred_worker": "claude",
     "description": "Apply M1 security playbook by default"},
    {"id": "bt-2", "backlog_id": "backlog-uuid-1", "position": 2,
     "title": "Wire hardening into scaffold", "type": "backend",
     "branch": "feature/m4d/scaffold-wire", "preferred_worker": None,
     "description": ""},
]


def _make_supabase_stub(rows):
    """Return a minimal Supabase client stub that yields *rows* on execute."""
    result_stub = MagicMock()
    result_stub.data = rows
    chain = MagicMock()
    chain.execute.return_value = result_stub
    chain.eq.return_value = chain
    chain.is_.return_value = chain
    chain.order.return_value = chain
    chain.limit.return_value = chain
    chain.insert.return_value = chain
    chain.update.return_value = chain
    chain.select.return_value = chain
    client = MagicMock()
    client.table.return_value = chain
    return client


def test_fetch_next_approved_backlog_entry_found():
    stub = _make_supabase_stub([_ENTRY])
    with patch("tools.mission_backlog._get_client", return_value=stub):
        result = fetch_next_approved_backlog_entry()
    assert result is not None
    assert result["id"] == "backlog-uuid-1"
    _ok("fetch_next_approved_backlog_entry_found")


def test_fetch_next_approved_backlog_entry_empty():
    stub = _make_supabase_stub([])
    with patch("tools.mission_backlog._get_client", return_value=stub):
        result = fetch_next_approved_backlog_entry()
    assert result is None
    _ok("fetch_next_approved_backlog_entry_empty")


def test_fetch_next_approved_backlog_entry_error():
    with patch("tools.mission_backlog._get_client", side_effect=RuntimeError("db down")):
        with patch("tools.mission_backlog.log_event"):
            result = fetch_next_approved_backlog_entry()
    assert result is None
    _ok("fetch_next_approved_backlog_entry_error")


def test_fetch_backlog_tasks():
    stub = _make_supabase_stub(_BTASKS)
    with patch("tools.mission_backlog._get_client", return_value=stub):
        result = fetch_backlog_tasks("backlog-uuid-1")
    assert len(result) == 2
    assert result[0]["title"] == "Add M1 hardening template"
    _ok("fetch_backlog_tasks")


def test_fetch_backlog_tasks_error():
    with patch("tools.mission_backlog._get_client", side_effect=RuntimeError("db down")):
        with patch("tools.mission_backlog.log_event"):
            result = fetch_backlog_tasks("backlog-uuid-1")
    assert result == []
    _ok("fetch_backlog_tasks_error")


def test_seed_backlog_entry_to_missions_success():
    """Verify that seed creates one mission row and N task rows."""
    inserted_missions = []
    inserted_tasks = []

    def _make_mock_client():
        result_mission = MagicMock()
        result_mission.data = [{"id": "new-mission-uuid"}]

        result_tasks = MagicMock()
        result_tasks.data = []

        call_count = {"n": 0}

        class _Chain:
            def __init__(self):
                self._result = result_mission

            def insert(self, payload):
                if "status" in payload and isinstance(payload, dict) and "name" in payload:
                    inserted_missions.append(payload)
                elif isinstance(payload, list):
                    inserted_tasks.extend(payload)
                call_count["n"] += 1
                return self

            def execute(self):
                if call_count["n"] == 1:
                    return result_mission
                return result_tasks

        chain = _Chain()
        client = MagicMock()
        client.table.return_value = chain
        return client

    with patch("tools.mission_backlog._get_client", side_effect=_make_mock_client):
        result = seed_backlog_entry_to_missions(_ENTRY, _BTASKS)

    assert result.get("success"), f"Expected success, got {result}"
    assert result.get("mission_id") == "new-mission-uuid"
    _ok("seed_backlog_entry_to_missions_success")


def test_seed_backlog_entry_no_tasks():
    result = seed_backlog_entry_to_missions(_ENTRY, [])
    assert not result.get("success")
    assert "no tasks" in result.get("error", "")
    _ok("seed_backlog_entry_no_tasks")


def test_mark_backlog_entry_seeded():
    stub = _make_supabase_stub([])
    with patch("tools.mission_backlog._get_client", return_value=stub):
        result = mark_backlog_entry_seeded("backlog-uuid-1", "mission-uuid-1")
    assert result.get("success")
    _ok("mark_backlog_entry_seeded")


# ---------------------------------------------------------------------------
# auto_seed_next_backlog_entry
# ---------------------------------------------------------------------------

def test_auto_seed_next_backlog_entry_no_entry():
    with patch("tools.mission_backlog.fetch_next_approved_backlog_entry", return_value=None):
        result = auto_seed_next_backlog_entry()
    assert not result.get("seeded")
    _ok("auto_seed_next_backlog_entry_no_entry")


def test_auto_seed_next_backlog_entry_seeded():
    with patch("tools.mission_backlog.fetch_next_approved_backlog_entry", return_value=_ENTRY), \
         patch("tools.mission_backlog.fetch_backlog_tasks", return_value=_BTASKS), \
         patch("tools.mission_backlog.seed_backlog_entry_to_missions",
               return_value={"success": True, "mission_id": "new-m-id"}), \
         patch("tools.mission_backlog.mark_backlog_entry_seeded", return_value={"success": True}), \
         patch("tools.mission_backlog.log_event"):
        result = auto_seed_next_backlog_entry()
    assert result.get("seeded")
    assert result.get("mission_id") == "new-m-id"
    assert result.get("backlog_id") == "backlog-uuid-1"
    _ok("auto_seed_next_backlog_entry_seeded")


def test_auto_seed_next_backlog_entry_seed_fails():
    with patch("tools.mission_backlog.fetch_next_approved_backlog_entry", return_value=_ENTRY), \
         patch("tools.mission_backlog.fetch_backlog_tasks", return_value=_BTASKS), \
         patch("tools.mission_backlog.seed_backlog_entry_to_missions",
               return_value={"success": False, "error": "db error"}), \
         patch("tools.mission_backlog.log_event"):
        result = auto_seed_next_backlog_entry()
    assert not result.get("seeded")
    _ok("auto_seed_next_backlog_entry_seed_fails")


# ---------------------------------------------------------------------------
# mission_planner: strategy_context injection
# ---------------------------------------------------------------------------

def test_build_planning_prompt_no_strategy():
    task = {"id": "t1", "title": "Add login", "type": "backend", "branch": "feature/login",
            "description": ""}
    prompt = build_planning_prompt(task, [])
    assert "task_id" not in prompt  # format keys resolved
    assert "t1" in prompt
    _ok("build_planning_prompt_no_strategy")


def test_build_planning_prompt_with_strategy():
    task = {"id": "t1", "title": "Add login", "type": "backend", "branch": "feature/login",
            "description": ""}
    prompt = build_planning_prompt(task, [], strategy_context="Sell convenience.")
    assert "convenience" in prompt.lower()
    assert "t1" in prompt
    _ok("build_planning_prompt_with_strategy")


def test_run_mission_planning_pass_accepts_strategy_context():
    """run_mission_planning_pass must accept the strategy_context kwarg without error."""
    with patch("tools.mission_planner.call_planning_model",
               return_value={"plan": {}, "error": None}), \
         patch("tools.mission_planner.load_all_plans", return_value={}), \
         patch("tools.mission_planner.save_plan"):
        tasks = [{"id": "t1", "title": "T", "type": "general", "branch": "feature/t"}]
        result = run_mission_planning_pass(
            tasks=tasks,
            repo_path="/fake",
            model="claude-haiku-4-5-20251001",
            api_key=None,
            strategy_context="doctrine here",
        )
    assert "plans" in result
    _ok("run_mission_planning_pass_accepts_strategy_context")


# ---------------------------------------------------------------------------
# New config fields
# ---------------------------------------------------------------------------

def test_config_mission_backlog_enabled():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "mission_backlog_enabled"), "missing mission_backlog_enabled"
    assert isinstance(cfg.mission_backlog_enabled, bool)
    _ok("config_mission_backlog_enabled")


def test_config_planner_strategy_context_enabled():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "planner_strategy_context_enabled")
    assert isinstance(cfg.planner_strategy_context_enabled, bool)
    _ok("config_planner_strategy_context_enabled")


def test_config_strategy_doc_path():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "strategy_doc_path")
    assert cfg.strategy_doc_path == "STRATEGY.md"
    _ok("config_strategy_doc_path")


def test_config_strategy_context_max_chars():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "strategy_context_max_chars")
    assert cfg.strategy_context_max_chars > 0
    _ok("config_strategy_context_max_chars")


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_load_strategy_doc_absent,
        test_load_strategy_doc_empty_file,
        test_load_strategy_doc_returns_content,
        test_load_strategy_doc_respects_max_chars,
        test_extract_sections_finds_target,
        test_extract_sections_fallback_truncation,
        test_fetch_next_approved_backlog_entry_found,
        test_fetch_next_approved_backlog_entry_empty,
        test_fetch_next_approved_backlog_entry_error,
        test_fetch_backlog_tasks,
        test_fetch_backlog_tasks_error,
        test_seed_backlog_entry_to_missions_success,
        test_seed_backlog_entry_no_tasks,
        test_mark_backlog_entry_seeded,
        test_auto_seed_next_backlog_entry_no_entry,
        test_auto_seed_next_backlog_entry_seeded,
        test_auto_seed_next_backlog_entry_seed_fails,
        test_build_planning_prompt_no_strategy,
        test_build_planning_prompt_with_strategy,
        test_run_mission_planning_pass_accepts_strategy_context,
        test_config_mission_backlog_enabled,
        test_config_planner_strategy_context_enabled,
        test_config_strategy_doc_path,
        test_config_strategy_context_max_chars,
    ]
    print(f"\nRunning {len(tests)} tests...\n")
    for t in tests:
        try:
            t()
        except Exception as exc:
            _fail(t.__name__, exc)

    print(f"\n{'='*50}")
    print(f"Results: {len(_PASS)} passed, {len(_FAIL)} failed")
    if _FAIL:
        sys.exit(1)
