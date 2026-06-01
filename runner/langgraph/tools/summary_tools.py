"""Parse worker output summaries into structured data."""
import re
from typing import Optional


def _extract_section(text: str, *keywords: str) -> Optional[str]:
    for kw in keywords:
        pattern = rf"(?i){re.escape(kw)}\s*[:\-]?\s*(.+?)(?=\n[A-Z]|\Z)"
        m = re.search(pattern, text, re.DOTALL)
        if m:
            return m.group(1).strip()
    return None


def _extract_list(text: str, *keywords: str) -> list[str]:
    for kw in keywords:
        pattern = rf"(?i){re.escape(kw)}\s*[:\-]?\s*\n((?:\s*[-*]\s*.+\n?)+)"
        m = re.search(pattern, text)
        if m:
            items = re.findall(r"[-*]\s*(.+)", m.group(1))
            return [i.strip() for i in items]
    return []


def _bool_from_text(text: Optional[str]) -> Optional[bool]:
    if not text:
        return None
    low = text.lower()
    if any(w in low for w in ("pass", "success", "ok", "true", "yes", "✓", "done")):
        return True
    if any(w in low for w in ("fail", "error", "false", "no", "✗", "blocked")):
        return False
    return None


def parse_worker_summary(text: str) -> dict:
    """Extract structured metadata from worker output text."""
    return {
        "files_created": _extract_list(text, "files created", "created files", "new files"),
        "files_modified": _extract_list(text, "files modified", "modified files", "changed files"),
        "check_result": _bool_from_text(_extract_section(text, "check result", "check", "tests")),
        "commit_result": _extract_section(text, "commit", "committed"),
        "push_result": _extract_section(text, "push", "pushed"),
        "merge_result": _extract_section(text, "merge", "merged"),
        "sql_required": _bool_from_text(_extract_section(text, "sql required", "sql needed", "sql")),
        "sql_file_path": _extract_section(text, "sql file", "sql path", "migration file"),
        "known_limitations": _extract_list(text, "known limitations", "limitations", "caveats"),
        "next_task_hints": _extract_list(text, "next task", "next steps", "follow-up"),
        "raw_length": len(text),
    }
