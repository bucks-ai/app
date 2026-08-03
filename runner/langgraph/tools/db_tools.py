"""Direct Postgres database tooling — schema inspection, RLS policy listing,
and guarded migration application.

Unlike ``tools/supabase_tools.py`` (which goes through the Supabase REST/RPC
layer), these tools open a direct ``psycopg`` connection using
``DATABASE_URL`` / ``DIRECT_DATABASE_URL``. Migration application always goes
through ``sql_guard.scan_sql_file`` and the ``sql_environment_gate`` policy
before anything is executed — the same gates the worker-emitted SQL path
already uses in ``graph.apply_sql_if_needed``.

All functions no-op with a clear ``ToolResult`` error when
``cfg.has_database`` is false, so this module is safe to import and call in
environments (like CI) with no database configured.
"""
import hashlib
import re
from pathlib import Path

from config import get_config
from state import ToolResult
from tools.log_tools import log_event
from tools.sql_guard import scan_sql_file
from tools.sql_environment_gate import evaluate_sql_approval_policy, infer_environment

MIGRATIONS_TABLE = "_runner_migrations"

# Patterns that mark a migration as non-additive — i.e. it can rename, remove,
# or mutate existing data/schema rather than only adding new schema. These are
# never auto-applied even when AUTO_APPLY_MIGRATIONS=true and the file passes
# sql_guard/sql_environment_gate; a human always reviews and applies them by
# hand (see supabase/migrations/README.md).
_NON_ADDITIVE_PATTERNS = [
    (r"\bDROP\s+", "drop statement (table/column/index/policy/etc.)"),
    (r"\bTRUNCATE\b", "truncate"),
    (r"\bDELETE\s+FROM\b", "delete from"),
    (r"\bUPDATE\s+\w+\s+SET\b", "update ... set (data mutation)"),
    (r"\bRENAME\b", "rename"),
    (r"\bALTER\s+COLUMN\b[\s\S]*?\bTYPE\b", "alter column type"),
]

_MIGRATIONS_TABLE_DDL = f"""
CREATE TABLE IF NOT EXISTS {MIGRATIONS_TABLE} (
    filename    TEXT PRIMARY KEY,
    sha256      TEXT NOT NULL,
    applied_at  TIMESTAMPTZ NOT NULL DEFAULT now()
);
"""


def _connect(url: str):
    import psycopg
    return psycopg.connect(url)


def _read_url(cfg) -> str:
    """Connection string for read-only inspection — pooled connections are fine."""
    return cfg.database_url or cfg.direct_database_url


def _apply_url(cfg) -> str:
    """Connection string for applying migrations — prefer the direct (non-pooled) URL."""
    return cfg.direct_database_url or cfg.database_url


def _no_database_result(tool: str) -> dict:
    return ToolResult(
        tool=tool,
        success=False,
        error="DATABASE_URL / DIRECT_DATABASE_URL not configured — database tooling disabled.",
    ).model_dump()


