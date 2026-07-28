"""Unit tests for tools/business_sandbox.py — the M4b sandbox-config
reconciliation module.

Runs standalone (no pytest dependency), mirroring test_foreign_repo_workspace.py:

    python tests/test_business_sandbox.py

Covers:
  - ``is_sandbox_configured`` pure helper (mirrors
    src/lib/sandbox.ts::computeSandboxStatus() == "configured").
  - ``fetch_business_sandbox`` against a stubbed Supabase client: found row,
    no row (None business_id in table), and graceful degradation on error.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.business_sandbox import (
    SANDBOX_FIELDS,
    fetch_business_sandbox,
    is_sandbox_configured,
)
import tools.business_sandbox as bs

# Silence the flight recorder during tests.
bs.log_event = lambda *a, **k: None

_FULL_SANDBOX = {
    "repo_full_name": "acme/landing",
    "vercel_project_id": "prj_acme",
    "github_token_secret_name": "ACME_GITHUB_TOKEN",
    "vercel_token_secret_name": "ACME_VERCEL_TOKEN",
    "status": "configured",
}


# ---------------------------------------------------------------------------
# is_sandbox_configured — pure helper
# ---------------------------------------------------------------------------

def test_is_sandbox_configured_true_for_full_row():
    assert is_sandbox_configured(_FULL_SANDBOX) is True


def test_is_sandbox_configured_false_for_none():
    assert is_sandbox_configured(None) is False


def test_is_sandbox_configured_false_for_empty_dict():
    assert is_sandbox_configured({}) is False


def test_is_sandbox_configured_false_when_one_field_missing():
    partial = dict(_FULL_SANDBOX)
    del partial["vercel_token_secret_name"]
    assert is_sandbox_configured(partial) is False


def test_is_sandbox_configured_false_for_blank_string_fields():
    blank = {field: "   " for field in SANDBOX_FIELDS}
    assert is_sandbox_configured(blank) is False


# ---------------------------------------------------------------------------
# fetch_business_sandbox — stubbed Supabase client
# ---------------------------------------------------------------------------

def _stub_create_client(rows):
    """Return a fake ``supabase.create_client`` whose ``.eq("business_id",
    value)`` actually filters *rows*, mirroring the fake client pattern in
    tests/test_seeded_mission_queue.py."""
    class FakeResult:
        def __init__(self, data):
            self.data = data

    class FakeQuery:
        def __init__(self, rows):
            self._rows = rows

        def select(self, *a):
            return self

        def eq(self, field, value):
            self._rows = [r for r in self._rows if r.get(field) == value]
            return self

        def limit(self, n):
            self._rows = self._rows[:n]
            return self

        def execute(self):
            return FakeResult(self._rows)

    class FakeTable:
        def table(self, name):
            assert name == "business_sandbox"
            return FakeQuery(rows)

    def _create_client(url, key):
        return FakeTable()

    return _create_client


def _with_stub_supabase(rows, fn):
    import config
    import supabase as supabase_module
    original_get_config = config.get_config
    original_create_client = supabase_module.create_client
    config.get_config = lambda: type(
        "Cfg", (), {"supabase_url": "https://x.supabase.co", "supabase_service_role_key": "key"}
    )()
    supabase_module.create_client = _stub_create_client(rows)
    try:
        return fn()
    finally:
        config.get_config = original_get_config
        supabase_module.create_client = original_create_client


def test_fetch_business_sandbox_returns_row_when_found():
    rows = [dict(_FULL_SANDBOX, business_id="biz-1")]
    result = _with_stub_supabase(rows, lambda: fetch_business_sandbox("biz-1"))
    assert result is not None
    assert result["repo_full_name"] == "acme/landing"


def test_fetch_business_sandbox_returns_none_when_no_row():
    rows = [dict(_FULL_SANDBOX, business_id="biz-other")]
    result = _with_stub_supabase(rows, lambda: fetch_business_sandbox("biz-1"))
    assert result is None


def test_fetch_business_sandbox_degrades_gracefully_on_error():
    import config
    original_get_config = config.get_config

    def _raise():
        raise RuntimeError("supabase unreachable")

    config.get_config = _raise
    try:
        result = fetch_business_sandbox("biz-1")
    finally:
        config.get_config = original_get_config
    assert result is None


if __name__ == "__main__":
    tests = [
        test_is_sandbox_configured_true_for_full_row,
        test_is_sandbox_configured_false_for_none,
        test_is_sandbox_configured_false_for_empty_dict,
        test_is_sandbox_configured_false_when_one_field_missing,
        test_is_sandbox_configured_false_for_blank_string_fields,
        test_fetch_business_sandbox_returns_row_when_found,
        test_fetch_business_sandbox_returns_none_when_no_row,
        test_fetch_business_sandbox_degrades_gracefully_on_error,
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
