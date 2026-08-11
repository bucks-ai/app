"""Unit tests for the auto-approval policy (M4c).

Runs standalone:
    python tests/test_auto_approval.py

Covers the pure helpers in tools/auto_approval.py, the config field, and
the graph-node integrations for merge approval, strategic gate, and SQL
approval.  Also covers auto_requeue_credential_satisfied_tasks in
tools/task_tools.py.
"""
import os
import sys
import tempfile
import traceback
from pathlib import Path

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.auto_approval import (
    is_destructive_diff,
    should_auto_approve_merge,
    should_auto_approve_sql,
    should_auto_approve_strategic,
)

_EVENTS = []


# ---------------------------------------------------------------------------
# is_destructive_diff
# ---------------------------------------------------------------------------

def test_drop_table_is_destructive():
    assert is_destructive_diff("DROP TABLE users;")


def test_truncate_is_destructive():
    assert is_destructive_diff("TRUNCATE TABLE sessions;")


def test_delete_from_is_destructive():
    assert is_destructive_diff("DELETE FROM logs WHERE created_at < now() - interval '90 days';")


def test_drop_database_is_destructive():
    assert is_destructive_diff("DROP DATABASE myapp_staging;")


def test_drop_schema_is_destructive():
    assert is_destructive_diff("DROP SCHEMA public CASCADE;")


def test_alter_table_drop_column_is_destructive():
    assert is_destructive_diff("ALTER TABLE users DROP COLUMN legacy_id;")


def test_create_table_is_not_destructive():
    assert not is_destructive_diff("CREATE TABLE new_feature (id uuid PRIMARY KEY);")


def test_add_column_is_not_destructive():
    assert not is_destructive_diff("ALTER TABLE users ADD COLUMN avatar_url text;")


def test_insert_is_not_destructive():
    assert not is_destructive_diff("INSERT INTO settings (key, value) VALUES ('theme', 'dark');")


def test_empty_diff_is_not_destructive():
    assert not is_destructive_diff("")
    assert not is_destructive_diff(None)


def test_python_diff_is_not_destructive():
    diff = "+def delete_from_cache(key):\n+    cache.pop(key, None)\n"
    assert not is_destructive_diff(diff), "Python code mentioning 'delete_from' is not SQL"


# ---------------------------------------------------------------------------
# should_auto_approve_merge
# ---------------------------------------------------------------------------

def _decision(risk_level="high", score=4, factors=None):
    return {
        "risk_level": risk_level,
        "skipped": False,
        "passed": False,
        "requires_human": True,
        "approved": False,
        "classification": {"risk_level": risk_level, "score": score, "reasons": [], "factors": factors or {}},
        "issues": ["merge requires human approval"],
    }


def test_high_risk_non_destructive_is_auto_approved():
    """A high-risk score alone does not block auto-approval."""
    assert should_auto_approve_merge(_decision(risk_level="high"))


def test_medium_risk_non_destructive_is_auto_approved():
    assert should_auto_approve_merge(_decision(risk_level="medium"))


def test_low_risk_non_destructive_is_auto_approved():
    assert should_auto_approve_merge(_decision(risk_level="low"))


def test_destructive_sql_factor_blocks_auto_approval():
    """When classify_merge_risk flagged destructive SQL, auto-approve is blocked."""
    d = _decision(factors={"destructive_sql": True})
    assert not should_auto_approve_merge(d)


def test_destructive_diff_text_blocks_auto_approval():
    """Belt-and-suspenders: destructive SQL in the diff text also blocks."""
    assert not should_auto_approve_merge(_decision(), diff_text="DROP TABLE users;")


def test_clean_diff_with_high_risk_keywords_is_approved():
    clean_diff = "+def authenticate(user, token):\n+    return verify(token)\n"
    assert should_auto_approve_merge(_decision(risk_level="high"), diff_text=clean_diff)


# ---------------------------------------------------------------------------
# should_auto_approve_sql
# ---------------------------------------------------------------------------

def test_additive_sql_is_auto_approved():
    sql = "CREATE TABLE IF NOT EXISTS events (id uuid PRIMARY KEY, payload jsonb);"
    assert should_auto_approve_sql(sql)


