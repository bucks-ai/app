"""Tests for sql_environment_gate — environment-aware SQL approval policy."""
import pytest
from tools.sql_environment_gate import evaluate_sql_approval_policy, infer_environment


# ---------------------------------------------------------------------------
# infer_environment
# ---------------------------------------------------------------------------

class TestInferEnvironment:
    def test_returns_development_when_url_is_none(self):
        assert infer_environment(None) == "development"

    def test_returns_development_when_url_is_empty(self):
        assert infer_environment("") == "development"

    def test_detects_production_url(self):
        assert infer_environment("https://abc-prod.supabase.co") == "production"

    def test_detects_production_url_uppercase(self):
        assert infer_environment("https://abc-PROD.supabase.co") == "production"

    def test_detects_staging_url(self):
        assert infer_environment("https://abc-stag.supabase.co") == "staging"

    def test_detects_staging_url_full_word(self):
        assert infer_environment("https://staging-xyz.supabase.co") == "staging"

    def test_production_takes_priority_over_staging(self):
        # prod appears first in regex; if both match, production wins
        url = "https://prod-staging.supabase.co"
        assert infer_environment(url) == "production"

    def test_returns_development_for_generic_url(self):
        assert infer_environment("https://abc-dev.supabase.co") == "development"

    def test_returns_development_for_local_url(self):
        assert infer_environment("http://localhost:54321") == "development"


# ---------------------------------------------------------------------------
# evaluate_sql_approval_policy — policy=auto
# ---------------------------------------------------------------------------

class TestPolicyAuto:
    def test_auto_never_requires_approval(self):
        result = evaluate_sql_approval_policy({}, "production", "auto")
        assert result["approval_required"] is False

    def test_auto_returns_informative_reason(self):
        result = evaluate_sql_approval_policy({}, "development", "auto")
        assert "auto" in result["reason"].lower()
        assert "legacy" in result["reason"].lower()


# ---------------------------------------------------------------------------
# evaluate_sql_approval_policy — policy=require_on_production
# ---------------------------------------------------------------------------

class TestPolicyRequireOnProduction:
    def test_requires_approval_in_production(self):
        result = evaluate_sql_approval_policy({}, "production", "require_on_production")
        assert result["approval_required"] is True

    def test_no_approval_in_staging(self):
        result = evaluate_sql_approval_policy({}, "staging", "require_on_production")
        assert result["approval_required"] is False

    def test_no_approval_in_development(self):
        result = evaluate_sql_approval_policy({}, "development", "require_on_production")
        assert result["approval_required"] is False

    def test_no_approval_in_preview(self):
        result = evaluate_sql_approval_policy({}, "preview", "require_on_production")
        assert result["approval_required"] is False

    def test_reason_mentions_environment(self):
        result = evaluate_sql_approval_policy({}, "production", "require_on_production")
        assert "production" in result["reason"]

    def test_case_insensitive_environment(self):
        result = evaluate_sql_approval_policy({}, "PRODUCTION", "require_on_production")
        assert result["approval_required"] is True


# ---------------------------------------------------------------------------
# evaluate_sql_approval_policy — policy=require_on_warning
# ---------------------------------------------------------------------------

class TestPolicyRequireOnWarning:
    _clean_scan = {"ok": True, "warnings": [], "blocked_terms": []}
    _warn_scan = {"ok": True, "warnings": ["alter table (review carefully)"], "blocked_terms": []}
    _blocked_scan = {"ok": False, "warnings": [], "blocked_terms": ["truncate"]}
    _both_scan = {"ok": False, "warnings": ["alter table"], "blocked_terms": ["drop schema"]}

    def test_no_approval_for_clean_scan(self):
        result = evaluate_sql_approval_policy(self._clean_scan, "production", "require_on_warning")
        assert result["approval_required"] is False

    def test_requires_approval_when_warnings_present(self):
        result = evaluate_sql_approval_policy(self._warn_scan, "development", "require_on_warning")
        assert result["approval_required"] is True

    def test_requires_approval_when_blocked_terms_present(self):
        result = evaluate_sql_approval_policy(self._blocked_scan, "development", "require_on_warning")
        assert result["approval_required"] is True

    def test_requires_approval_when_both_present(self):
        result = evaluate_sql_approval_policy(self._both_scan, "staging", "require_on_warning")
        assert result["approval_required"] is True

    def test_reason_mentions_warning_count(self):
        result = evaluate_sql_approval_policy(self._warn_scan, "production", "require_on_warning")
        assert "1" in result["reason"]

    def test_empty_scan_result_treated_as_clean(self):
        result = evaluate_sql_approval_policy({}, "production", "require_on_warning")
        assert result["approval_required"] is False


# ---------------------------------------------------------------------------
# evaluate_sql_approval_policy — policy=always_require
# ---------------------------------------------------------------------------

class TestPolicyAlwaysRequire:
    def test_requires_approval_in_development(self):
        result = evaluate_sql_approval_policy({}, "development", "always_require")
        assert result["approval_required"] is True

    def test_requires_approval_in_production(self):
        result = evaluate_sql_approval_policy({}, "production", "always_require")
        assert result["approval_required"] is True

    def test_requires_approval_in_preview(self):
        result = evaluate_sql_approval_policy({}, "preview", "always_require")
        assert result["approval_required"] is True

    def test_reason_mentions_all_environments(self):
        result = evaluate_sql_approval_policy({}, "staging", "always_require")
        assert "all" in result["reason"].lower() or "always" in result["reason"].lower()


# ---------------------------------------------------------------------------
# evaluate_sql_approval_policy — unknown policy
# ---------------------------------------------------------------------------

class TestUnknownPolicy:
    def test_unknown_policy_defaults_to_require(self):
        result = evaluate_sql_approval_policy({}, "development", "bogus_policy")
        assert result["approval_required"] is True

    def test_unknown_policy_reason_mentions_policy_name(self):
        result = evaluate_sql_approval_policy({}, "development", "bogus_policy")
        assert "bogus_policy" in result["reason"]


# ---------------------------------------------------------------------------
# Return type contract
# ---------------------------------------------------------------------------

class TestReturnContract:
    def test_always_returns_approval_required_bool(self):
        for policy in ("auto", "require_on_production", "require_on_warning", "always_require"):
            result = evaluate_sql_approval_policy({}, "production", policy)
            assert isinstance(result["approval_required"], bool), f"failed for policy={policy}"

    def test_always_returns_reason_string(self):
        for policy in ("auto", "require_on_production", "require_on_warning", "always_require"):
            result = evaluate_sql_approval_policy({}, "staging", policy)
            assert isinstance(result["reason"], str) and result["reason"], f"failed for policy={policy}"
