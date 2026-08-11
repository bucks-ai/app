"""Tests for tools/dependency_batch_ahead.py — roadmap dependency scan."""
import json
import pytest
from pathlib import Path
from unittest.mock import patch

from tools.dependency_batch_ahead import (
    run_batch_ahead_check,
    _format_batch_request,
    _load_queued_tasks,
    _ROADMAP_DEPS,
)


# ---------------------------------------------------------------------------
# _ROADMAP_DEPS completeness
# ---------------------------------------------------------------------------

def test_roadmap_deps_contains_ntfy_topic():
    assert "NTFY_TOPIC" in _ROADMAP_DEPS


def test_roadmap_deps_contains_supabase_management_key():
    assert "SUPABASE_MANAGEMENT_API_KEY" in _ROADMAP_DEPS


def test_roadmap_deps_contains_github_token():
    assert "GITHUB_TOKEN" in _ROADMAP_DEPS


def test_roadmap_deps_contains_vercel_token():
    assert "VERCEL_TOKEN" in _ROADMAP_DEPS


def test_roadmap_deps_all_screaming_snake_case():
    import re
    pattern = re.compile(r"^[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+$")
    for name in _ROADMAP_DEPS:
        assert pattern.match(name), f"{name!r} is not SCREAMING_SNAKE_CASE"


def test_roadmap_deps_purposes_non_empty():
    for name, purpose in _ROADMAP_DEPS.items():
        assert purpose.strip(), f"{name} has empty purpose"


# ---------------------------------------------------------------------------
# _format_batch_request — pure function
# ---------------------------------------------------------------------------

def test_format_batch_request_contains_inbox_filename():
    text = _format_batch_request([{"name": "FOO_BAR", "purpose": "test"}], "dep_provided.txt")
    assert "dep_provided.txt" in text


def test_format_batch_request_lists_credential_names():
    text = _format_batch_request(
        [
            {"name": "GITHUB_TOKEN", "purpose": "GitHub parent"},
            {"name": "NTFY_TOPIC", "purpose": "Phone push"},
        ],
        "dep.txt",
    )
    assert "GITHUB_TOKEN" in text
    assert "NTFY_TOPIC" in text


def test_format_batch_request_no_secret_values():
    text = _format_batch_request([{"name": "X_KEY", "purpose": "some key"}], "dep.txt")
    assert "paste values" not in text.lower() or "do not paste" in text.lower()
    assert "SECURITY NOTE" in text


# ---------------------------------------------------------------------------
# run_batch_ahead_check — integration with tmp dirs
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_dirs(tmp_path, monkeypatch):
    outbox = tmp_path / "outbox"
    inbox = tmp_path / "inbox"
    outbox.mkdir()
    inbox.mkdir()
    monkeypatch.setattr("tools.dependency_batch_ahead._OUTBOX_DIR", outbox)
    monkeypatch.setattr("tools.dependency_batch_ahead._INBOX_DIR", inbox)
    return {"outbox": outbox, "inbox": inbox, "tmp": tmp_path}


def test_run_batch_ahead_writes_outbox_on_missing_deps(tmp_dirs):
    available = {"OPENAI_API_KEY"}  # almost nothing configured
    result = run_batch_ahead_check(available=available)
    assert result["ran"] is True
    assert result["missing_count"] > 0
    assert (tmp_dirs["outbox"] / "dependency_batch_request.txt").exists()


def test_run_batch_ahead_skips_if_outbox_exists(tmp_dirs):
    (tmp_dirs["outbox"] / "dependency_batch_request.txt").write_text("already sent")
    result = run_batch_ahead_check(available=set())
    assert result["ran"] is False
    assert result["status"] == "already_sent"


def test_run_batch_ahead_skips_if_inbox_exists(tmp_dirs):
    (tmp_dirs["inbox"] / "dependency_batch_provided.txt").write_text("done")
    result = run_batch_ahead_check(available=set())
    assert result["ran"] is False
    assert result["status"] == "fulfilled"


def test_run_batch_ahead_all_present(tmp_dirs):
    available = set(_ROADMAP_DEPS.keys())
    result = run_batch_ahead_check(available=available)
    assert result["ran"] is True
    assert result["missing_count"] == 0
    assert result["status"] == "all_present"
    # Should NOT write an outbox file when nothing is missing
    assert not (tmp_dirs["outbox"] / "dependency_batch_request.txt").exists()


def test_run_batch_ahead_force_rewrites(tmp_dirs):
    (tmp_dirs["outbox"] / "dependency_batch_request.txt").write_text("old content")
    available = {"OPENAI_API_KEY"}
    result = run_batch_ahead_check(available=available, force=True)
    assert result["ran"] is True
    new_content = (tmp_dirs["outbox"] / "dependency_batch_request.txt").read_text()
    assert new_content != "old content"


def test_run_batch_ahead_fires_log_event(tmp_dirs, monkeypatch):
    events = []
    monkeypatch.setattr(
        "tools.dependency_batch_ahead.log_event",
        lambda etype, payload, **kw: events.append((etype, payload)),
    )
    run_batch_ahead_check(available={"OPENAI_API_KEY"})
    event_types = [e[0] for e in events]
    assert "dependency_batch_request" in event_types


def test_run_batch_ahead_missing_list_excludes_available(tmp_dirs):
    available = set(_ROADMAP_DEPS.keys()) - {"NTFY_TOPIC"}
    result = run_batch_ahead_check(available=available)
    assert result["missing_count"] == 1
    assert result["missing"][0]["name"] == "NTFY_TOPIC"


# ---------------------------------------------------------------------------
# _load_queued_tasks
# ---------------------------------------------------------------------------

def test_load_queued_tasks_returns_empty_when_no_file(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.dependency_batch_ahead._RUNTIME_DIR", tmp_path)
    result = _load_queued_tasks()
    assert result == []


def test_load_queued_tasks_filters_by_status(tmp_path, monkeypatch):
    monkeypatch.setattr("tools.dependency_batch_ahead._RUNTIME_DIR", tmp_path)
    tasks = [
        {"id": "t1", "status": "queued", "description": "foo"},
        {"id": "t2", "status": "complete", "description": "bar"},
        {"id": "t3", "status": "blocked", "description": "baz"},
    ]
    (tmp_path / "tasks.local.json").write_text(json.dumps(tasks))
    result = _load_queued_tasks()
    ids = [t["id"] for t in result]
    assert "t1" in ids
    assert "t3" in ids
    assert "t2" not in ids