def test_add_column_sql_is_auto_approved():
    sql = "ALTER TABLE users ADD COLUMN stripe_customer_id text;"
    assert should_auto_approve_sql(sql)


def test_drop_table_sql_blocks_auto_approval():
    assert not should_auto_approve_sql("DROP TABLE legacy_data;")


def test_truncate_sql_blocks_auto_approval():
    assert not should_auto_approve_sql("TRUNCATE TABLE sessions;")


def test_delete_from_sql_blocks_auto_approval():
    assert not should_auto_approve_sql("DELETE FROM audit_log WHERE age > 365;")


def test_empty_sql_is_auto_approved():
    assert should_auto_approve_sql("")
    assert should_auto_approve_sql(None)


# ---------------------------------------------------------------------------
# should_auto_approve_strategic
# ---------------------------------------------------------------------------

def test_strategic_always_approved():
    assert should_auto_approve_strategic() is True


# ---------------------------------------------------------------------------
# Config field
# ---------------------------------------------------------------------------

def test_config_has_auto_approve_field():
    from config import RunnerConfig
    cfg = RunnerConfig()
    assert hasattr(cfg, "auto_approve_enabled")
    assert isinstance(cfg.auto_approve_enabled, bool)


def test_config_auto_approve_enabled_by_default():
    import unittest.mock as mock
    with mock.patch.dict(os.environ, {}, clear=False):
        os.environ.pop("AUTO_APPROVE_ENABLED", None)
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.auto_approve_enabled is True


def test_config_auto_approve_can_be_disabled():
    import unittest.mock as mock
    with mock.patch.dict(os.environ, {"AUTO_APPROVE_ENABLED": "false"}):
        from config import RunnerConfig
        cfg = RunnerConfig()
        assert cfg.auto_approve_enabled is False


# ---------------------------------------------------------------------------
# Graph node: merge approval auto-approve
# ---------------------------------------------------------------------------

def _with_merge_stubs(fn, **cfg_overrides):
    import graph
    from state import RunnerState
    import tools.task_tools as task_tools

    _EVENTS.clear()
    originals = {
        "mark_task_blocked": graph.mark_task_blocked,
        "get_diff_text": graph.get_diff_text,
        "log_event": graph.log_event,
        "update_state": graph.update_state,
    }
    graph.mark_task_blocked = lambda tid, reason: None
    graph.get_diff_text = lambda *a, **k: ""
    graph.log_event = lambda event, payload=None, **k: _EVENTS.append((event, payload or {}))
    graph.update_state = lambda *a, **k: None
    saved_cfg = {k: getattr(graph.cfg, k) for k in cfg_overrides}
    for k, v in cfg_overrides.items():
        setattr(graph.cfg, k, v)
    try:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "outbox").mkdir()
            (root / "inbox").mkdir()
            original_runner_dir = graph._RUNNER_DIR
            graph._RUNNER_DIR = root
            try:
                return fn(root / "outbox", root / "inbox")
            finally:
                graph._RUNNER_DIR = original_runner_dir
    finally:
        for name, value in originals.items():
            setattr(graph, name, value)
        for k, v in saved_cfg.items():
            setattr(graph.cfg, k, v)


def test_high_risk_merge_auto_approved_when_enabled():
    """A high-risk merge is auto-approved when AUTO_APPROVE_ENABLED=true."""
    import graph
    from state import RunnerState

    def body(outbox, inbox):
        state = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1", "title": "migrate the payments schema"},
            worker_result={"success": True},
            worker_summary={},
            check_passed=True,
        )
        out = graph.check_merge_approval_if_needed(state)
        assert out.merge_approval_status == "approved", out.merge_approval_status
        assert out.stop_reason is None, out.stop_reason
        # Inbox file written
        assert (inbox / "t1_merge_approved.txt").exists()
        # Event fired
        events = [e for e, _ in _EVENTS if e == "merge_auto_approved"]
        assert events, _EVENTS

    _with_merge_stubs(
        body,
        risk_based_merge_approval_enabled=True,
        merge_approval_policy="require_approval_on_high",
        auto_approve_enabled=True,
    )


