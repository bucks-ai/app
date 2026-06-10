"""Parse worker output summaries into structured data."""
import re
from typing import Optional


def _extract_section(text: str, *keywords: str) -> Optional[str]:
    for kw in keywords:
        # Anchor to line start (after optional bullet/dash) and capture to
        # end of that line only.  The old DOTALL approach consumed multiple
        # sections when section headers start with "- " rather than a capital
        # letter, causing false-positive values to bleed across fields.
        pattern = rf"(?im)^[- ]*{re.escape(kw)}\s*[:\-]\s*(.+?)\s*$"
        m = re.search(pattern, text)
        if m:
            return m.group(1).strip()
    return None


# A bullet whose text is itself a section label, e.g. "Resources Needed:" or
# "Check Result: pass". Used to stop a list capture from bleeding into the
# following section when sections are formatted as "- Header:" bullets.
_SECTION_HEADER = re.compile(r"^[A-Za-z][A-Za-z /]{0,40}:")


def _extract_list(text: str, *keywords: str) -> list[str]:
    for kw in keywords:
        pattern = rf"(?i){re.escape(kw)}\s*[:\-]?\s*\n((?:\s*[-*]\s*.+\n?)+)"
        m = re.search(pattern, text)
        if m:
            items = []
            for raw in re.findall(r"[-*]\s*(.+)", m.group(1)):
                item = raw.strip()
                # Stop at the next section header so one list doesn't absorb the
                # bullets (or inline values) of the sections that follow it.
                if _SECTION_HEADER.match(item):
                    break
                items.append(item)
            return items
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
        "check_result": _bool_from_text(_extract_section(text, "check result")),
        "commit_result": _extract_section(text, "commit result", "commit"),
        "push_result": _extract_section(text, "push result", "push"),
        "merge_result": _extract_section(text, "merge result", "merge"),
        "sql_required": _bool_from_text(_extract_section(text, "sql required", "sql needed")),
        "sql_file_path": _extract_section(text, "sql file path", "sql file", "sql path", "migration file"),
        "credentials_needed": _extract_list(text, "credentials needed", "credentials required", "credential needed", "secrets needed"),
        "resources_needed": _extract_list(text, "resources needed", "resources required", "resource needed"),
        "known_limitations": _extract_list(text, "known limitations", "limitations", "caveats"),
        "next_task_hints": _extract_list(text, "next task", "next steps", "follow-up"),
        "raw_length": len(text),
    }
