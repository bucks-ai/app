"""Tests for tools/claude_subagent_pack.py."""
import pytest
from tools.claude_subagent_pack import (
    SUBAGENT_REGISTRY,
    select_subagent,
    build_subagent_prompt_prefix,
    list_subagents,
)


# ---------------------------------------------------------------------------
# select_subagent — explicit override
# ---------------------------------------------------------------------------

def test_preferred_subagent_override_respected():
    task = {"id": "t", "title": "something", "type": "general", "preferred_subagent": "testing"}
    assert select_subagent(task)["name"] == "testing"


def test_preferred_subagent_unknown_falls_through_to_type_match():
    # "nope" is not in the registry, so falls through to task_type match
    task = {"id": "t", "title": "write tests", "type": "testing", "preferred_subagent": "nope"}
    assert select_subagent(task)["name"] == "testing"


def test_preferred_subagent_empty_string_falls_through():
    task = {"id": "t", "title": "api work", "type": "backend", "preferred_subagent": ""}
    assert select_subagent(task)["name"] == "backend"


# ---------------------------------------------------------------------------
# select_subagent — task_type matching
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("task_type,expected_role", [
    ("backend", "backend"),
    ("api", "backend"),
    ("schema", "backend"),
    ("database", "backend"),
    ("testing", "testing"),
    ("test", "testing"),
    ("qa", "testing"),
    ("review", "review"),
    ("audit", "review"),
    ("security", "review"),
    ("agent", "agent"),
    ("runner", "agent"),
    ("langgraph", "agent"),
    ("ui", "frontend"),
    ("frontend", "frontend"),
    ("polish", "frontend"),
    ("design", "frontend"),
])
def test_task_type_routing(task_type, expected_role):
    task = {"id": "t", "title": "some task", "type": task_type}
    assert select_subagent(task)["name"] == expected_role


def test_unknown_task_type_falls_to_general():
    task = {"id": "t", "title": "random thing", "type": "unknown_xyz"}
    assert select_subagent(task)["name"] == "general"


# ---------------------------------------------------------------------------
# select_subagent — keyword matching
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("title,expected_role", [
    ("Add new REST endpoint for users", "backend"),
    ("Migrate database schema", "backend"),
    ("Write unit tests for auth module", "testing"),
    ("Fix coverage gaps in pytest suite", "testing"),
    ("Review PR for security vulnerabilities", "review"),
    ("Build LangGraph orchestration node", "agent"),
    ("Add guard to runner loop", "agent"),
    ("Create React component for modal", "frontend"),
    ("Polish the landing page layout", "frontend"),
])
def test_keyword_matching_on_title(title, expected_role):
    task = {"id": "t", "title": title, "type": "general"}
    assert select_subagent(task)["name"] == expected_role


def test_keyword_matching_on_description():
    task = {
        "id": "t",
        "title": "improve the system",
        "type": "general",
        "description": "we need to add a new supabase rpc endpoint for fetching data",
    }
    assert select_subagent(task)["name"] == "backend"


def test_no_keyword_match_falls_to_general():
    task = {"id": "t", "title": "miscellaneous chore", "type": "general"}
    assert select_subagent(task)["name"] == "general"


# ---------------------------------------------------------------------------
# select_subagent — missing / None fields
# ---------------------------------------------------------------------------

def test_empty_task_returns_general():
    assert select_subagent({})["name"] == "general"


def test_none_type_handled():
    task = {"id": "t", "title": "task", "type": None}
    result = select_subagent(task)
    assert result["name"] in SUBAGENT_REGISTRY


# ---------------------------------------------------------------------------
# build_subagent_prompt_prefix
# ---------------------------------------------------------------------------

def test_prefix_empty_for_general():
    general = SUBAGENT_REGISTRY["general"]
    assert build_subagent_prompt_prefix(general) == ""


def test_prefix_contains_subagent_name():
    backend = SUBAGENT_REGISTRY["backend"]
    prefix = build_subagent_prompt_prefix(backend)
    assert "[Subagent: backend]" in prefix


def test_prefix_contains_system_context():
    agent = SUBAGENT_REGISTRY["agent"]
    prefix = build_subagent_prompt_prefix(agent)
    assert agent["system_context"] in prefix


def test_prefix_ends_with_double_newline():
    testing = SUBAGENT_REGISTRY["testing"]
    prefix = build_subagent_prompt_prefix(testing)
    assert prefix.endswith("\n\n")


def test_prefix_empty_dict_returns_empty():
    assert build_subagent_prompt_prefix({}) == ""


# ---------------------------------------------------------------------------
# list_subagents
# ---------------------------------------------------------------------------

def test_list_subagents_returns_all_roles():
    names = {s["name"] for s in list_subagents()}
    assert names == set(SUBAGENT_REGISTRY.keys())


def test_list_subagents_sorted_by_name():
    names = [s["name"] for s in list_subagents()]
    assert names == sorted(names)


def test_list_subagents_has_description():
    for entry in list_subagents():
        assert "description" in entry
        assert entry["description"]


# ---------------------------------------------------------------------------
# Registry completeness
# ---------------------------------------------------------------------------

def test_all_roles_have_required_keys():
    required = {"name", "description", "task_types", "keyword_hints", "system_context"}
    for name, cfg in SUBAGENT_REGISTRY.items():
        missing = required - set(cfg.keys())
        assert not missing, f"Role '{name}' missing keys: {missing}"


def test_general_role_has_empty_system_context():
    assert SUBAGENT_REGISTRY["general"]["system_context"] == ""
