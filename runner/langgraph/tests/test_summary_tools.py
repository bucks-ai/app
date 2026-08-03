"""Unit tests for summary_tools.parse_worker_summary."""
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.summary_tools import (
    build_run_summary_digest,
    parse_worker_summary,
    _extract_section,
    _bool_from_text,
)

# ---------------------------------------------------------------------------
# Canonical structured output (matches the prompt template exactly)
# ---------------------------------------------------------------------------

CANONICAL = """
- Files Created:
  - app/api/buckets/route.ts
- Files Modified:
  - lib/db.ts
  - lib/schema.ts
- Check Result: pass
- Commit Result: abc1234
- Push Result: done
- SQL Required: no
- SQL File Path: N/A
- Known Limitations:
  - only tested locally
- Next Task:
  - add unit tests
"""

SQL_REQUIRED = """
- Files Created:
  - migrations/001_add_buckets.sql
- Files Modified:
  - lib/schema.ts
- Check Result: pass
- Commit Result: def5678
- Push Result: done
- SQL Required: yes
- SQL File Path: migrations/001_add_buckets.sql
- Known Limitations:
  - migration not applied yet
- Next Task:
  - apply migration in prod
"""

# ---------------------------------------------------------------------------
# False-positive regression inputs
# ---------------------------------------------------------------------------

# SQL mentioned in prose but NOT required
SQL_MENTION_NO_REQUIRED = """
I updated the schema. No SQL migration is required for this change.
The check ran successfully.

- Files Created: (none)
- Files Modified:
  - lib/schema.ts
- Check Result: pass
- Commit Result: aaa1111
- Push Result: done
- SQL Required: no
- SQL File Path: N/A
- Known Limitations: (none)
- Next Task: (none)
"""

# "check" appears in prose before the structured section
CHECK_IN_PROSE = """
I ran a quick check on the build and it failed for an edge case but I fixed it.

- Files Created: (none)
- Files Modified:
  - lib/utils.ts
- Check Result: pass
- Commit Result: bbb2222
- Push Result: done
- SQL Required: no
- SQL File Path: N/A
- Known Limitations: (none)
- Next Task: (none)
"""

# Multiple SQL-related words in prose; sql_required should be False
SQL_PROSE_FALSE_POSITIVE = """
This task involved updating the SQL query builder.
We refactored how SQL statements are constructed in the ORM.
No schema changes needed.

- Files Created: (none)
- Files Modified:
  - lib/query_builder.ts
- Check Result: pass
- Commit Result: ccc3333
- Push Result: skipped
- SQL Required: no
- SQL File Path: N/A
- Known Limitations: (none)
- Next Task: (none)
"""


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_canonical_check_result_pass():
    result = parse_worker_summary(CANONICAL)
    assert result["check_result"] is True, f"Expected True, got {result['check_result']!r}"


def test_canonical_sql_not_required():
    result = parse_worker_summary(CANONICAL)
    assert result["sql_required"] is False, f"Expected False, got {result['sql_required']!r}"


def test_canonical_commit_result():
    result = parse_worker_summary(CANONICAL)
    assert result["commit_result"] == "abc1234", f"Got {result['commit_result']!r}"


def test_canonical_push_result():
    result = parse_worker_summary(CANONICAL)
    assert result["push_result"] == "done", f"Got {result['push_result']!r}"


def test_canonical_files_created():
    result = parse_worker_summary(CANONICAL)
    assert "app/api/buckets/route.ts" in result["files_created"]


def test_canonical_files_modified():
    result = parse_worker_summary(CANONICAL)
    assert "lib/db.ts" in result["files_modified"]


def test_sql_required_yes():
    result = parse_worker_summary(SQL_REQUIRED)
    assert result["sql_required"] is True, f"Expected True, got {result['sql_required']!r}"


def test_sql_file_path():
    result = parse_worker_summary(SQL_REQUIRED)
    assert result["sql_file_path"] == "migrations/001_add_buckets.sql", f"Got {result['sql_file_path']!r}"


