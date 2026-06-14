"""Parse worker output summaries into structured data."""
import re
from typing import Any, Optional


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


_EMPTY_VALUES = frozenset({"", "n/a", "na", "none", "(none)", "not applicable", "skipped"})


def _meaningful(value: Any) -> bool:
    return str(value).strip().lower() not in _EMPTY_VALUES


def _shorten(value: Any, limit: int = 140) -> str:
    text = " ".join(str(value).strip().split())
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip() + "…"


def _format_bool(value: Optional[bool], *, yes: str = "yes", no: str = "no") -> str:
    if value is True:
        return yes
    if value is False:
        return no
    return "unknown"


def _format_items(items: list[str], *, max_items: int = 4) -> str:
    cleaned = [_shorten(item) for item in items if _meaningful(item)]
    if not cleaned:
        return "none"
    shown = cleaned[:max_items]
    suffix = f" (+{len(cleaned) - max_items} more)" if len(cleaned) > max_items else ""
    return "; ".join(shown) + suffix


def build_run_summary_digest(summary: Optional[dict], *, task: Optional[dict] = None, max_chars: int = 1200) -> str:
    """Build a compact, stable digest of a parsed worker summary.

    The digest is optimized for task queue summaries, GitHub comments, planner
    context, and log inspection. It intentionally avoids raw worker-output dumps
    so downstream consumers receive predictable fields.
    """
    summary = summary or {}
    task = task or {}

    lines = []
    task_label = task.get("title") or task.get("id")
    if task_label:
        lines.append(f"Task: {_shorten(task_label)}")

    lines.extend([
        f"Files: created {_format_items(summary.get('files_created') or [])}; modified {_format_items(summary.get('files_modified') or [])}",
        f"Check: {_format_bool(summary.get('check_result'), yes='pass', no='fail')}",
    ])

    commit_result = summary.get("commit_result")
    push_result = summary.get("push_result")
    if _meaningful(commit_result) or _meaningful(push_result):
        lines.append(
            f"Git: commit {_shorten(commit_result) if _meaningful(commit_result) else 'unknown'}; "
            f"push {_shorten(push_result) if _meaningful(push_result) else 'unknown'}"
        )

    sql_required = summary.get("sql_required")
    sql_file = summary.get("sql_file_path")
    sql_text = f"SQL: {_format_bool(sql_required)}"
    if sql_required and _meaningful(sql_file):
        sql_text += f" ({_shorten(sql_file)})"
    lines.append(sql_text)

    credentials = summary.get("credentials_needed") or []
    resources = summary.get("resources_needed") or []
    if any(_meaningful(item) for item in credentials + resources):
        lines.append(
            f"Needs: credentials {_format_items(credentials)}; resources {_format_items(resources)}"
        )

    limitations = summary.get("known_limitations") or []
    if any(_meaningful(item) for item in limitations):
        lines.append(f"Limitations: {_format_items(limitations, max_items=3)}")

    next_tasks = summary.get("next_task_hints") or []
    if any(_meaningful(item) for item in next_tasks):
        lines.append(f"Next: {_format_items(next_tasks, max_items=3)}")

    digest = "\n".join(lines)
    if len(digest) <= max_chars:
        return digest
    return digest[: max_chars - 1].rstrip() + "…"


def parse_worker_summary(text: str) -> dict:
    """Extract structured metadata from worker output text."""
    summary = {
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
    summary["run_summary_digest"] = build_run_summary_digest(summary)
    return summary
