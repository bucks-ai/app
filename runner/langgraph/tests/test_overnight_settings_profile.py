"""Tests for the overnight runner settings profile (profiles/overnight.env)."""
import os
from pathlib import Path
from dataclasses import fields

import pytest

from config import RunnerConfig

_PROFILE = Path(__file__).parent.parent / "profiles" / "overnight.env"


def _parse_profile() -> dict[str, str]:
    """Parse profiles/overnight.env into a key→value dict (skip comments/blanks)."""
    result = {}
    for line in _PROFILE.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, _, value = line.partition("=")
        result[key.strip()] = value.strip()
    return result


def test_profile_file_exists():
    assert _PROFILE.exists(), f"overnight.env profile not found at {_PROFILE}"


def test_profile_parses_without_error():
    data = _parse_profile()
    assert len(data) > 0


def test_all_profile_keys_are_known_env_vars():
    """Every key in the profile must correspond to a RunnerConfig env var or a
    credential key used by config.py — catches typos in the profile file."""
    # Build the set of env var names from RunnerConfig field defaults.
    # Each field uses os.getenv("VAR_NAME", ...) so we extract those names.
    import inspect, re
    import config as config_module

    # Scan the whole module so module-level helpers (e.g. _load_slack_events) are included.
    src = inspect.getsource(config_module)
    known_vars = set(re.findall(r'os\.getenv\("([^"]+)"', src))

    # Credential keys aren't always listed in field defaults but are well-known.
    known_vars.update({
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "GITHUB_TOKEN",
        "GITHUB_REPO",
        "GITHUB_REPOSITORY",
        "SUPABASE_URL",
        "SUPABASE_SERVICE_ROLE_KEY",
        "VERCEL_TOKEN",
        "VERCEL_PROJECT_ID",
        "SLACK_WEBHOOK_URL",
    })

    profile_keys = set(_parse_profile().keys())
    unknown = profile_keys - known_vars
    assert not unknown, f"Unknown env vars in overnight.env: {unknown}"


def test_overnight_key_settings():
    """Spot-check the overnight-specific tuning values."""
    data = _parse_profile()

    # Slack must be on
    assert data.get("SLACK_NOTIFY") == "true"

    # Seeded queue strict mode for clean stops
    assert data.get("SEEDED_MISSION_QUEUE_STRICT") == "true"

    # Merge policy must be auto (fully autonomous)
    assert data.get("MERGE_APPROVAL_POLICY") == "auto"

    # SQL approval must be off (would block indefinitely overnight)
    assert data.get("REQUIRE_SQL_APPROVAL") == "false"

    # Cost guard on
    assert data.get("COST_BUDGET_GUARD") == "true"

    # Session cost limit must be set (non-zero)
    cost = float(data.get("MAX_SESSION_COST_DOLLARS", "0"))
    assert cost > 0, "MAX_SESSION_COST_DOLLARS must be > 0 in the overnight profile"

    # Stale watchdog on
    assert data.get("STALE_RUN_WATCHDOG") == "true"

    # Warn before hard stop
    warn = int(data.get("STALE_RUN_WARN_MINUTES", "0"))
    hard = int(data.get("MAX_STALE_TASK_MINUTES", "0"))
    assert 0 < warn < hard, "STALE_RUN_WARN_MINUTES must be between 0 and MAX_STALE_TASK_MINUTES"

    # Backoff max must exceed base
    base = float(data.get("FAILURE_RETRY_BACKOFF_BASE_S", "0"))
    cap = float(data.get("FAILURE_RETRY_BACKOFF_MAX_S", "0"))
    assert cap > base

    # Live ping on
    assert data.get("WORKER_HEALTH_LIVE_PING") == "true"

    # More HTTP retries than default (3)
    assert int(data.get("HTTP_RETRY_ATTEMPTS", "0")) > 3

    # MAX_LOOP_TASKS must accommodate a long overnight run
    assert int(data.get("MAX_LOOP_TASKS", "0")) >= 20

    # Strict modes off (gates warn, not block)
    for key in (
        "ACCEPTANCE_CRITERIA_STRICT_MODE",
        "DEFINITION_OF_DONE_STRICT_MODE",
        "INDEPENDENT_CODE_REVIEW_STRICT_MODE",
        "HIGH_RISK_CLAUDE_REVIEW_STRICT_MODE",
        "BUSINESS_OUTPUT_RUBRICS_STRICT_MODE",
        "LAUNCH_READINESS_SCORECARD_STRICT_MODE",
    ):
        assert data.get(key) == "false", f"{key} must be false in the overnight profile"


def test_profile_loads_as_runner_config(monkeypatch):
    """Simulate loading the overnight profile as a RunnerConfig."""
    data = _parse_profile()
    # Patch env with profile values (use empty string for blank credentials)
    for k, v in data.items():
        monkeypatch.setenv(k, v)

    # Should not raise
    cfg = RunnerConfig()

    assert cfg.seeded_mission_queue_strict is True
    assert cfg.merge_approval_policy == "auto"
    assert cfg.slack_notify is True
    assert cfg.max_loop_tasks == 50
    assert cfg.worker_health_live_ping_enabled is True
    assert cfg.max_session_cost_dollars == 25.0
    assert cfg.stale_run_warn_minutes == 45
    assert cfg.max_stale_task_minutes == 90