def test_no_false_positive_sql_required_from_prose():
    """sql_required must be False even when 'SQL' appears extensively in prose."""
    result = parse_worker_summary(SQL_MENTION_NO_REQUIRED)
    assert result["sql_required"] is False, (
        f"False positive: sql_required={result['sql_required']!r} for a 'SQL Required: no' summary"
    )


def test_no_false_positive_check_result_from_prose():
    """check_result must be True (pass) even when 'check ... failed' appears in prose."""
    result = parse_worker_summary(CHECK_IN_PROSE)
    assert result["check_result"] is True, (
        f"False positive: check_result={result['check_result']!r}; prose mention of failure should not override structured field"
    )


def test_no_false_positive_sql_required_sql_prose():
    result = parse_worker_summary(SQL_PROSE_FALSE_POSITIVE)
    assert result["sql_required"] is False, (
        f"False positive: sql_required={result['sql_required']!r}"
    )


def test_push_skipped():
    result = parse_worker_summary(SQL_PROSE_FALSE_POSITIVE)
    assert result["push_result"] == "skipped", f"Got {result['push_result']!r}"


def test_list_does_not_bleed_into_next_section():
    """A bulleted list must stop at the next section header, not absorb it."""
    result = parse_worker_summary(CANONICAL)
    assert result["files_modified"] == ["lib/db.ts", "lib/schema.ts"], result["files_modified"]
    assert result["files_created"] == ["app/api/buckets/route.ts"], result["files_created"]


def test_empty_text():
    result = parse_worker_summary("")
    assert result["sql_required"] is None
    assert result["check_result"] is None
    assert result["files_created"] == []


def test_parse_includes_run_summary_digest():
    result = parse_worker_summary(CANONICAL)
    digest = result["run_summary_digest"]
    assert "Files: created app/api/buckets/route.ts; modified lib/db.ts; lib/schema.ts" in digest
    assert "Check: pass" in digest
    assert "SQL: no" in digest
    assert "Next: add unit tests" in digest


def test_digest_includes_task_label_and_resource_needs():
    summary = parse_worker_summary("""
- Files Created: (none)
- Files Modified:
  - runner/langgraph/graph.py
- Check Result: fail
- Commit Result: skipped
- Push Result: skipped
- SQL Required: yes
- SQL File Path: supabase/run-summary.sql
- Credentials Needed:
  - SUPABASE_SERVICE_ROLE_KEY
- Resources Needed:
  - Supabase SQL editor access
- Known Limitations:
  - SQL was not applied
- Next Task:
  - apply SQL
""")
    digest = build_run_summary_digest(summary, task={"title": "Add digest"})
    assert digest.startswith("Task: Add digest")
    assert "Check: fail" in digest
    assert "SQL: yes (supabase/run-summary.sql)" in digest
    assert "Needs: credentials SUPABASE_SERVICE_ROLE_KEY; resources Supabase SQL editor access" in digest
    assert "Limitations: SQL was not applied" in digest


def test_digest_truncates_predictably():
    summary = {
        "files_created": [f"created-{idx}.txt" for idx in range(10)],
        "files_modified": [f"modified-{idx}.txt" for idx in range(10)],
        "check_result": True,
        "sql_required": False,
    }
    digest = build_run_summary_digest(summary, max_chars=80)
    assert len(digest) <= 80
    assert digest.endswith("…")


if __name__ == "__main__":
    import traceback
    tests = [
        test_canonical_check_result_pass,
        test_canonical_sql_not_required,
        test_canonical_commit_result,
        test_canonical_push_result,
        test_canonical_files_created,
        test_canonical_files_modified,
        test_sql_required_yes,
        test_sql_file_path,
        test_no_false_positive_sql_required_from_prose,
        test_no_false_positive_check_result_from_prose,
        test_no_false_positive_sql_required_sql_prose,
        test_push_skipped,
        test_list_does_not_bleed_into_next_section,
        test_empty_text,
        test_parse_includes_run_summary_digest,
        test_digest_includes_task_label_and_resource_needs,
        test_digest_truncates_predictably,
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
