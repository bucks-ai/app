"""Unit tests for the graph.check_pending_migrations_if_needed startup node.

This node is the fix for the M4a critical finding: merged additive migrations
under supabase/migrations/ used to sit un-applied forever because nothing
called tools/db_tools.py::apply_pending_migrations. Here we exercise the node
in isolation — db_tools functions are stubbed on the graph module so no real
database or filesystem migrations directory is touched.

Runs standalone (no pytest dependency):

    python tests/test_migrations_wiring_node.py
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import graph
from state import RunnerState

# Silence disk persistence during tests; log_event is swapped per-test below
# so individual tests can assert on what was logged.
graph.update_state = lambda *a, **k: None


_log_calls: list[tuple] = []


def _capture_log(*args, **kwargs):
    _log_calls.append((args, kwargs))


def _event_types() -> list[str]:
    return [args[0] for args, _ in _log_calls]


def _run_node(*, has_database=True, auto_apply=False, pending_result=None,
              additivity_map=None, apply_results=None):
    """Run check_pending_migrations_if_needed with db_tools stubbed out.

    pending_result: dict returned by list_pending_migrations (ToolResult shape).
    additivity_map: {filename: {"additive": bool, "reasons": [...]}}.
    apply_results: {filename: ToolResult-shaped dict} for apply_db_migration_file.
    """
    additivity_map = additivity_map or {}
    apply_results = apply_results or {}

    original_cfg_db_url = graph.cfg.database_url
    original_cfg_direct_url = graph.cfg.direct_database_url
    original_auto_apply = graph.cfg.auto_apply_migrations
    original_repo_path = graph.cfg.repo_path
    original_list_pending = graph.list_pending_migrations
    original_classify = graph.classify_migration_additivity
    original_apply = graph.apply_db_migration_file
    original_log_event = graph.log_event

    class _FakePath:
        """Stand-in for a migration file path — only `.read_text()` and
        `str()` (for the filename) are used by the node."""
        def __init__(self, name):
            self._name = name

        def read_text(self):
            return f"-- {self._name}"

        def __truediv__(self, other):
            return _FakePath(other)

        def __str__(self):
            return f"/fake/repo/supabase/migrations/{self._name}"

    try:
        graph.cfg.database_url = "postgresql://x" if has_database else None
        graph.cfg.direct_database_url = "postgresql://direct" if has_database else None
        graph.cfg.auto_apply_migrations = auto_apply
        graph.cfg.repo_path = "/fake/repo"
        graph.log_event = _capture_log
        _log_calls.clear()

        graph.list_pending_migrations = lambda directory: (
            pending_result if pending_result is not None
            else {"tool": "db_list_pending_migrations", "success": True, "data": {"pending": []}}
        )
        graph.classify_migration_additivity = lambda text: additivity_map.get(text.split()[-1], {"additive": True, "reasons": []})
        graph.apply_db_migration_file = lambda path: apply_results[path.split("/")[-1]]

        # Path(cfg.repo_path) / "supabase/migrations" — patch Path within graph module
        # only for the duration of this call via a lightweight fake that supports
        # `/` and produces filenames read_text() can identify.
        original_path_cls = graph.Path

        class _FakeRootPath:
            def __init__(self, *_a, **_k):
                pass

            def __truediv__(self, other):
                return _FakePath(other)

        graph.Path = _FakeRootPath

        state = RunnerState()
        result = graph.check_pending_migrations_if_needed(state)
        return result
    finally:
        graph.cfg.database_url = original_cfg_db_url
        graph.cfg.direct_database_url = original_cfg_direct_url
        graph.cfg.auto_apply_migrations = original_auto_apply
        graph.cfg.repo_path = original_repo_path
        graph.list_pending_migrations = original_list_pending
        graph.classify_migration_additivity = original_classify
        graph.apply_db_migration_file = original_apply
        graph.log_event = original_log_event
        graph.Path = original_path_cls


# ---------------------------------------------------------------------------
# No database configured — pure no-op
# ---------------------------------------------------------------------------

def test_no_op_without_database():
    _run_node(has_database=False)
    assert _log_calls == []


# ---------------------------------------------------------------------------
# Pending detection — always alerts, regardless of auto-apply
# ---------------------------------------------------------------------------

def test_no_pending_migrations_logs_nothing():
    _run_node(pending_result={"success": True, "data": {"pending": []}})
    assert "migrations_pending" not in _event_types()


def test_pending_migrations_logs_loud_alert_with_filenames():
    _run_node(
        auto_apply=False,
        pending_result={"success": True, "data": {"pending": ["0002_x.sql", "0003_y.sql"]}},
    )
    assert _event_types().count("migrations_pending") == 1
    args, _ = next(c for c in _log_calls if c[0][0] == "migrations_pending")
    payload = args[1]
    assert payload["pending"] == ["0002_x.sql", "0003_y.sql"]
    assert payload["count"] == 2
    assert payload["auto_apply_migrations"] is False


def test_pending_migrations_never_auto_applies_when_flag_off():
    _run_node(
        auto_apply=False,
        pending_result={"success": True, "data": {"pending": ["0002_x.sql"]}},
        additivity_map={"0002_x.sql": {"additive": True, "reasons": []}},
        apply_results={"0002_x.sql": {"success": True, "data": {"sha256": "abc"}}},
    )
    assert "migration_applied" not in _event_types()


def test_list_pending_migrations_error_is_logged_and_does_not_crash():
    _run_node(pending_result={"success": False, "error": "Failed to read _runner_migrations ledger."})
    assert "error" in _event_types()
    assert "migrations_pending" not in _event_types()


# ---------------------------------------------------------------------------
# Auto-apply happy path
# ---------------------------------------------------------------------------

def test_auto_apply_happy_path_applies_all_additive_pending_in_order():
    _run_node(
        auto_apply=True,
        pending_result={"success": True, "data": {"pending": ["0002_x.sql", "0003_y.sql"]}},
        additivity_map={
            "0002_x.sql": {"additive": True, "reasons": []},
            "0003_y.sql": {"additive": True, "reasons": []},
        },
        apply_results={
            "0002_x.sql": {"success": True, "data": {"sha256": "sha-0002"}},
            "0003_y.sql": {"success": True, "data": {"sha256": "sha-0003"}},
        },
    )

    applied_events = [args for args, _ in _log_calls if args[0] == "migration_applied"]
    assert [a[1]["filename"] for a in applied_events] == ["0002_x.sql", "0003_y.sql"]
    assert [a[1]["sha256"] for a in applied_events] == ["sha-0002", "sha-0003"]


# ---------------------------------------------------------------------------
# Guard/gate-blocked refusal — never auto-applies, alerts instead
# ---------------------------------------------------------------------------

def test_guard_blocked_file_is_never_auto_applied():
    _run_node(
        auto_apply=True,
        pending_result={"success": True, "data": {"pending": ["0002_blocked.sql"]}},
        additivity_map={"0002_blocked.sql": {"additive": True, "reasons": []}},
        apply_results={
            "0002_blocked.sql": {
                "success": False,
                "error": "sql_scan_blocked",
                "data": {"scan": {"blocked_terms": ["drop table (without IF EXISTS)"]}},
            },
        },
    )
    assert "migration_applied" not in _event_types()
    assert "migration_auto_apply_blocked" in _event_types()
    args, _ = next(c for c in _log_calls if c[0][0] == "migration_auto_apply_blocked")
    assert args[1]["filename"] == "0002_blocked.sql"
    assert args[1]["reason"] == "sql_scan_blocked"


def test_non_additive_file_is_never_auto_applied():
    # apply_results is intentionally left empty — if apply_db_migration_file
    # were called for a non-additive file, the stub raises KeyError.
    _run_node(
        auto_apply=True,
        pending_result={"success": True, "data": {"pending": ["0002_drop.sql"]}},
        additivity_map={"0002_drop.sql": {"additive": False, "reasons": ["drop statement (table/column/index/policy/etc.)"]}},
    )

    assert "migration_applied" not in _event_types()
    args, _ = next(c for c in _log_calls if c[0][0] == "migration_auto_apply_blocked")
    assert args[1]["filename"] == "0002_drop.sql"
    assert args[1]["reason"] == "non_additive"


def test_non_additive_file_stops_auto_apply_before_later_files():
    """A non-additive file earlier in filename order must block later
    (even additive) files from being auto-applied out of order."""
    # apply_results is intentionally left empty — a KeyError would surface if
    # the later additive file were (wrongly) applied before the check aborts.
    _run_node(
        auto_apply=True,
        pending_result={"success": True, "data": {"pending": ["0002_drop.sql", "0003_additive.sql"]}},
        additivity_map={
            "0002_drop.sql": {"additive": False, "reasons": ["drop statement (table/column/index/policy/etc.)"]},
            "0003_additive.sql": {"additive": True, "reasons": []},
        },
    )

    assert _event_types().count("migration_auto_apply_blocked") == 1
    assert "migration_applied" not in _event_types()


# ---------------------------------------------------------------------------
# Graph structure
# ---------------------------------------------------------------------------

def test_node_present_in_graph():
    assert "check_pending_migrations_if_needed" in graph.graph.nodes


def test_node_wired_between_launch_readiness_and_load_next_task():
    edges = [(e.source, e.target) for e in graph.graph.get_graph().edges]
    assert ("check_launch_readiness_if_needed", "check_pending_migrations_if_needed") in edges
    assert ("check_pending_migrations_if_needed", "load_next_task") in edges


if __name__ == "__main__":
    tests = [
        test_no_op_without_database,
        test_no_pending_migrations_logs_nothing,
        test_pending_migrations_logs_loud_alert_with_filenames,
        test_pending_migrations_never_auto_applies_when_flag_off,
        test_list_pending_migrations_error_is_logged_and_does_not_crash,
        test_auto_apply_happy_path_applies_all_additive_pending_in_order,
        test_guard_blocked_file_is_never_auto_applied,
        test_non_additive_file_is_never_auto_applied,
        test_non_additive_file_stops_auto_apply_before_later_files,
        test_node_present_in_graph,
        test_node_wired_between_launch_readiness_and_load_next_task,
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