def test_destructive_merge_not_auto_approved():
    """A merge with DROP TABLE in the diff must NOT be auto-approved."""
    import graph
    from state import RunnerState

    def body(outbox, inbox):
        graph.get_diff_text = lambda *a, **k: "DROP TABLE users;"
        state = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1", "title": "drop legacy table", "high_risk": True},
            worker_result={"success": True},
            worker_summary={},
            check_passed=True,
        )
        out = graph.check_merge_approval_if_needed(state)
        assert out.merge_approval_status == "pending", out.merge_approval_status
        assert not (inbox / "t1_merge_approved.txt").exists()

    _with_merge_stubs(
        body,
        risk_based_merge_approval_enabled=True,
        merge_approval_policy="always_require",
        auto_approve_enabled=True,
    )


def test_merge_blocked_when_auto_approve_disabled():
    """When AUTO_APPROVE_ENABLED=false, approval must still be requested."""
    import graph
    from state import RunnerState

    def body(outbox, inbox):
        state = RunnerState(
            current_task_id="t1",
            current_task={"id": "t1", "title": "migrate the payments schema"},
            worker_result={"success": True},
            worker_summary={},
            check_passed=True,
        )
        out = graph.check_merge_approval_if_needed(state)
        assert out.merge_approval_status == "pending", out.merge_approval_status
        assert not (inbox / "t1_merge_approved.txt").exists()

    _with_merge_stubs(
        body,
        risk_based_merge_approval_enabled=True,
        merge_approval_policy="require_approval_on_high",
        auto_approve_enabled=False,
    )


# ---------------------------------------------------------------------------
# Graph node: strategic gate auto-approve
# ---------------------------------------------------------------------------

def _with_strategic_stubs(fn, **cfg_overrides):
    import graph

    _EVENTS.clear()
    original_log = graph.log_event
    original_update = graph.update_state
    graph.log_event = lambda event, payload=None, **k: _EVENTS.append((event, payload or {}))
    graph.update_state = lambda *a, **k: None
    saved_cfg = {k: getattr(graph.cfg, k) for k in cfg_overrides}
    for k, v in cfg_overrides.items():
        setattr(graph.cfg, k, v)
    try:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "outbox").mkdir()
            (root / "inbox").mkdir()
            original_runner_dir = graph._RUNNER_DIR
            graph._RUNNER_DIR = root
            try:
                return fn(root / "outbox", root / "inbox")
            finally:
                graph._RUNNER_DIR = original_runner_dir
    finally:
        graph.log_event = original_log
        graph.update_state = original_update
        for k, v in saved_cfg.items():
            setattr(graph.cfg, k, v)


def test_strategic_gate_auto_approved_when_enabled():
    """When auto_approve_enabled, the gate writes the inbox file and does not stop."""
    import graph
    from state import RunnerState
    from tools.strategic_decision_gate import STRATEGIC_GATE_STOP

    def body(outbox, inbox):
        state = RunnerState(loop_count=7, strategic_tasks_since_gate=4)
        out = graph.run_strategic_gate(state)
        assert out.stop_reason is None, out.stop_reason
        assert out.strategic_gate_status is None, out.strategic_gate_status
        # Review file still written for observability
        assert (outbox / "strategic_review_7.txt").exists()
        # Inbox approval file written
        assert (inbox / "strategic_review_7_approved.txt").exists()
        events = [e for e, _ in _EVENTS if e == "strategic_gate_auto_approved"]
        assert events, _EVENTS

    _with_strategic_stubs(
        body,
        strategic_gate_enabled=True,
        strategic_pause_interval=5,
        auto_approve_enabled=True,
    )