def inspect_schema() -> dict:
    """Return tables/columns/types from information_schema.columns."""
    cfg = get_config()
    if not cfg.has_database:
        return _no_database_result("db_inspect_schema")
    try:
        with _connect(_read_url(cfg)) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT table_schema, table_name, column_name, data_type,
                           is_nullable, column_default
                    FROM information_schema.columns
                    WHERE table_schema NOT IN ('pg_catalog', 'information_schema')
                    ORDER BY table_schema, table_name, ordinal_position
                    """
                )
                rows = cur.fetchall()
        tables: dict[str, list[dict]] = {}
        for schema, table, column, dtype, nullable, default in rows:
            key = f"{schema}.{table}"
            tables.setdefault(key, []).append({
                "column": column,
                "type": dtype,
                "nullable": nullable == "YES",
                "default": default,
            })
        return ToolResult(
            tool="db_inspect_schema",
            success=True,
            data={"tables": tables, "table_count": len(tables)},
        ).model_dump()
    except Exception as e:
        log_event("error", {"tool": "db_inspect_schema", "error": str(e)})
        return ToolResult(tool="db_inspect_schema", success=False, error=str(e)).model_dump()


def list_rls_policies() -> dict:
    """Return row-level-security policies from pg_policies."""
    cfg = get_config()
    if not cfg.has_database:
        return _no_database_result("db_list_rls_policies")
    try:
        with _connect(_read_url(cfg)) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT schemaname, tablename, policyname, permissive, roles, cmd, qual, with_check
                    FROM pg_policies
                    ORDER BY schemaname, tablename, policyname
                    """
                )
                cols = [d.name for d in cur.description]
                rows = cur.fetchall()
        policies = [dict(zip(cols, row)) for row in rows]
        return ToolResult(
            tool="db_list_rls_policies",
            success=True,
            data={"policies": policies, "policy_count": len(policies)},
        ).model_dump()
    except Exception as e:
        log_event("error", {"tool": "db_list_rls_policies", "error": str(e)})
        return ToolResult(tool="db_list_rls_policies", success=False, error=str(e)).model_dump()


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def classify_migration_additivity(sql_text: str) -> dict:
    """Pure classifier: does this SQL only ADD schema, or could it remove/rename/
    mutate something that already exists?

    Returns {"additive": bool, "reasons": [str, ...]} — reasons is empty when
    additive. This is intentionally conservative (any DROP, even a guarded
    `DROP ... IF EXISTS`, counts as non-additive) since auto-apply eligibility
    is the caller, and a false "non-additive" only costs a human review, while
    a false "additive" could auto-apply something destructive.
    """
    text = sql_text.upper()
    reasons = [label for pattern, label in _NON_ADDITIVE_PATTERNS if re.search(pattern, text)]
    return {"additive": len(reasons) == 0, "reasons": reasons}


def apply_migration_file(path: str) -> dict:
    """Apply ONE .sql migration file inside a transaction.

    Gated by sql_guard.scan_sql_file (blocked terms abort before any
    connection is opened) and sql_environment_gate (approval-required
    environments abort before any connection is opened). On success, records
    (filename, sha256, applied_at) in the `_runner_migrations` ledger table
    (created if absent) in the SAME transaction as the migration, so a
    duplicate filename or a failing statement rolls back everything.
    """
    cfg = get_config()
    if not cfg.has_database:
        return _no_database_result("db_apply_migration_file")

    file_path = Path(path)
    if not file_path.exists():
        return ToolResult(
            tool="db_apply_migration_file", success=False, error=f"File not found: {path}"
        ).model_dump()

    scan = scan_sql_file(str(file_path))
    if not scan["ok"]:
        log_event("sql_scan_blocked", {
            "tool": "db_apply_migration_file", "path": path, "blocked_terms": scan["blocked_terms"],
        })
        return ToolResult(
            tool="db_apply_migration_file",
            success=False,
            error="sql_scan_blocked",
            data={"scan": scan},
        ).model_dump()

    effective_env = cfg.sql_environment or infer_environment(cfg.supabase_url)
    gate = evaluate_sql_approval_policy(
        scan_result=scan,
        sql_environment=effective_env,
        policy=cfg.sql_approval_policy,
    )
    if gate["approval_required"]:
        log_event("sql_approval_pending", {
            "tool": "db_apply_migration_file", "path": path, "reason": gate["reason"],
        })
        return ToolResult(
            tool="db_apply_migration_file",
            success=False,
            error="approval_required",
            data={"scan": scan, "gate": gate},
        ).model_dump()

    sql_text = file_path.read_text()
    sha256 = _sha256_file(file_path)
    filename = file_path.name

    try:
        # Exiting `with conn:` without an exception commits; an exception
        # anywhere inside (bad SQL, duplicate ledger filename, etc.) rolls
        # back the whole transaction — migration DDL and ledger insert together.
        with _connect(_apply_url(cfg)) as conn:
            with conn.cursor() as cur:
                cur.execute(_MIGRATIONS_TABLE_DDL)
                cur.execute(sql_text)
                cur.execute(
                    f"INSERT INTO {MIGRATIONS_TABLE} (filename, sha256) VALUES (%s, %s)",
                    (filename, sha256),
                )
        log_event("sql_applied", {"tool": "db_apply_migration_file", "path": path, "filename": filename})
        return ToolResult(
            tool="db_apply_migration_file",
            success=True,
            data={"filename": filename, "sha256": sha256},
        ).model_dump()
    except Exception as e:
        log_event("error", {"tool": "db_apply_migration_file", "path": path, "error": str(e)})
        return ToolResult(tool="db_apply_migration_file", success=False, error=str(e)).model_dump()


