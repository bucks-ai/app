"""Unit tests for tools/db_tools.py — pure logic with mocked psycopg connections.

No real database is used anywhere in this file (CI has no database).
Connections are stubbed via FakeConnection/FakeCursor; only migration
ordering/skip logic, guard/gate integration, and no-op-without-credentials
behavior are exercised.

Runs standalone:

    python tests/test_db_tools.py
"""
import hashlib
import os
import sys
import tempfile
import traceback
import unittest.mock as mock
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from config import RunnerConfig
import tools.db_tools as db_tools


# ── Fake psycopg connection/cursor ───────────────────────────────────────────

class FakeCursor:
    def __init__(self, conn):
        self._conn = conn
        self.description = None
        self._last_result = []

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def execute(self, sql, params=None):
        self._conn.executed.append((sql, params))
        if self._conn.raise_on and self._conn.raise_on(sql, params):
            raise RuntimeError("simulated db error")
        if self._conn.fetch_provider:
            result = self._conn.fetch_provider(sql, params)
            if result is not None:
                rows, cols = result
                self._last_result = rows
                self.description = [SimpleNamespace(name=c) for c in cols]

    def fetchall(self):
        return self._last_result


class FakeConnection:
    def __init__(self, raise_on=None, fetch_provider=None):
        self.executed = []
        self.raise_on = raise_on
        self.fetch_provider = fetch_provider
        self.committed = False
        self.rolled_back = False

    def cursor(self):
        return FakeCursor(self)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        if exc_type is None:
            self.committed = True
        else:
            self.rolled_back = True
        return False  # never suppress — caller must see the exception


# ── config: has_database / report() ─────────────────────────────────────────

def test_has_database_false_without_either_url():
    cfg = RunnerConfig(database_url=None, direct_database_url=None)
    assert cfg.has_database is False


def test_has_database_true_with_database_url_only():
    cfg = RunnerConfig(database_url="postgresql://x", direct_database_url=None)
    assert cfg.has_database is True


def test_has_database_true_with_direct_database_url_only():
    cfg = RunnerConfig(database_url=None, direct_database_url="postgresql://y")
    assert cfg.has_database is True


def test_report_includes_database_flags():
    cfg = RunnerConfig(database_url="postgresql://x", direct_database_url=None)
    report = cfg.report()
    assert report["database"] is True
    assert report["has_direct_database_url"] is False
    # never leak the actual connection string
    assert "postgresql://x" not in str(report.values())


# ── inspect_schema ────────────────────────────────────────────────────────

def test_inspect_schema_no_op_without_database():
    with mock.patch("tools.db_tools.get_config") as mock_cfg, \
         mock.patch("tools.db_tools._connect") as mock_connect:
        mock_cfg.return_value = RunnerConfig(database_url=None, direct_database_url=None)
        result = db_tools.inspect_schema()
    assert result["success"] is False
    assert "not configured" in result["error"]
    mock_connect.assert_not_called()


def test_inspect_schema_success():
    rows = [
        ("public", "businesses", "id", "uuid", "NO", None),
        ("public", "businesses", "name", "text", "YES", None),
    ]

    def provider(sql, params):
        if "information_schema.columns" in sql:
            return rows, []
        return None

    fake_conn = FakeConnection(fetch_provider=provider)
    with mock.patch("tools.db_tools.get_config") as mock_cfg, \
         mock.patch("tools.db_tools._connect", return_value=fake_conn) as mock_connect:
        mock_cfg.return_value = RunnerConfig(database_url="postgresql://x", direct_database_url=None)
        result = db_tools.inspect_schema()

    mock_connect.assert_called_once_with("postgresql://x")
    assert result["success"] is True
    assert result["data"]["table_count"] == 1
    cols = result["data"]["tables"]["public.businesses"]
    assert [c["column"] for c in cols] == ["id", "name"]
    assert cols[0]["nullable"] is False
    assert cols[1]["nullable"] is True


def test_inspect_schema_handles_connection_error():
    def boom(url):
        raise RuntimeError("connection refused")

    with mock.patch("tools.db_tools.get_config") as mock_cfg, \
         mock.patch("tools.db_tools._connect", side_effect=boom):
        mock_cfg.return_value = RunnerConfig(database_url="postgresql://x", direct_database_url=None)
        result = db_tools.inspect_schema()

    assert result["success"] is False
    assert "connection refused" in result["error"]