def test_strategic_gate_blocks_when_auto_approve_disabled():
    """When AUTO_APPROVE_ENABLED=false, the gate must still block."""
    import graph
    from state import RunnerState
    from tools.strategic_decision_gate import STRATEGIC_GATE_STOP

    def body(outbox, inbox):
        state = RunnerState(loop_count=7, strategic_tasks_since_gate=4)
        out = graph.run_strategic_gate(state)
        assert out.stop_reason == STRATEGIC_GATE_STOP, out.stop_reason
        assert out.strategic_gate_status == "pending", out.strategic_gate_status
        assert not (inbox / "strategic_review_7_approved.txt").exists()

    _with_strategic_stubs(
        body,
        strategic_gate_enabled=True,
        strategic_pause_interval=5,
        auto_approve_enabled=False,
    )


# ---------------------------------------------------------------------------
# auto_requeue_credential_satisfied_tasks
# ---------------------------------------------------------------------------

def test_auto_requeue_creates_inbox_file_when_credentials_satisfied():
    from tools.task_tools import auto_requeue_credential_satisfied_tasks
    import tools.task_tools as task_tools

    saved = (task_tools.load_tasks, task_tools.save_tasks)
    store = {"tasks": [{"id": "t1", "status": "blocked", "error": "awaiting resources/credentials"}]}
    task_tools.load_tasks = lambda: store["tasks"]
    task_tools.save_tasks = lambda t: store.update(tasks=t)
    try:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inbox = root / "inbox"
            outbox = root / "outbox"
            inbox.mkdir()
            outbox.mkdir()

            # Write a resource request that only needs STRIPE_API_KEY
            (outbox / "t1_resource_request.txt").write_text(
                "# Resource / Credential Request — task: t1\n"
                "\n"
                "## Credentials needed\n"
                "- STRIPE_API_KEY\n"
            )

            # Credential is now available
            available = {"STRIPE_API_KEY"}
            created = auto_requeue_credential_satisfied_tasks(inbox, outbox, available)

            assert "t1" in created, created
            assert (inbox / "t1_resources_provided.txt").exists()
    finally:
        task_tools.load_tasks, task_tools.save_tasks = saved


def test_auto_requeue_skips_when_credentials_missing():
    from tools.task_tools import auto_requeue_credential_satisfied_tasks
    import tools.task_tools as task_tools

    saved = (task_tools.load_tasks, task_tools.save_tasks)
    store = {"tasks": [{"id": "t1", "status": "blocked"}]}
    task_tools.load_tasks = lambda: store["tasks"]
    task_tools.save_tasks = lambda t: store.update(tasks=t)
    try:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inbox = root / "inbox"
            outbox = root / "outbox"
            inbox.mkdir()
            outbox.mkdir()

            (outbox / "t1_resource_request.txt").write_text(
                "## Credentials needed\n"
                "- RESEND_API_KEY\n"
            )

            created = auto_requeue_credential_satisfied_tasks(inbox, outbox, {"STRIPE_API_KEY"})
            assert created == [], created
            assert not (inbox / "t1_resources_provided.txt").exists()
    finally:
        task_tools.load_tasks, task_tools.save_tasks = saved


def test_auto_requeue_skips_when_non_credential_resources_present():
    """Tasks blocked on non-credential resources cannot be auto-satisfied."""
    from tools.task_tools import auto_requeue_credential_satisfied_tasks
    import tools.task_tools as task_tools

    saved = (task_tools.load_tasks, task_tools.save_tasks)
    store = {"tasks": [{"id": "t1", "status": "blocked"}]}
    task_tools.load_tasks = lambda: store["tasks"]
    task_tools.save_tasks = lambda t: store.update(tasks=t)
    try:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inbox = root / "inbox"
            outbox = root / "outbox"
            inbox.mkdir()
            outbox.mkdir()

            # Both a credential (satisfied) AND a non-credential resource
            (outbox / "t1_resource_request.txt").write_text(
                "## Credentials needed\n"
                "- RESEND_API_KEY\n"
                "\n"
                "## Resources needed\n"
                "- access to the Resend dashboard\n"
            )

            created = auto_requeue_credential_satisfied_tasks(
                inbox, outbox, {"RESEND_API_KEY"}
            )
            assert created == [], "non-credential resource prevents auto-requeue"
    finally:
        task_tools.load_tasks, task_tools.save_tasks = saved


