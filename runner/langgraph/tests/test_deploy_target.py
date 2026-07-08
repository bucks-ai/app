"""Unit tests for tools/deploy_target.py.

Runs standalone (no pytest dependency), mirroring test_resource_gate.py:

    python tests/test_deploy_target.py

Covers the pure ``resolve_target_url`` helper used by the E2E and UI flow
graph nodes to pick a base URL — ``E2E_BASE_URL`` must always win over the
Vercel-reported deploy URL.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.deploy_target import resolve_target_url


def test_env_override_wins_over_deploy_result():
    url, source = resolve_target_url("https://override.example.com", {"url": "https://deploy.vercel.app"})
    assert url == "https://override.example.com", url
    assert source == "env_override", source


def test_falls_back_to_deploy_result_url():
    url, source = resolve_target_url(None, {"url": "https://my-app.vercel.app"})
    assert url == "https://my-app.vercel.app", url
    assert source == "deploy_result", source


def test_falls_back_to_legacy_deployment_url_key():
    url, source = resolve_target_url(None, {"deployment_url": "https://legacy.vercel.app"})
    assert url == "https://legacy.vercel.app", url
    assert source == "deploy_result", source


def test_no_url_available_returns_none_none():
    url, source = resolve_target_url(None, {})
    assert url is None, url
    assert source is None, source


def test_no_url_available_handles_none_deploy_result():
    url, source = resolve_target_url(None, None)
    assert url is None, url
    assert source is None, source


def test_empty_env_override_falls_through():
    url, source = resolve_target_url("", {"url": "https://my-app.vercel.app"})
    assert url == "https://my-app.vercel.app", url
    assert source == "deploy_result", source


if __name__ == "__main__":
    tests = [
        test_env_override_wins_over_deploy_result,
        test_falls_back_to_deploy_result_url,
        test_falls_back_to_legacy_deployment_url_key,
        test_no_url_available_returns_none_none,
        test_no_url_available_handles_none_deploy_result,
        test_empty_env_override_falls_through,
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
