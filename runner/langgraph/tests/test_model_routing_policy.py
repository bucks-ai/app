"""Unit tests for model routing policy.

Runs standalone:

    python tests/test_model_routing_policy.py
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.model_routing_policy import (
    normalize_policy,
    resolve_model,
    evaluate_model_routing_policy,
    format_routing_summary,
)


def test_normalize_policy_values():
    assert normalize_policy(None) == "default"
    assert normalize_policy("performance") == "performance"
    assert normalize_policy("ECONOMY") == "economy"
    assert normalize_policy("latency-fast") == "default"  # normalized but unknown → default
    assert normalize_policy("off") == "disabled"
    assert normalize_policy("false") == "disabled"
    assert normalize_policy("unknown_tier") == "default"


def test_normalize_valid_policies():
    for p in ("default", "performance", "economy", "latency", "disabled"):
        assert normalize_policy(p) == p


def test_resolve_model_by_policy_tier_claude():
    assert resolve_model("claude", "default") == "claude-sonnet-4-6"
    assert resolve_model("claude", "performance") == "claude-opus-4-8"
    assert resolve_model("claude", "economy") == "claude-haiku-4-5-20251001"
    assert resolve_model("claude", "latency") == "claude-haiku-4-5-20251001"


def test_resolve_model_by_policy_tier_chatgpt():
    assert resolve_model("chatgpt", "default") == "gpt-4o"
    assert resolve_model("chatgpt", "performance") == "gpt-4o"
    assert resolve_model("chatgpt", "economy") == "gpt-4o-mini"
    assert resolve_model("chatgpt", "latency") == "gpt-4o-mini"


def test_resolve_model_by_policy_tier_codex():
    assert resolve_model("codex", "default") == "gpt-4o"
    assert resolve_model("codex", "economy") == "gpt-4o-mini"


def test_resolve_model_task_override_wins():
    model = resolve_model("claude", "economy", task_model_override="claude-opus-4-8")
    assert model == "claude-opus-4-8"


def test_resolve_model_config_override_wins_over_policy():
    model = resolve_model("claude", "economy", config_model_override="claude-sonnet-4-6")
    assert model == "claude-sonnet-4-6"


def test_resolve_model_task_override_beats_config_override():
    model = resolve_model(
        "claude", "economy",
        task_model_override="claude-opus-4-8",
        config_model_override="claude-sonnet-4-6",
    )
    assert model == "claude-opus-4-8"


def test_resolve_model_disabled_policy_returns_none():
    assert resolve_model("claude", "disabled") is None
    assert resolve_model("chatgpt", "disabled") is None
    assert resolve_model("codex", "disabled") is None


def test_resolve_model_disabled_ignores_config_override():
    # disabled means don't resolve at all — even if a config override is present
    assert resolve_model("claude", "disabled", config_model_override="claude-opus-4-8") is None


def test_resolve_model_unknown_worker_returns_none():
    assert resolve_model("unknown_worker", "default") is None
    assert resolve_model("", "performance") is None


def test_evaluate_model_routing_policy_default():
    decision = evaluate_model_routing_policy(
        worker="claude",
        policy="default",
        task={"id": "t1"},
    )
    assert decision["resolved_model"] == "claude-sonnet-4-6"
    assert decision["policy"] == "default"
    assert decision["source"] == "policy"
    assert decision["task_id"] == "t1"


def test_evaluate_model_routing_policy_performance():
    decision = evaluate_model_routing_policy(
        worker="claude",
        policy="performance",
        task={"id": "t2"},
    )
    assert decision["resolved_model"] == "claude-opus-4-8"
    assert decision["source"] == "policy"


def test_evaluate_model_routing_policy_economy():
    decision = evaluate_model_routing_policy(
        worker="chatgpt",
        policy="economy",
        task={"id": "t3"},
    )
    assert decision["resolved_model"] == "gpt-4o-mini"
    assert decision["source"] == "policy"


def test_evaluate_model_routing_policy_task_override():
    decision = evaluate_model_routing_policy(
        worker="claude",
        policy="economy",
        task={"id": "t4", "preferred_model": "claude-opus-4-8"},
    )
    assert decision["resolved_model"] == "claude-opus-4-8"
    assert decision["source"] == "task_override"


def test_evaluate_model_routing_policy_config_override():
    decision = evaluate_model_routing_policy(
        worker="claude",
        policy="economy",
        task={"id": "t5"},
        config_model_override="claude-sonnet-4-6",
    )
    assert decision["resolved_model"] == "claude-sonnet-4-6"
    assert decision["source"] == "config_override"


def test_evaluate_model_routing_policy_disabled():
    decision = evaluate_model_routing_policy(
        worker="claude",
        policy="disabled",
        task={"id": "t6"},
    )
    assert decision["resolved_model"] is None
    assert decision["source"] == "disabled"
    assert decision["policy"] == "disabled"


def test_evaluate_model_routing_policy_none_worker():
    decision = evaluate_model_routing_policy(
        worker=None,
        policy="performance",
        task={"id": "t7"},
    )
    assert decision["resolved_model"] is None
    assert decision["worker"] is None


def test_format_routing_summary_includes_key_fields():
    decision = evaluate_model_routing_policy(
        worker="claude",
        policy="performance",
        task={"id": "task-abc"},
    )
    text = format_routing_summary(decision)
    assert "Model Routing Decision" in text
    assert "claude-opus-4-8" in text
    assert "performance" in text
    assert "task-abc" in text


def test_format_routing_summary_disabled():
    decision = evaluate_model_routing_policy(
        worker="claude",
        policy="disabled",
        task={"id": "t8"},
    )
    text = format_routing_summary(decision)
    assert "(worker default)" in text


if __name__ == "__main__":
    tests = [
        test_normalize_policy_values,
        test_normalize_valid_policies,
        test_resolve_model_by_policy_tier_claude,
        test_resolve_model_by_policy_tier_chatgpt,
        test_resolve_model_by_policy_tier_codex,
        test_resolve_model_task_override_wins,
        test_resolve_model_config_override_wins_over_policy,
        test_resolve_model_task_override_beats_config_override,
        test_resolve_model_disabled_policy_returns_none,
        test_resolve_model_disabled_ignores_config_override,
        test_resolve_model_unknown_worker_returns_none,
        test_evaluate_model_routing_policy_default,
        test_evaluate_model_routing_policy_performance,
        test_evaluate_model_routing_policy_economy,
        test_evaluate_model_routing_policy_task_override,
        test_evaluate_model_routing_policy_config_override,
        test_evaluate_model_routing_policy_disabled,
        test_evaluate_model_routing_policy_none_worker,
        test_format_routing_summary_includes_key_fields,
        test_format_routing_summary_disabled,
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