def test_auto_requeue_skips_already_requeued_tasks():
    """A task with unblock_requeued_at is not touched again."""
    from tools.task_tools import auto_requeue_credential_satisfied_tasks
    import tools.task_tools as task_tools

    saved = (task_tools.load_tasks, task_tools.save_tasks)
    store = {"tasks": [{"id": "t1", "status": "blocked", "unblock_requeued_at": "2026-01-01T00:00:00"}]}
    task_tools.load_tasks = lambda: store["tasks"]
    task_tools.save_tasks = lambda t: store.update(tasks=t)
    try:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inbox = root / "inbox"
            outbox = root / "outbox"
            inbox.mkdir()
            outbox.mkdir()

            (outbox / "t1_resource_request.txt").write_text(
                "## Credentials needed\n- STRIPE_API_KEY\n"
            )

            created = auto_requeue_credential_satisfied_tasks(inbox, outbox, {"STRIPE_API_KEY"})
            assert created == [], "already requeued task must be skipped"
    finally:
        task_tools.load_tasks, task_tools.save_tasks = saved


def test_auto_requeue_skips_when_inbox_file_already_exists():
    """If the inbox file already exists, don't create it again."""
    from tools.task_tools import auto_requeue_credential_satisfied_tasks
    import tools.task_tools as task_tools

    saved = (task_tools.load_tasks, task_tools.save_tasks)
    store = {"tasks": [{"id": "t1", "status": "blocked"}]}
    task_tools.load_tasks = lambda: store["tasks"]
    task_tools.save_tasks = lambda t: store.update(tasks=t)
    try:
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            inbox = root / "inbox"
            outbox = root / "outbox"
            inbox.mkdir()
            outbox.mkdir()

            (outbox / "t1_resource_request.txt").write_text(
                "## Credentials needed\n- STRIPE_API_KEY\n"
            )
            (inbox / "t1_resources_provided.txt").write_text("already there")

            created = auto_requeue_credential_satisfied_tasks(inbox, outbox, {"STRIPE_API_KEY"})
            assert created == [], "existing inbox file → nothing to create"
    finally:
        task_tools.load_tasks, task_tools.save_tasks = saved


if __name__ == "__main__":
    tests = [
        test_drop_table_is_destructive,
        test_truncate_is_destructive,
        test_delete_from_is_destructive,
        test_drop_database_is_destructive,
        test_drop_schema_is_destructive,
        test_alter_table_drop_column_is_destructive,
        test_create_table_is_not_destructive,
        test_add_column_is_not_destructive,
        test_insert_is_not_destructive,
        test_empty_diff_is_not_destructive,
        test_python_diff_is_not_destructive,
        test_high_risk_non_destructive_is_auto_approved,
        test_medium_risk_non_destructive_is_auto_approved,
        test_low_risk_non_destructive_is_auto_approved,
        test_destructive_sql_factor_blocks_auto_approval,
        test_destructive_diff_text_blocks_auto_approval,
        test_clean_diff_with_high_risk_keywords_is_approved,
        test_additive_sql_is_auto_approved,
        test_add_column_sql_is_auto_approved,
        test_drop_table_sql_blocks_auto_approval,
        test_truncate_sql_blocks_auto_approval,
        test_delete_from_sql_blocks_auto_approval,
        test_empty_sql_is_auto_approved,
        test_strategic_always_approved,
        test_config_has_auto_approve_field,
        test_config_auto_approve_enabled_by_default,
        test_config_auto_approve_can_be_disabled,
        test_high_risk_merge_auto_approved_when_enabled,
        test_destructive_merge_not_auto_approved,
        test_merge_blocked_when_auto_approve_disabled,
        test_strategic_gate_auto_approved_when_enabled,
        test_strategic_gate_blocks_when_auto_approve_disabled,
        test_auto_requeue_creates_inbox_file_when_credentials_satisfied,
        test_auto_requeue_skips_when_credentials_missing,
        test_auto_requeue_skips_when_non_credential_resources_present,
        test_auto_requeue_skips_already_requeued_tasks,
        test_auto_requeue_skips_when_inbox_file_already_exists,
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