# ── list_rls_policies ─────────────────────────────────────────────────────

def test_list_rls_policies_no_op_without_database():
    with mock.patch("tools.db_tools.get_config") as mock_cfg, \
         mock.patch("tools.db_tools._connect") as mock_connect:
        mock_cfg.return_value = RunnerConfig(database_url=None, direct_database_url=None)
        result = db_tools.list_rls_policies()
    assert result["success"] is False
    assert "not configured" in result["error"]
    mock_connect.assert_not_called()


def test_list_rls_policies_success():
    cols = ["schemaname", "tablename", "policyname", "permissive", "roles", "cmd", "qual", "with_check"]
    rows = [("public", "businesses", "owner_only", "PERMISSIVE", ["authenticated"], "ALL", "user_id = auth.uid()", None)]

    def provider(sql, params):
        if "pg_policies" in sql:
            return rows, cols
        return None

    fake_conn = FakeConnection(fetch_provider=provider)
    with mock.patch("tools.db_tools.get_config") as mock_cfg, \
         mock.patch("tools.db_tools._connect", return_value=fake_conn):
        mock_cfg.return_value = RunnerConfig(database_url="postgresql://x", direct_database_url=None)
        result = db_tools.list_rls_policies()

    assert result["success"] is True
    assert result["data"]["policy_count"] == 1
    assert result["data"]["policies"][0]["policyname"] == "owner_only"


# ── apply_migration_file ─────────────────────────────────────────────────

def _cfg_for_apply(**overrides):
    defaults = dict(
        database_url="postgresql://x",
        direct_database_url="postgresql://direct",
        sql_environment="development",
        sql_approval_policy="require_on_production",
        supabase_url=None,
    )
    defaults.update(overrides)
    return RunnerConfig(**defaults)


def test_apply_migration_file_no_op_without_database():
    with mock.patch("tools.db_tools.get_config") as mock_cfg, \
         mock.patch("tools.db_tools._connect") as mock_connect:
        mock_cfg.return_value = RunnerConfig(database_url=None, direct_database_url=None)
        result = db_tools.apply_migration_file("/nonexistent/0001_x.sql")
    assert result["success"] is False
    assert "not configured" in result["error"]
    mock_connect.assert_not_called()


def test_apply_migration_file_missing_file():
    with mock.patch("tools.db_tools.get_config") as mock_cfg:
        mock_cfg.return_value = _cfg_for_apply()
        result = db_tools.apply_migration_file("/definitely/not/a/real/path_0001.sql")
    assert result["success"] is False
    assert "not found" in result["error"]


def test_apply_migration_file_blocked_by_sql_guard():
    """Real (unmocked) sql_guard.scan_sql_file — a real destructive statement
    must be blocked before any connection is attempted."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d, "0001_drop.sql")
        path.write_text("DROP TABLE users;")
        with mock.patch("tools.db_tools.get_config") as mock_cfg, \
             mock.patch("tools.db_tools._connect") as mock_connect:
            mock_cfg.return_value = _cfg_for_apply()
            result = db_tools.apply_migration_file(str(path))
    assert result["success"] is False
    assert result["error"] == "sql_scan_blocked"
    assert "drop table (without IF EXISTS)" in result["data"]["scan"]["blocked_terms"]
    mock_connect.assert_not_called()


def test_apply_migration_file_blocked_by_environment_gate():
    """Real (unmocked) sql_environment_gate — production + require_on_production
    must block before any connection is attempted."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d, "0001_create.sql")
        path.write_text("CREATE TABLE runner_test_gate (id int);")
        with mock.patch("tools.db_tools.get_config") as mock_cfg, \
             mock.patch("tools.db_tools._connect") as mock_connect:
            mock_cfg.return_value = _cfg_for_apply(
                sql_environment="production", sql_approval_policy="require_on_production",
            )
            result = db_tools.apply_migration_file(str(path))
    assert result["success"] is False
    assert result["error"] == "approval_required"
    assert result["data"]["gate"]["approval_required"] is True
    mock_connect.assert_not_called()


