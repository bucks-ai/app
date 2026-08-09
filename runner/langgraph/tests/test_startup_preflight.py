"""Unit tests for the M4c.0 startup preflight.

Runs standalone (no pytest dependency):

    python tests/test_startup_preflight.py

Every check exists because of a real incident, so the tests are written against
those incidents rather than against the happy path:

  - a migration file merged but never recorded in the ``_runner_migrations``
    ledger (M4a — Execute 500'd for a whole mission);
  - a Vercel project that is reachable but NOT git-connected, and a production
    deployment whose commit is not ``origin/main`` (M4b — production served
    stale code for hours while ``main`` moved);
  - a ``GITHUB_REPO`` that 404s for the configured token (``testflow`` vs
    ``testflow-demo`` — burned a full run before failing at clone).

The behavioural invariant under test throughout: the preflight REPORTS. Only
``git_state`` may halt. Every check is injected with a fake reader, so none of
this touches the network, a database, or git.
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.startup_preflight import (
    PASS, WARN, FAIL, SKIP,
    DEFAULT_REQUIRED_TABLES,
    make_check,
    check_git_state,
    check_pending_migrations,
    check_production_sha,
    check_vercel_project,
    check_github_repo,
    check_required_tables,
    check_credentials,
    required_credentials,
    deployment_commit_sha,
    interpret_vercel_project,
    summarize_checks,
    format_preflight_report,
    run_startup_preflight,
    guard_startup_preflight,
)
import tools.startup_preflight as sp


def _status(check, expected):
    assert check["status"] == expected, f"{check['name']}: {check['status']} != {expected} ({check['detail']})"


# ---------------------------------------------------------------------------
# git_state — the ONLY halting check
# ---------------------------------------------------------------------------

def test_git_state_passes_on_clean_main():
    check = check_git_state("/repo", evaluate=lambda p: {"ok": True, "branch": "main"})
    _status(check, PASS)
    assert check["halting"] is False


def test_git_state_is_halting_when_tree_is_dirty():
    check = check_git_state("/repo", evaluate=lambda p: {
        "ok": False, "reason": "dirty_working_tree", "branch": "main",
        "dirty": True, "message": "uncommitted changes",
    })
    _status(check, FAIL)
    assert check["halting"] is True, "a dirty tree must halt — workers inherit this tree"


def test_git_state_is_halting_on_wrong_branch():
    check = check_git_state("/repo", evaluate=lambda p: {
        "ok": False, "reason": "non_main_branch", "branch": "fix/x",
        "dirty": False, "message": "not on main",
    })
    _status(check, FAIL)
    assert check["halting"] is True


# ---------------------------------------------------------------------------
# pending_migrations — the M4a incident
# ---------------------------------------------------------------------------

def test_pending_migrations_warns_and_names_the_files():
    check = check_pending_migrations("/m", True, list_fn=lambda d: {
        "success": True, "data": {"pending": ["003_x.sql", "004_y.sql"], "total_count": 4},
    })
    _status(check, WARN)
    assert "003_x.sql" in check["detail"] and "004_y.sql" in check["detail"]
    assert check["halting"] is False


def test_pending_migrations_passes_when_ledger_is_complete():
    check = check_pending_migrations("/m", True, list_fn=lambda d: {
        "success": True, "data": {"pending": [], "total_count": 7},
    })
    _status(check, PASS)


def test_pending_migrations_warns_when_ledger_is_unreadable():
    # An unreadable ledger is NOT "no pending migrations" — the M1 failure was
    # precisely a ledger table that did not exist in production.
    check = check_pending_migrations("/m", True, list_fn=lambda d: {
        "success": False, "error": "relation _runner_migrations does not exist",
    })
    _status(check, WARN)


def test_pending_migrations_skips_without_a_database():
    _status(check_pending_migrations("/m", False), SKIP)


# ---------------------------------------------------------------------------
# production_sha / vercel_project — the M4b outage
# ---------------------------------------------------------------------------

def test_deployment_commit_sha_reads_any_git_provider():
    assert deployment_commit_sha({"meta": {"githubCommitSha": "abc123"}}) == "abc123"
    assert deployment_commit_sha({"meta": {"gitlabCommitSha": "def456"}}) == "def456"
    assert deployment_commit_sha({"meta": {}}) == ""
    assert deployment_commit_sha({}) == ""


def _sha_check(origin, deployed):
    return check_production_sha(
        "/repo", "prj_1", True,
        origin_sha_fn=lambda p: origin,
        deployment_fn=lambda pid: {
            "available": True, "deployment": {"meta": {"githubCommitSha": deployed}},
        },
    )


def test_production_sha_passes_when_production_serves_main():
    _status(_sha_check("a" * 40, "a" * 40), PASS)


def test_production_sha_fails_when_production_is_stale():
    check = _sha_check("a" * 40, "b" * 40)
    _status(check, FAIL)
    assert check["halting"] is False, "stale production is loud, but must not stop the loop"
    assert check["data"]["deployed_sha"] == "b" * 7


def test_production_sha_warns_when_deployment_has_no_commit():
    check = check_production_sha(
        "/repo", "prj_1", True,
        origin_sha_fn=lambda p: "a" * 40,
        deployment_fn=lambda pid: {"available": True, "deployment": {"meta": {}}},
    )
    _status(check, WARN)


def test_production_sha_warns_when_vercel_is_unreachable():
    check = check_production_sha(
        "/repo", "prj_1", True,
        origin_sha_fn=lambda p: "a" * 40,
        deployment_fn=lambda pid: {"available": False, "error": "timeout"},
    )
    _status(check, WARN)


def test_production_sha_skips_without_vercel_token():
    _status(check_production_sha("/repo", "prj_1", False), SKIP)


def test_interpret_vercel_project_detects_a_missing_link():
    assert interpret_vercel_project({})["connected"] is False
    linked = interpret_vercel_project(
        {"link": {"type": "github", "org": "acme", "repo": "app"}}
    )
    assert linked["connected"] is True
    assert linked["repo"] == "acme/app"


def test_vercel_project_fails_when_not_git_connected():
    # The M4b outage exactly: reachable, healthy-looking, and deploying nothing.
    check = check_vercel_project("prj_1", True, fetch=lambda pid: {
        "available": True, "project": {"name": "app"},
    })
    _status(check, FAIL)
    assert check["halting"] is False
    assert "git-connected" in check["detail"]


def test_vercel_project_passes_when_git_connected():
    check = check_vercel_project("prj_1", True, fetch=lambda pid: {
        "available": True, "project": {"link": {"type": "github", "org": "a", "repo": "b"}},
    })
    _status(check, PASS)


def test_vercel_project_warns_when_unreachable():
    _status(check_vercel_project("prj_1", True, fetch=lambda pid: {
        "available": False, "error": "401",
    }), WARN)


# ---------------------------------------------------------------------------
# github_repo — the testflow / testflow-demo run
# ---------------------------------------------------------------------------

def test_github_repo_fails_on_404():
    check = check_github_repo("acme/testflow", True, fetch=lambda r: {
        "available": False, "status_code": 404, "error": "Not Found",
    })
    _status(check, FAIL)
    assert check["halting"] is False


def test_github_repo_fails_on_403():
    _status(check_github_repo("acme/x", True, fetch=lambda r: {
        "available": False, "status_code": 403, "error": "Forbidden",
    }), FAIL)


def test_github_repo_warns_on_transient_error():
    # A 502 is GitHub having a moment, not a wrong repo name — must not be
    # reported with the same severity as "this repo does not exist".
    _status(check_github_repo("acme/x", True, fetch=lambda r: {
        "available": False, "status_code": 502, "error": "Bad Gateway",
    }), WARN)


def test_github_repo_passes_when_reachable():
    _status(check_github_repo("acme/x", True, fetch=lambda r: {"available": True}), PASS)


def test_github_repo_skips_without_token():
    _status(check_github_repo("acme/x", False), SKIP)


# ---------------------------------------------------------------------------
# required_tables
# ---------------------------------------------------------------------------

def test_required_tables_fails_on_a_confirmed_absence():
    check = check_required_tables(("a", "b"), exists_fn=lambda t: t == "a")
    _status(check, FAIL)
    assert check["data"]["missing"] == ["b"]


def test_required_tables_warns_when_existence_is_unknown():
    # None means "could not determine" — an unreachable database must never be
    # reported as a missing schema.
    _status(check_required_tables(("a",), exists_fn=lambda t: None), WARN)


def test_required_tables_passes_when_all_present():
    _status(check_required_tables(("a", "b"), exists_fn=lambda t: True), PASS)


def test_required_tables_skips_without_a_reader():
    _status(check_required_tables(DEFAULT_REQUIRED_TABLES, exists_fn=None), SKIP)


# ---------------------------------------------------------------------------
# credentials — names only, and only what this config actually needs
# ---------------------------------------------------------------------------

_FULL = {
    "anthropic": True, "github": True, "supabase": True, "database": True,
    "vercel": True, "slack": True, "auto_apply_sql": True,
    "auto_apply_migrations": True, "auto_deploy": True, "slack_notify": True,
}


def test_credentials_pass_when_everything_needed_is_present():
    _status(check_credentials(dict(_FULL)), PASS)


def test_credentials_fail_and_name_the_missing_variable():
    check = check_credentials({**_FULL, "vercel": False})
    _status(check, FAIL)
    assert "VERCEL_TOKEN" in check["detail"]
    assert check["halting"] is False


def test_credentials_ignore_integrations_that_are_switched_off():
    # AUTO_DEPLOY=false means VERCEL_TOKEN is not a requirement; reporting it
    # missing would be noise, and noise is what this mission exists to cut.
    snapshot = {**_FULL, "auto_deploy": False, "vercel": False}
    assert not any(r["name"] == "VERCEL_TOKEN" for r in required_credentials(snapshot))
    _status(check_credentials(snapshot), PASS)


def test_credentials_accept_subscription_auth_instead_of_an_api_key():
    snapshot = {**_FULL, "anthropic": False, "claude_auth_mode": "subscription"}
    _status(check_credentials(snapshot), PASS)


def test_credentials_never_leak_a_value():
    secret = "sk-ant-supersecretvalue"
    snapshot = {**_FULL, "vercel": False, "anthropic": secret}
    check = check_credentials(snapshot)
    assert secret not in str(check), "credential values must never appear in a check"


# ---------------------------------------------------------------------------
# Aggregation
# ---------------------------------------------------------------------------

def test_summary_status_is_the_worst_check():
    assert summarize_checks([make_check("a", PASS, "")])["status"] == "PASS"
    assert summarize_checks([
        make_check("a", PASS, ""), make_check("b", WARN, ""),
    ])["status"] == "WARN"
    assert summarize_checks([
        make_check("a", WARN, ""), make_check("b", FAIL, ""),
    ])["status"] == "FAIL"


def test_skip_does_not_degrade_the_verdict():
    assert summarize_checks([
        make_check("a", PASS, ""), make_check("b", SKIP, ""),
    ])["status"] == "PASS"


def test_failures_are_not_unsafe_unless_the_check_is_halting():
    summary = summarize_checks([
        make_check("github_repo", FAIL, "gone"),
        make_check("vercel_project", FAIL, "unlinked"),
    ])
    assert summary["status"] == "FAIL"
    assert summary["unsafe"] is False, "a FAIL verdict must not halt the loop by itself"


def test_a_failing_halting_check_is_unsafe():
    summary = summarize_checks([
        make_check("git_state", FAIL, "dirty", halting=True),
        make_check("github_repo", PASS, ""),
    ])
    assert summary["unsafe"] is True
    assert summary["unsafe_checks"] == ["git_state"]


def test_report_lists_every_check_and_flags_halting():
    summary = summarize_checks([
        make_check("git_state", FAIL, "dirty tree", halting=True),
        make_check("github_repo", PASS, "reachable"),
    ])
    report = format_preflight_report(summary)
    assert "FAIL" in report
    assert "git_state" in report and "github_repo" in report
    assert "HALTING" in report


def test_report_says_reporting_only_when_nothing_halts():
    report = format_preflight_report(summarize_checks([make_check("github_repo", FAIL, "gone")]))
    assert "HALTING" not in report
    assert "Reporting only" in report


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

class _Cfg:
    repo_path = "/repo"
    vercel_project_id = "prj_1"
    github_repo = "acme/app"
    has_vercel = False
    has_github = False
    has_database = False
    has_supabase = False
    preflight_required_tables = ()

    def report(self):
        return dict(_FULL)


def test_a_raising_probe_never_stops_the_preflight():
    def _boom():
        raise RuntimeError("network exploded")
    _boom.check_name = "github_repo"

    summary = run_startup_preflight(_Cfg(), probes=[
        _boom, lambda: make_check("credentials", PASS, "ok"),
    ])
    assert summary["status"] == "WARN"
    assert summary["unsafe"] is False
    assert len(summary["checks"]) == 2


def test_a_raising_probe_is_attributed_to_its_check():
    def _boom():
        raise RuntimeError("boom")
    _boom.check_name = "production_sha"

    summary = run_startup_preflight(_Cfg(), probes=[_boom])
    assert summary["checks"][0]["name"] == "production_sha", \
        "an unattributed warning cannot be traced back to later"


def test_run_startup_preflight_carries_a_rendered_report():
    summary = run_startup_preflight(_Cfg(), probes=[lambda: make_check("a", PASS, "fine")])
    assert "Startup Preflight: PASS" in summary["report"]
    assert summary["generated_at"]


def test_default_probes_run_without_network_or_git():
    # Nothing is configured on _Cfg, so every integration check must skip
    # rather than attempt a call — a preflight that hangs at startup is worse
    # than the assumptions it verifies.
    original = sp.check_git_state
    sp.check_git_state = lambda repo_path, evaluate=None: make_check("git_state", PASS, "clean")
    try:
        summary = run_startup_preflight(_Cfg())
    finally:
        sp.check_git_state = original

    names = [c["name"] for c in summary["checks"]]
    assert names == [
        "git_state", "repo_health", "pending_migrations", "production_sha",
        "vercel_project", "github_repo", "required_tables", "credentials",
    ]
    assert summary["unsafe"] is False


def test_guard_emits_preflight_report_with_every_check():
    events = []
    original = sp.log_event
    sp.log_event = lambda t, p: events.append((t, p))
    try:
        summary = guard_startup_preflight(_Cfg(), probes=[
            lambda: make_check("github_repo", FAIL, "404"),
        ])
    finally:
        sp.log_event = original

    assert len(events) == 1
    event_type, payload = events[0]
    assert event_type == "preflight_report"
    assert payload["status"] == "FAIL"
    assert payload["unsafe"] is False
    assert payload["checks"] == [
        {"name": "github_repo", "status": FAIL, "detail": "404"}
    ]
    assert summary["status"] == "FAIL"


def test_guard_reports_unsafe_for_a_halting_check():
    original = sp.log_event
    sp.log_event = lambda t, p: None
    try:
        summary = guard_startup_preflight(_Cfg(), probes=[
            lambda: make_check("git_state", FAIL, "dirty", halting=True),
        ])
    finally:
        sp.log_event = original
    assert summary["unsafe"] is True


# ---------------------------------------------------------------------------
# Graph node — runs once per session, reports, and halts only when unsafe
# ---------------------------------------------------------------------------

import graph  # noqa: E402
from state import RunnerState  # noqa: E402

graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None


def _run_node(summary, enabled=True, state=None):
    """Drive the node with a stubbed preflight (no network, no outbox write)."""
    original_guard = graph.guard_startup_preflight
    original_cfg_flag = graph.cfg.startup_preflight_enabled
    calls = []
    graph.guard_startup_preflight = lambda cfg, **kw: (calls.append(1), dict(summary))[1]
    graph.cfg.startup_preflight_enabled = enabled
    try:
        state = state or RunnerState(started_at="2026-08-02T00:00:00")
        return graph.run_startup_preflight_if_needed(state), calls
    finally:
        graph.guard_startup_preflight = original_guard
        graph.cfg.startup_preflight_enabled = original_cfg_flag


_CLEAN = {"status": "PASS", "counts": {}, "checks": [], "unsafe": False,
          "unsafe_checks": [], "report": "Startup Preflight: PASS\n"}
_UNSAFE = {**_CLEAN, "status": "FAIL", "unsafe": True, "unsafe_checks": ["git_state"]}
_NOISY = {**_CLEAN, "status": "FAIL", "unsafe": False, "unsafe_checks": []}


def test_node_stores_the_report_on_state():
    state, calls = _run_node(_CLEAN)
    assert len(calls) == 1
    assert state.preflight_report["status"] == "PASS"


def test_node_does_not_stop_the_loop_on_a_non_halting_failure():
    # The whole point: a FAIL verdict is loud, not blocking.
    state, _ = _run_node(_NOISY)
    assert state.stop_reason is None


def test_node_stops_the_loop_only_when_unsafe():
    state, _ = _run_node(_UNSAFE)
    assert state.stop_reason == "preflight_unsafe"


def test_node_runs_once_per_session():
    state, calls = _run_node(_CLEAN)
    assert len(calls) == 1
    # Second pass through the graph in the same session: no repeat round-trips.
    _, calls_again = _run_node(_CLEAN, state=state)
    assert calls_again == []


def test_node_runs_again_for_a_new_session():
    state, _ = _run_node(_CLEAN)
    state.started_at = "2026-08-03T00:00:00"
    _, calls = _run_node(_CLEAN, state=state)
    assert len(calls) == 1


def test_node_is_a_noop_when_disabled():
    state, calls = _run_node(_CLEAN, enabled=False)
    assert calls == []
    assert state.preflight_report is None


def test_node_is_wired_into_the_graph_before_any_task_is_claimed():
    # A preflight that is defined but never reached is the failure this whole
    # task is about, one level up.
    compiled = graph.build_graph()
    nodes = compiled.get_graph().nodes
    assert "run_startup_preflight_if_needed" in nodes


if __name__ == "__main__":
    tests = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
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
