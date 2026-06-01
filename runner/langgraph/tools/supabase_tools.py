"""Supabase SQL execution tools with sql_guard pre-check."""
from pathlib import Path
from config import get_config
from tools.sql_guard import scan_sql_text
from tools.log_tools import log_event


def apply_sql_text(sql: str) -> dict:
    cfg = get_config()
    scan = scan_sql_text(sql)
    log_event("sql_detected", {"scan": scan})

    if not scan["ok"]:
        log_event("sql_scan_blocked", {"blocked_terms": scan["blocked_terms"]})
        return {"success": False, "reason": "sql_scan_blocked", "scan": scan}

    log_event("sql_scan_passed", {"warnings": scan["warnings"]})

    if not cfg.has_supabase:
        msg = "SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY not configured — SQL needs manual execution."
        log_event("sql_manual_required", {"message": msg, "sql_preview": sql[:200]})
        return {"success": False, "reason": "no_supabase_config", "message": msg}

    if not cfg.auto_apply_sql:
        msg = "AUTO_APPLY_SQL=false — SQL not applied automatically."
        log_event("sql_manual_required", {"message": msg})
        return {"success": False, "reason": "auto_apply_disabled", "message": msg}

    try:
        from supabase import create_client
        client = create_client(cfg.supabase_url, cfg.supabase_service_role_key)
        client.rpc("exec_sql", {"query": sql}).execute()
        log_event("sql_applied", {"sql_preview": sql[:200]})
        return {"success": True, "scan": scan}
    except Exception as e:
        # Supabase client may not support arbitrary SQL via RPC without a custom function.
        msg = f"SQL execution failed: {e}. Apply manually via Supabase SQL editor."
        log_event("error", {"tool": "supabase", "error": str(e)})
        return {"success": False, "reason": "execution_error", "message": msg}


def apply_sql_file(path: str) -> dict:
    try:
        sql = Path(path).read_text()
        return apply_sql_text(sql)
    except FileNotFoundError:
        return {"success": False, "reason": "file_not_found", "path": path}


def verify_table_exists(table_name: str) -> dict:
    cfg = get_config()
    if not cfg.has_supabase:
        return {"success": False, "reason": "no_supabase_config"}
    try:
        from supabase import create_client
        client = create_client(cfg.supabase_url, cfg.supabase_service_role_key)
        result = client.table(table_name).select("*").limit(1).execute()
        return {"success": True, "exists": True}
    except Exception as e:
        return {"success": False, "exists": False, "error": str(e)}