def test_apply_migration_file_success_records_ledger_in_same_transaction():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d, "0001_create.sql")
        sql_text = "CREATE TABLE runner_test_apply_migration_file (id int);"
        path.write_text(sql_text)
        expected_sha = hashlib.sha256(sql_text.encode()).hexdigest()

        fake_conn = FakeConnection()
        with mock.patch("tools.db_tools.get_config") as mock_cfg, \
             mock.patch("tools.db_tools._connect", return_value=fake_conn) as mock_connect:
            mock_cfg.return_value = _cfg_for_apply()
            result = db_tools.apply_migration_file(str(path))

    assert result["success"] is True
    assert result["data"]["filename"] == "0001_create.sql"
    assert result["data"]["sha256"] == expected_sha
    # applied via DIRECT_DATABASE_URL, not the pooled DATABASE_URL
    mock_connect.assert_called_once_with("postgresql://direct")
    # ledger table ensured + migration executed + ledger row inserted, all in one connection
    executed_sql = [call[0] for call in fake_conn.executed]
    assert any("_runner_migrations" in s and "CREATE TABLE IF NOT EXISTS" in s for s in executed_sql)
    assert any(sql_text in s for s in executed_sql)
    assert any("INSERT INTO _runner_migrations" in s for s in executed_sql)
    assert fake_conn.committed is True
    assert fake_conn.rolled_back is False


def test_apply_migration_file_rolls_back_on_error():
    with tempfile.TemporaryDirectory() as d:
        path = Path(d, "0001_create.sql")
        sql_text = "CREATE TABLE runner_test_rollback (id int);"
        path.write_text(sql_text)

        fake_conn = FakeConnection(raise_on=lambda sql, params: sql_text in sql)
        with mock.patch("tools.db_tools.get_config") as mock_cfg, \
             mock.patch("tools.db_tools._connect", return_value=fake_conn):
            mock_cfg.return_value = _cfg_for_apply()
            result = db_tools.apply_migration_file(str(path))

    assert result["success"] is False
    assert "simulated db error" in result["error"]
    assert fake_conn.rolled_back is True
    assert fake_conn.committed is False


def test_apply_migration_file_rolls_back_on_duplicate_ledger_entry():
    """Simulates re-applying an already-recorded filename: the ledger INSERT
    (PRIMARY KEY violation) fails and the whole transaction rolls back."""
    with tempfile.TemporaryDirectory() as d:
        path = Path(d, "0001_create.sql")
        path.write_text("CREATE TABLE runner_test_dup (id int);")

        fake_conn = FakeConnection(raise_on=lambda sql, params: "INSERT INTO _runner_migrations" in sql)
        with mock.patch("tools.db_tools.get_config") as mock_cfg, \
             mock.patch("tools.db_tools._connect", return_value=fake_conn):
            mock_cfg.return_value = _cfg_for_apply()
            result = db_tools.apply_migration_file(str(path))

    assert result["success"] is False
    assert fake_conn.rolled_back is True
    assert fake_conn.committed is False


# ── apply_pending_migrations ──────────────────────────────────────────────

def test_apply_pending_migrations_no_op_without_database():
    with mock.patch("tools.db_tools.get_config") as mock_cfg, \
         mock.patch("tools.db_tools._connect") as mock_connect:
        mock_cfg.return_value = RunnerConfig(database_url=None, direct_database_url=None)
        result = db_tools.apply_pending_migrations("/some/dir")
    assert result["success"] is False
    assert "not configured" in result["error"]
    mock_connect.assert_not_called()


def test_apply_pending_migrations_missing_directory():
    with mock.patch("tools.db_tools.get_config") as mock_cfg:
        mock_cfg.return_value = _cfg_for_apply()
        result = db_tools.apply_pending_migrations("/definitely/not/a/real/dir")
    assert result["success"] is False
    assert "not found" in result["error"]


def test_apply_pending_migrations_orders_by_filename():
    calls = []

    def fake_apply(path):
        calls.append(Path(path).name)
        return {"tool": "db_apply_migration_file", "success": True, "data": {"filename": Path(path).name}}

    with tempfile.TemporaryDirectory() as d:
        Path(d, "0002_second.sql").write_text("select 1;")
        Path(d, "0001_first.sql").write_text("select 1;")
        with mock.patch("tools.db_tools.get_config") as mock_cfg, \
             mock.patch("tools.db_tools._fetch_applied_filenames", return_value=set()), \
             mock.patch("tools.db_tools.apply_migration_file", side_effect=fake_apply):
            mock_cfg.return_value = _cfg_for_apply()
            result = db_tools.apply_pending_migrations(d)

    assert calls == ["0001_first.sql", "0002_second.sql"]
    assert result["success"] is True


