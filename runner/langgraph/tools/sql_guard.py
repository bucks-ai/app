"""SQL safety scanner — detect and block destructive SQL before execution."""
import re
from state import SqlScanResult

_BLOCKED_PATTERNS = [
    (r"\bDROP\s+TABLE\s+(?!IF\s+EXISTS)\w", "drop table (without IF EXISTS)"),
    (r"\bDROP\s+SCHEMA\b", "drop schema"),
    (r"\bDROP\s+DATABASE\b", "drop database"),
    (r"\bTRUNCATE\b", "truncate"),
    (r"\bDELETE\s+FROM\s+\w+\s*(?:WHERE\s+1\s*=\s*1|;)", "delete from (effectively all rows)"),
    (r"\bUPDATE\s+\w+\s+SET\b(?![\s\S]*\bWHERE\b)", "update without where"),
]

_SAFE_WARNINGS = [
    (r"\bDROP\s+POLICY\s+IF\s+EXISTS\b", "drop policy if exists (safe)"),
    (r"\bDROP\s+TRIGGER\s+IF\s+EXISTS\b", "drop trigger if exists (safe)"),
    (r"\bDROP\s+INDEX\s+IF\s+EXISTS\b", "drop index if exists (safe)"),
    (r"\bDROP\s+TABLE\s+IF\s+EXISTS\b", "drop table if exists (safe, flagged for review)"),
    (r"\bALTER\s+TABLE\b", "alter table (review carefully)"),
    (r"\bCREATE\s+TABLE\b", "create table"),
    (r"\bCREATE\s+INDEX\b", "create index"),
    (r"\bCREATE\s+POLICY\b", "create policy"),
    (r"\bENABLE\s+ROW\s+LEVEL\s+SECURITY\b", "enable row level security"),
]


def scan_sql_text(sql: str) -> dict:
    text = sql.upper()
    blocked_terms = []
    warnings = []

    for pattern, label in _BLOCKED_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            blocked_terms.append(label)

    for pattern, label in _SAFE_WARNINGS:
        if re.search(pattern, text, re.IGNORECASE | re.MULTILINE):
            warnings.append(label)

    ok = len(blocked_terms) == 0
    result = SqlScanResult(ok=ok, warnings=warnings, blocked_terms=blocked_terms)
    return result.model_dump()


def scan_sql_file(path: str) -> dict:
    try:
        sql = open(path).read()
        return scan_sql_text(sql)
    except FileNotFoundError:
        return SqlScanResult(
            ok=False, blocked_terms=[], warnings=[f"File not found: {path}"]
        ).model_dump()
