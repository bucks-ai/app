"""Unit tests for tools/mcp_connector_registry.py.

All functions under test are pure (no I/O, no graph state), so these tests
run without any mocking of the file system or network.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.mcp_connector_registry import (
    MCP_CONNECTOR_REGISTRY,
    build_mcp_server_config,
    format_connector_report,
    is_connector_available,
    list_connectors,
    select_connectors,
)


# ---------------------------------------------------------------------------
# MCP_CONNECTOR_REGISTRY structure
# ---------------------------------------------------------------------------

def test_registry_has_expected_connectors():
    assert "supabase" in MCP_CONNECTOR_REGISTRY
    assert "github" in MCP_CONNECTOR_REGISTRY
    assert "filesystem" in MCP_CONNECTOR_REGISTRY
    assert "slack" in MCP_CONNECTOR_REGISTRY


def test_each_connector_has_required_keys():
    required_keys = {"name", "description", "task_types", "keyword_hints",
                     "command", "args", "required_env", "env_passthrough"}
    for name, connector in MCP_CONNECTOR_REGISTRY.items():
        missing = required_keys - connector.keys()
        assert not missing, f"Connector '{name}' missing keys: {missing}"


def test_filesystem_requires_no_env():
    assert MCP_CONNECTOR_REGISTRY["filesystem"]["required_env"] == []


def test_supabase_requires_env_vars():
    required = MCP_CONNECTOR_REGISTRY["supabase"]["required_env"]
    assert "SUPABASE_URL" in required
    assert "SUPABASE_SERVICE_ROLE_KEY" in required


# ---------------------------------------------------------------------------
# is_connector_available
# ---------------------------------------------------------------------------

def test_available_when_all_env_vars_set():
    connector = MCP_CONNECTOR_REGISTRY["supabase"]
    env = {"SUPABASE_URL": "https://xyz.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "secret"}
    assert is_connector_available(connector, env) is True


def test_unavailable_when_env_var_missing():
    connector = MCP_CONNECTOR_REGISTRY["supabase"]
    env = {"SUPABASE_URL": "https://xyz.supabase.co"}
    assert is_connector_available(connector, env) is False


def test_unavailable_when_env_var_empty():
    connector = MCP_CONNECTOR_REGISTRY["github"]
    env = {"GITHUB_TOKEN": ""}
    assert is_connector_available(connector, env) is False


def test_filesystem_always_available():
    connector = MCP_CONNECTOR_REGISTRY["filesystem"]
    assert is_connector_available(connector, {}) is True


def test_uses_os_environ_when_env_is_none(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "test-token")
    connector = MCP_CONNECTOR_REGISTRY["github"]
    assert is_connector_available(connector, None) is True


# ---------------------------------------------------------------------------
# select_connectors
# ---------------------------------------------------------------------------

def _full_env():
    return {
        "SUPABASE_URL": "https://xyz.supabase.co",
        "SUPABASE_SERVICE_ROLE_KEY": "secret",
        "GITHUB_TOKEN": "gh-token",
        "SLACK_BOT_TOKEN": "xoxb-token",
        "SLACK_TEAM_ID": "T12345",
    }


def test_select_by_task_type_backend():
    task = {"type": "backend", "title": "", "description": ""}
    result = select_connectors(task, env=_full_env())
    names = [c["name"] for c in result]
    assert "supabase" in names
    assert "github" in names
    assert "filesystem" in names


def test_select_by_keyword_hint():
    task = {"type": "general", "title": "fix the supabase rls policy", "description": ""}
    result = select_connectors(task, env=_full_env())
    names = [c["name"] for c in result]
    assert "supabase" in names


def test_select_by_keyword_in_description():
    task = {"type": "general", "title": "misc", "description": "update github issue status"}
    result = select_connectors(task, env=_full_env())
    names = [c["name"] for c in result]
    assert "github" in names


def test_unavailable_connectors_excluded():
    task = {"type": "backend", "title": "", "description": ""}
    env = {}  # no credentials set
    result = select_connectors(task, env=env)
    names = [c["name"] for c in result]
    # Only filesystem (no required env) should pass
    assert "supabase" not in names
    assert "github" not in names
    assert "slack" not in names
    assert "filesystem" in names


def test_no_match_returns_empty_when_no_creds():
    task = {"type": "unknown_type", "title": "make coffee", "description": "brew a latte"}
    env = {}
    result = select_connectors(task, env=env)
    assert result == []


def test_no_duplicate_connectors():
    # A task type match AND a keyword match should not duplicate the connector
    task = {"type": "backend", "title": "supabase migration", "description": ""}
    result = select_connectors(task, env=_full_env())
    names = [c["name"] for c in result]
    assert len(names) == len(set(names))


def test_select_handles_missing_task_fields():
    task = {}
    result = select_connectors(task, env={})
    # Should not raise and should return only connectors with no required env
    names = [c["name"] for c in result]
    assert "filesystem" not in names  # no keyword/type match for empty task
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# build_mcp_server_config
# ---------------------------------------------------------------------------

def test_build_config_returns_correct_shape():
    connector = MCP_CONNECTOR_REGISTRY["supabase"]
    env = {"SUPABASE_URL": "https://xyz.supabase.co", "SUPABASE_SERVICE_ROLE_KEY": "secret"}
    configs = build_mcp_server_config([connector], env=env)
    assert len(configs) == 1
    cfg = configs[0]
    assert cfg["name"] == "supabase"
    assert cfg["command"] == "npx"
    assert isinstance(cfg["args"], list)
    assert cfg["env"]["SUPABASE_URL"] == "https://xyz.supabase.co"
    assert cfg["env"]["SUPABASE_SERVICE_ROLE_KEY"] == "secret"


def test_build_config_omits_missing_env_vars():
    connector = MCP_CONNECTOR_REGISTRY["supabase"]
    env = {"SUPABASE_URL": "https://xyz.supabase.co"}  # key missing
    configs = build_mcp_server_config([connector], env=env)
    assert "SUPABASE_SERVICE_ROLE_KEY" not in configs[0]["env"]


def test_build_config_filesystem_has_empty_env():
    connector = MCP_CONNECTOR_REGISTRY["filesystem"]
    configs = build_mcp_server_config([connector], env={})
    assert configs[0]["env"] == {}


def test_build_config_multiple_connectors():
    connectors = [
        MCP_CONNECTOR_REGISTRY["filesystem"],
        MCP_CONNECTOR_REGISTRY["github"],
    ]
    env = {"GITHUB_TOKEN": "gh-token"}
    configs = build_mcp_server_config(connectors, env=env)
    assert len(configs) == 2
    names = [c["name"] for c in configs]
    assert "filesystem" in names
    assert "github" in names


def test_build_config_empty_list():
    assert build_mcp_server_config([], env={}) == []


def test_build_config_uses_os_environ_when_none(monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", "env-token")
    connector = MCP_CONNECTOR_REGISTRY["github"]
    configs = build_mcp_server_config([connector], env=None)
    assert configs[0]["env"].get("GITHUB_TOKEN") == "env-token"


# ---------------------------------------------------------------------------
# format_connector_report
# ---------------------------------------------------------------------------

def test_report_contains_header():
    report = format_connector_report([], all_connectors=[])
    assert "MCP Connector Registry" in report


def test_report_shows_selected_count():
    selected = [MCP_CONNECTOR_REGISTRY["filesystem"]]
    all_c = list(MCP_CONNECTOR_REGISTRY.values())
    report = format_connector_report(selected, all_connectors=all_c)
    assert "1 /" in report or "Selected connectors: 1" in report


def test_report_marks_selected_connector():
    selected = [MCP_CONNECTOR_REGISTRY["filesystem"]]
    all_c = [MCP_CONNECTOR_REGISTRY["filesystem"]]
    report = format_connector_report(selected, all_connectors=all_c)
    assert "[+]" in report


def test_report_marks_unavailable_connector():
    selected = []
    all_c = [MCP_CONNECTOR_REGISTRY["supabase"]]
    report = format_connector_report(selected, all_connectors=all_c)
    assert "[-]" in report or "unavailable" in report


def test_report_uses_all_registry_when_none_given():
    report = format_connector_report([])
    for name in MCP_CONNECTOR_REGISTRY:
        assert name in report


# ---------------------------------------------------------------------------
# list_connectors
# ---------------------------------------------------------------------------

def test_list_connectors_returns_all():
    result = list_connectors()
    names = [c["name"] for c in result]
    for key in MCP_CONNECTOR_REGISTRY:
        assert key in names


def test_list_connectors_sorted():
    result = list_connectors()
    names = [c["name"] for c in result]
    assert names == sorted(names)


def test_list_connectors_has_name_and_description():
    result = list_connectors()
    for entry in result:
        assert "name" in entry
        assert "description" in entry
        assert isinstance(entry["description"], str)
        assert len(entry["description"]) > 0