def test_apply_pending_migrations_skips_already_applied():
    calls = []

    def fake_apply(path):
        calls.append(Path(path).name)
        return {"tool": "db_apply_migration_file", "success": True, "data": {}}

    with tempfile.TemporaryDirectory() as d:
        Path(d, "0001_first.sql").write_text("select 1;")
        Path(d, "0002_second.sql").write_text("select 1;")
        with mock.patch("tools.db_tools.get_config") as mock_cfg, \
             mock.patch("tools.db_tools._fetch_applied_filenames", return_value={"0001_first.sql"}), \
             mock.patch("tools.db_tools.apply_migration_file", side_effect=fake_apply):
            mock_cfg.return_value = _cfg_for_apply()
            result = db_tools.apply_pending_migrations(d)

    assert calls == ["0002_second.sql"]
    results = result["data"]["results"]
    assert results[0] == {"filename": "0001_first.sql", "status": "skipped_already_applied"}
    assert results[1]["status"] == "applied"
    assert result["success"] is True


def test_apply_pending_migrations_stops_on_first_failure():
    calls = []

    def fake_apply(path):
        name = Path(path).name
        calls.append(name)
        ok = name != "0001_first.sql"
        return {"tool": "db_apply_migration_file", "success": ok, "error": None if ok else "boom"}

    with tempfile.TemporaryDirectory() as d:
        Path(d, "0001_first.sql").write_text("select 1;")
        Path(d, "0002_second.sql").write_text("select 1;")
        with mock.patch("tools.db_tools.get_config") as mock_cfg, \
             mock.patch("tools.db_tools._fetch_applied_filenames", return_value=set()), \
             mock.patch("tools.db_tools.apply_migration_file", side_effect=fake_apply):
            mock_cfg.return_value = _cfg_for_apply()
            result = db_tools.apply_pending_migrations(d)

    assert calls == ["0001_first.sql"]  # 0002 never attempted after 0001 fails
    assert result["success"] is False


def test_apply_pending_migrations_ledger_read_failure():
    with tempfile.TemporaryDirectory() as d:
        Path(d, "0001_first.sql").write_text("select 1;")
        with mock.patch("tools.db_tools.get_config") as mock_cfg, \
             mock.patch("tools.db_tools._fetch_applied_filenames", return_value=None):
            mock_cfg.return_value = _cfg_for_apply()
            result = db_tools.apply_pending_migrations(d)

    assert result["success"] is False
    assert "ledger" in result["error"]


def test_fetch_applied_filenames_uses_direct_url_and_creates_table():
    def provider(sql, params):
        if "SELECT filename FROM _runner_migrations" in sql:
            return [("0001_x.sql",), ("0002_y.sql",)], ["filename"]
        return None

    fake_conn = FakeConnection(fetch_provider=provider)
    with mock.patch("tools.db_tools._connect", return_value=fake_conn) as mock_connect:
        cfg = _cfg_for_apply()
        result = db_tools._fetch_applied_filenames(cfg)

    mock_connect.assert_called_once_with("postgresql://direct")
    assert result == {"0001_x.sql", "0002_y.sql"}
    assert any("CREATE TABLE IF NOT EXISTS _runner_migrations" in s for s, _ in fake_conn.executed)


if __name__ == "__main__":
    tests = [
        test_has_database_false_without_either_url,
        test_has_database_true_with_database_url_only,
        test_has_database_true_with_direct_database_url_only,
        test_report_includes_database_flags,
        test_inspect_schema_no_op_without_database,
        test_inspect_schema_success,
        test_inspect_schema_handles_connection_error,
        test_list_rls_policies_no_op_without_database,
        test_list_rls_policies_success,
        test_apply_migration_file_no_op_without_database,
        test_apply_migration_file_missing_file,
        test_apply_migration_file_blocked_by_sql_guard,
        test_apply_migration_file_blocked_by_environment_gate,
        test_apply_migration_file_success_records_ledger_in_same_transaction,
        test_apply_migration_file_rolls_back_on_error,
        test_apply_migration_file_rolls_back_on_duplicate_ledger_entry,
        test_apply_pending_migrations_no_op_without_database,
        test_apply_pending_migrations_missing_directory,
        test_apply_pending_migrations_orders_by_filename,
        test_apply_pending_migrations_skips_already_applied,
        test_apply_pending_migrations_stops_on_first_failure,
        test_apply_pending_migrations_ledger_read_failure,
        test_fetch_applied_filenames_uses_direct_url_and_creates_table,
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