def _fetch_applied_filenames(cfg) -> set | None:
    try:
        with _connect(_apply_url(cfg)) as conn:
            with conn.cursor() as cur:
                cur.execute(_MIGRATIONS_TABLE_DDL)
                cur.execute(f"SELECT filename FROM {MIGRATIONS_TABLE}")
                rows = cur.fetchall()
        return {row[0] for row in rows}
    except Exception as e:
        log_event("error", {"tool": "db_apply_pending_migrations", "error": str(e)})
        return None


def list_pending_migrations(directory: str) -> dict:
    """Read-only: which *.sql files in `directory` are NOT yet recorded in the
    `_runner_migrations` ledger, in filename order. Applies nothing."""
    cfg = get_config()
    if not cfg.has_database:
        return _no_database_result("db_list_pending_migrations")

    dir_path = Path(directory)
    if not dir_path.exists():
        return ToolResult(
            tool="db_list_pending_migrations", success=False, error=f"Directory not found: {directory}"
        ).model_dump()

    applied = _fetch_applied_filenames(cfg)
    if applied is None:
        return ToolResult(
            tool="db_list_pending_migrations",
            success=False,
            error=f"Failed to read {MIGRATIONS_TABLE} ledger.",
        ).model_dump()

    migration_files = sorted(dir_path.glob("*.sql"), key=lambda p: p.name)
    pending = [f.name for f in migration_files if f.name not in applied]
    return ToolResult(
        tool="db_list_pending_migrations",
        success=True,
        data={"pending": pending, "total_count": len(migration_files), "applied_count": len(applied)},
    ).model_dump()


def apply_pending_migrations(directory: str) -> dict:
    """Apply all *.sql files in `directory`, in filename order, skipping ones
    already recorded in the `_runner_migrations` ledger. Stops at the first
    failure so later migrations are never applied out of order."""
    cfg = get_config()
    if not cfg.has_database:
        return _no_database_result("db_apply_pending_migrations")

    dir_path = Path(directory)
    if not dir_path.exists():
        return ToolResult(
            tool="db_apply_pending_migrations", success=False, error=f"Directory not found: {directory}"
        ).model_dump()

    applied = _fetch_applied_filenames(cfg)
    if applied is None:
        return ToolResult(
            tool="db_apply_pending_migrations",
            success=False,
            error=f"Failed to read {MIGRATIONS_TABLE} ledger.",
        ).model_dump()

    migration_files = sorted(dir_path.glob("*.sql"), key=lambda p: p.name)
    results = []
    all_ok = True
    for f in migration_files:
        if f.name in applied:
            results.append({"filename": f.name, "status": "skipped_already_applied"})
            continue
        result = apply_migration_file(str(f))
        results.append({
            "filename": f.name,
            "status": "applied" if result["success"] else "failed",
            "result": result,
        })
        if not result["success"]:
            all_ok = False
            break

    return ToolResult(
        tool="db_apply_pending_migrations",
        success=all_ok,
        data={"results": results},
    ).model_dump()
