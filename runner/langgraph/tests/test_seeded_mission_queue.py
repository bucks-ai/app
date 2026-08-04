"""Unit tests for the Seeded Mission Queue Executor.

Runs standalone (no pytest dependency):

    python tests/test_seeded_mission_queue.py

Covers:
  - ``seed_tasks_from_mission`` pure conversion helper
  - ``check_mission_completion`` Supabase polling helper (stubbed client)
  - ``fetch_next_queued_mission`` / ``evaluate_business_mission_claim``
    runner_target claim gate (CRITICAL SAFETY — a mission with
    runner_target="business" is claimable only with BUSINESS_EXECUTION_ENABLED
    on, a fully configured sandbox, and both named secrets resolving)
  - ``BUSINESS_EXECUTION_ENABLED`` env wiring (the gate's kill switch)
  - Graph node ``seed_mission_queue_if_needed`` (Supabase stubbed via monkeypatching)
  - Routing: ``_route_after_compile_mission`` and ``_route_after_seed_mission_queue``
  - Graph wiring: node present in compiled graph
"""
import os
import sys
import traceback

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from tools.seeded_mission_queue import (
    seed_tasks_from_mission,
    check_mission_completion,
    fetch_next_queued_mission,
    evaluate_business_mission_claim,
)
import tools.seeded_mission_queue as smq
import graph
from state import RunnerState

# Silence flight recorder and disk persistence during all tests.
graph.log_event = lambda *a, **k: None
graph.update_state = lambda *a, **k: None


# ---------------------------------------------------------------------------
# Pure helper: seed_tasks_from_mission
# ---------------------------------------------------------------------------

_MISSION = {
    "id": "mission-uuid-1",
    "name": "Auth Feature",
    "goal": "Add user authentication",
    "status": "queued",
}

_TASKS = [
    {
        "id": "task-uuid-1",
        "mission_id": "mission-uuid-1",
        "task_id": "",
        "title": "Add login page",
        "type": "frontend",
        "branch": "feature/auth/login",
        "preferred_worker": "codex",
        "position": 1,
        "status": "queued",
    },
    {
        "id": "task-uuid-2",
        "mission_id": "mission-uuid-1",
        "task_id": "",
        "title": "Add auth API",
        "type": "backend",
        "branch": "",
        "preferred_worker": None,
        "position": 2,
        "status": "queued",
    },
]


def test_seed_tasks_count():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    assert len(tasks) == 2


def test_seed_tasks_titles():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    assert tasks[0]["title"] == "Add login page"
    assert tasks[1]["title"] == "Add auth API"


def test_seed_tasks_types():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    assert tasks[0]["type"] == "frontend"
    assert tasks[1]["type"] == "backend"


def test_seed_tasks_status_queued():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    for t in tasks:
        assert t["status"] == "queued"


def test_seed_tasks_source():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    for t in tasks:
        assert t["source"] == "seeded_mission"


def test_seed_tasks_mission_name():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    for t in tasks:
        assert t["mission"] == "Auth Feature"


def test_seed_tasks_seeded_mission_id():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    for t in tasks:
        assert t["seeded_mission_id"] == "mission-uuid-1"


def test_seed_tasks_seeded_task_id():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    assert tasks[0]["seeded_task_id"] == "task-uuid-1"
    assert tasks[1]["seeded_task_id"] == "task-uuid-2"


def test_seed_tasks_custom_branch_preserved():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    assert tasks[0]["branch"] == "feature/auth/login"


def test_seed_tasks_auto_branch_when_empty():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    branch = tasks[1]["branch"]
    assert branch.startswith("feature/auth-feature/")
    assert "add-auth-api" in branch


def test_seed_tasks_preferred_worker_included():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    assert tasks[0].get("preferred_worker") == "codex"


def test_seed_tasks_no_preferred_worker_excluded():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    assert "preferred_worker" not in tasks[1] or tasks[1].get("preferred_worker") is None
    # The field must not be set when None to avoid confusing the worker chooser
    # (seed_tasks_from_mission only adds it when truthy)
    assert not tasks[1].get("preferred_worker")


def test_seed_tasks_uses_db_task_id():
    tasks_with_id = [dict(_TASKS[0], task_id="my-custom-id")]
    tasks = seed_tasks_from_mission(_MISSION, tasks_with_id)
    assert tasks[0]["id"] == "my-custom-id"


def test_seed_tasks_generates_task_id_when_empty():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    # No task_id set in _TASKS → generated from mission slug + position
    assert tasks[0]["id"] == "auth-feature-1"
    assert tasks[1]["id"] == "auth-feature-2"


def test_seed_tasks_empty_list():
    tasks = seed_tasks_from_mission(_MISSION, [])
    assert tasks == []


def test_seed_tasks_description_included():
    tasks_with_description = [dict(_TASKS[0], description="Do the thing carefully.")]
    tasks = seed_tasks_from_mission(_MISSION, tasks_with_description)
    assert tasks[0]["description"] == "Do the thing carefully."


def test_seed_tasks_no_description_excluded():
    tasks = seed_tasks_from_mission(_MISSION, _TASKS)
    # _TASKS rows carry no "description" key → the field must not be set,
    # matching the existing preferred_worker convention.
    assert "description" not in tasks[0]
    assert "description" not in tasks[1]


# ---------------------------------------------------------------------------
# check_mission_completion (Supabase stubbed)
# ---------------------------------------------------------------------------

def _stub_client(rows):
    """Return a fake Supabase client that returns *rows* for table queries."""
    class FakeResult:
        data = rows

    class FakeQuery:
        def select(self, *a): return self
        def eq(self, *a): return self
        def order(self, *a): return self
        def limit(self, *a): return self
        def execute(self): return FakeResult()

    class FakeTable:
        def table(self, name): return FakeQuery()

    return FakeTable()


def _with_stub_client(rows, fn):
    """Run fn() with _get_client stubbed to return a fake client."""
    import tools.seeded_mission_queue as smq
    original = smq._get_client
    smq._get_client = lambda: _stub_client(rows)
    try:
        return fn()
    finally:
        smq._get_client = original


def test_check_completion_all_complete():
    rows = [{"status": "complete"}, {"status": "complete"}]
    result = _with_stub_client(rows, lambda: check_mission_completion("uuid-1"))
    assert result["status"] == "completed"


def test_check_completion_one_failed():
    rows = [{"status": "complete"}, {"status": "failed"}]
    result = _with_stub_client(rows, lambda: check_mission_completion("uuid-1"))
    assert result["status"] == "failed"


def test_check_completion_still_running():
    rows = [{"status": "complete"}, {"status": "running"}]
    result = _with_stub_client(rows, lambda: check_mission_completion("uuid-1"))
    assert result["status"] == "in_progress"


def test_check_completion_queued_still_running():
    rows = [{"status": "queued"}]
    result = _with_stub_client(rows, lambda: check_mission_completion("uuid-1"))
    assert result["status"] == "in_progress"


def test_check_completion_no_rows():
    result = _with_stub_client([], lambda: check_mission_completion("uuid-1"))
    assert result["status"] == "unknown"


def test_check_completion_blocked_counts_as_terminal():
    rows = [{"status": "complete"}, {"status": "blocked"}]
    result = _with_stub_client(rows, lambda: check_mission_completion("uuid-1"))
    # blocked is terminal but not complete → failed status
    assert result["status"] == "failed"


# ---------------------------------------------------------------------------
# fetch_next_queued_mission — CRITICAL SAFETY: M4b business-mission claim gate
#
# A mission created for a customer business (runner_target="business", e.g.
# via the app's Execute button, src/app/api/businesses/[id]/execute) may only
# be claimed when evaluate_business_mission_claim allows it: config enabled,
# a fully configured sandbox, and both secrets resolving in the runner env.
# Any failing condition leaves the mission queued and untouched.
# runner_target="self" missions are always claimable, as before M4b.
# ---------------------------------------------------------------------------

def _stub_filtering_client(rows):
    """Fake Supabase client whose ``.eq()`` actually filters *rows*.

    Unlike ``_stub_client`` above (which ignores filter args — sufficient for
    the completion-check tests), this stub applies every ``.eq(field, value)``
    call so tests can prove the claim query's WHERE clause, not just that some
    row was returned.
    """
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

        def order(self, *a):
            return self

        def limit(self, n):
            self._rows = self._rows[:n]
            return self

        def execute(self):
            return FakeResult(self._rows)

    class FakeTable:
        def table(self, name):
            return FakeQuery(rows)

    return FakeTable()


def _with_filtering_stub_client(rows, fn):
    original = smq._get_client
    smq._get_client = lambda: _stub_filtering_client(rows)
    try:
        return fn()
    finally:
        smq._get_client = original


def _patch(obj, **attrs):
    """Set *attrs* on *obj*, returning the originals for restoration.

    Manual patch/restore (no pytest monkeypatch fixture) so every test here
    stays runnable both under pytest and via this file's standalone
    ``__main__`` runner, matching ``_with_stub_client`` / ``_restore_graph_seeded``
    above.
    """
    originals = {name: getattr(obj, name) for name in attrs}
    for name, value in attrs.items():
        setattr(obj, name, value)
    return originals


def _unpatch(obj, originals):
    for name, value in originals.items():
        setattr(obj, name, value)


_FULL_SANDBOX_CONFIG = {
    "repo_full_name": "acme/landing",
    "github_token_secret_name": "ACME_GITHUB_TOKEN",
    "vercel_project_id": "prj_acme",
    "vercel_token_secret_name": "ACME_VERCEL_TOKEN",
}


def test_fetch_next_queued_mission_skips_business_target_when_disabled():
    rows = [
        {"id": "biz-1", "status": "queued", "runner_target": "business",
         "business_id": "b-1", "created_at": "2026-01-01"},
    ]
    from config import get_config
    original = get_config().business_execution_enabled
    get_config().business_execution_enabled = False
    try:
        result = _with_filtering_stub_client(rows, fetch_next_queued_mission)
        assert result is None
    finally:
        get_config().business_execution_enabled = original


def test_fetch_next_queued_mission_claims_self_target():
    rows = [
        {"id": "self-1", "status": "queued", "runner_target": "self", "created_at": "2026-01-01"},
    ]
    result = _with_filtering_stub_client(rows, fetch_next_queued_mission)
    assert result is not None
    assert result["id"] == "self-1"


def test_fetch_next_queued_mission_prefers_self_over_blocked_business():
    rows = [
        {"id": "biz-1", "status": "queued", "runner_target": "business",
         "business_id": "b-1", "created_at": "2026-01-01"},
        {"id": "self-1", "status": "queued", "runner_target": "self", "created_at": "2026-01-02"},
    ]
    from config import get_config
    original = get_config().business_execution_enabled
    get_config().business_execution_enabled = False
    try:
        result = _with_filtering_stub_client(rows, fetch_next_queued_mission)
        assert result is not None
        assert result["id"] == "self-1"
    finally:
        get_config().business_execution_enabled = original


def test_fetch_next_queued_mission_none_when_only_business_targets_disabled():
    rows = [
        {"id": "biz-1", "status": "queued", "runner_target": "business",
         "business_id": "b-1", "created_at": "2026-01-01"},
        {"id": "biz-2", "status": "queued", "runner_target": "business",
         "business_id": "b-2", "created_at": "2026-01-02"},
    ]
    from config import get_config
    original = get_config().business_execution_enabled
    get_config().business_execution_enabled = False
    try:
        result = _with_filtering_stub_client(rows, fetch_next_queued_mission)
        assert result is None
    finally:
        get_config().business_execution_enabled = original


def test_fetch_next_queued_mission_logs_business_mission_blocked():
    rows = [
        {"id": "biz-1", "status": "queued", "runner_target": "business",
         "business_id": "b-1", "created_at": "2026-01-01"},
    ]
    from config import get_config
    original = get_config().business_execution_enabled
    get_config().business_execution_enabled = False
    captured_events = []
    log_original = _patch(smq, log_event=lambda event_type, payload: captured_events.append((event_type, payload)))
    try:
        result = _with_filtering_stub_client(rows, fetch_next_queued_mission)
        assert result is None
        assert any(e[0] == "business_mission_blocked" for e in captured_events)
        blocked = [e[1] for e in captured_events if e[0] == "business_mission_blocked"][0]
        assert blocked["reason"] == "business_execution_disabled"
        assert blocked["mission_id"] == "biz-1"
    finally:
        get_config().business_execution_enabled = original
        _unpatch(smq, log_original)


def test_fetch_next_queued_mission_claims_business_when_fully_configured():
    rows = [
        {"id": "biz-1", "status": "queued", "runner_target": "business",
         "business_id": "b-1", "created_at": "2026-01-01"},
    ]
    from config import get_config
    original = get_config().business_execution_enabled
    get_config().business_execution_enabled = True
    originals = _patch(
        smq,
        lookup_business=lambda bid: {"status": "found", "business": {"id": "b-1"}},
        fetch_business_sandbox=lambda bid: _FULL_SANDBOX_CONFIG,
        resolve_scoped_github_token=lambda name: {"success": True, "token": "x", "secret_name": name},
        resolve_scoped_vercel_token=lambda name: {"success": True, "token": "x", "secret_name": name},
    )
    try:
        result = _with_filtering_stub_client(rows, fetch_next_queued_mission)
        assert result is not None
        assert result["id"] == "biz-1"
    finally:
        get_config().business_execution_enabled = original
        _unpatch(smq, originals)


# ---------------------------------------------------------------------------
# evaluate_business_mission_claim — every refusal path + the full-config pass
# ---------------------------------------------------------------------------

def test_claim_refused_when_business_execution_disabled():
    from config import get_config
    original = get_config().business_execution_enabled
    get_config().business_execution_enabled = False
    try:
        result = evaluate_business_mission_claim({"business_id": "b-1"})
        assert result == {"allowed": False, "reason": "business_execution_disabled"}
    finally:
        get_config().business_execution_enabled = original


def test_claim_refused_when_missing_business_id():
    from config import get_config
    original = get_config().business_execution_enabled
    get_config().business_execution_enabled = True
    try:
        result = evaluate_business_mission_claim({})
        assert result == {"allowed": False, "reason": "missing_business_id"}
    finally:
        get_config().business_execution_enabled = original


def test_claim_refused_when_business_not_found():
    from config import get_config
    original = get_config().business_execution_enabled
    get_config().business_execution_enabled = True
    originals = _patch(smq, lookup_business=lambda bid: {"status": "not_found", "business": None})
    try:
        result = evaluate_business_mission_claim({"business_id": "b-1"})
        assert result == {"allowed": False, "reason": "business_not_found"}
    finally:
        get_config().business_execution_enabled = original
        _unpatch(smq, originals)


def test_claim_refused_when_sandbox_not_configured():
    from config import get_config
    original = get_config().business_execution_enabled
    get_config().business_execution_enabled = True
    originals = _patch(
        smq,
        lookup_business=lambda bid: {"status": "found", "business": {"id": "b-1"}},
        fetch_business_sandbox=lambda bid: {
            "repo_full_name": "acme/landing",
            # github_token_secret_name missing
            "vercel_project_id": "prj_acme",
            # vercel_token_secret_name missing
        },
    )
    try:
        result = evaluate_business_mission_claim({"business_id": "b-1"})
        assert result["allowed"] is False
        assert result["reason"] == "sandbox_not_configured"
        assert set(result["missing_fields"]) == {"github_token_secret_name", "vercel_token_secret_name"}
    finally:
        get_config().business_execution_enabled = original
        _unpatch(smq, originals)


def test_claim_refused_when_sandbox_config_absent():
    from config import get_config
    original = get_config().business_execution_enabled
    get_config().business_execution_enabled = True
    originals = _patch(
        smq,
        lookup_business=lambda bid: {"status": "found", "business": {"id": "b-1"}},
        fetch_business_sandbox=lambda bid: None,
    )
    try:
        result = evaluate_business_mission_claim({"business_id": "b-1"})
        assert result["allowed"] is False
        assert result["reason"] == "sandbox_not_configured"
        assert len(result["missing_fields"]) == 4
    finally:
        get_config().business_execution_enabled = original
        _unpatch(smq, originals)


def test_claim_refused_when_only_legacy_business_sandbox_config_populated():
    """A business whose only populated sandbox data lives on the deprecated
    businesses.sandbox_config JSONB column (business_sandbox table empty)
    must be refused exactly like an unconfigured business — no silent
    stale-data fallback onto the legacy column."""
    from config import get_config
    original = get_config().business_execution_enabled
    get_config().business_execution_enabled = True
    originals = _patch(
        smq,
        lookup_business=lambda bid: {"status": "found",
                                    "business": {"id": "b-1", "sandbox_config": _FULL_SANDBOX_CONFIG}},
        fetch_business_sandbox=lambda bid: None,
    )
    try:
        result = evaluate_business_mission_claim({"business_id": "b-1"})
        assert result["allowed"] is False
        assert result["reason"] == "sandbox_not_configured"
        assert len(result["missing_fields"]) == 4
    finally:
        get_config().business_execution_enabled = original
        _unpatch(smq, originals)


def test_claim_refused_when_github_secret_unresolved():
    from config import get_config
    original = get_config().business_execution_enabled
    get_config().business_execution_enabled = True
    originals = _patch(
        smq,
        lookup_business=lambda bid: {"status": "found", "business": {"id": "b-1"}},
        fetch_business_sandbox=lambda bid: _FULL_SANDBOX_CONFIG,
        resolve_scoped_github_token=lambda name: {"success": False, "error": "missing_secret", "secret_name": name},
    )
    try:
        result = evaluate_business_mission_claim({"business_id": "b-1"})
        assert result == {"allowed": False, "reason": "secret_unresolved", "secret_name": "ACME_GITHUB_TOKEN"}
    finally:
        get_config().business_execution_enabled = original
        _unpatch(smq, originals)


def test_claim_refused_when_vercel_secret_unresolved():
    from config import get_config
    original = get_config().business_execution_enabled
    get_config().business_execution_enabled = True
    originals = _patch(
        smq,
        lookup_business=lambda bid: {"status": "found", "business": {"id": "b-1"}},
        fetch_business_sandbox=lambda bid: _FULL_SANDBOX_CONFIG,
        resolve_scoped_github_token=lambda name: {"success": True, "token": "x", "secret_name": name},
        resolve_scoped_vercel_token=lambda name: {"success": False, "error": "missing_secret", "secret_name": name},
    )
    try:
        result = evaluate_business_mission_claim({"business_id": "b-1"})
        assert result == {"allowed": False, "reason": "secret_unresolved", "secret_name": "ACME_VERCEL_TOKEN"}
    finally:
        get_config().business_execution_enabled = original
        _unpatch(smq, originals)


def test_claim_allowed_when_fully_configured():
    from config import get_config
    original = get_config().business_execution_enabled
    get_config().business_execution_enabled = True
    originals = _patch(
        smq,
        lookup_business=lambda bid: {"status": "found", "business": {"id": "b-1"}},
        fetch_business_sandbox=lambda bid: _FULL_SANDBOX_CONFIG,
        resolve_scoped_github_token=lambda name: {"success": True, "token": "x", "secret_name": name},
        resolve_scoped_vercel_token=lambda name: {"success": True, "token": "x", "secret_name": name},
    )
    try:
        result = evaluate_business_mission_claim({"business_id": "b-1"})
        assert result == {"allowed": True}
    finally:
        get_config().business_execution_enabled = original
        _unpatch(smq, originals)


# ---------------------------------------------------------------------------
# Config wiring: BUSINESS_EXECUTION_ENABLED -> cfg.business_execution_enabled
#
# The gate tests above flip ``cfg.business_execution_enabled`` directly, so on
# their own they would still pass if the env var were renamed or dropped from
# config.py — leaving the kill switch unreachable from the environment while
# the suite stayed green.  These two tests pin the wiring itself: unset means
# off (the safe default), and the documented env var is what turns it on.
# ---------------------------------------------------------------------------

def _config_with_env(value):
    """Build a fresh RunnerConfig with BUSINESS_EXECUTION_ENABLED set to *value*.

    ``value=None`` unsets the variable entirely.  RunnerConfig reads env at
    construction time (``default_factory``), so a new instance re-reads it;
    the process-wide ``get_config()`` singleton is left untouched.
    """
    from config import RunnerConfig
    original = os.environ.get("BUSINESS_EXECUTION_ENABLED")
    if value is None:
        os.environ.pop("BUSINESS_EXECUTION_ENABLED", None)
    else:
        os.environ["BUSINESS_EXECUTION_ENABLED"] = value
    try:
        return RunnerConfig().business_execution_enabled
    finally:
        if original is None:
            os.environ.pop("BUSINESS_EXECUTION_ENABLED", None)
        else:
            os.environ["BUSINESS_EXECUTION_ENABLED"] = original


def test_business_execution_defaults_off_when_env_unset():
    assert _config_with_env(None) is False


def test_business_execution_only_enabled_by_explicit_true():
    assert _config_with_env("true") is True
    assert _config_with_env("TRUE") is True
    assert _config_with_env("false") is False
    assert _config_with_env("") is False
    assert _config_with_env("1") is False
    assert _config_with_env("yes") is False


# ---------------------------------------------------------------------------
# Graph node: seed_mission_queue_if_needed
# ---------------------------------------------------------------------------

def _make_state(**kwargs) -> RunnerState:
    return RunnerState(**kwargs)


def _stub_graph_seeded(mission=None, task_rows=None, captured_tasks=None, existing_tasks=None):
    """Patch graph module globals to stub Supabase and task_tools.

    ``existing_tasks`` is what the local queue already holds — the input to
    m4c-03's idempotent-seeding check. Stubbing ``load_tasks`` also keeps these
    tests off the founder's real ``.runtime/tasks.local.json``.
    """
    if captured_tasks is None:
        captured_tasks = []
    existing_tasks = list(existing_tasks or [])

    graph.fetch_next_queued_mission = lambda: mission
    graph.fetch_mission_tasks = lambda mid: task_rows or []
    graph.seed_tasks_from_mission = lambda m, t: [
        {
            "id": f"task-{i+1}",
            "title": row["title"],
            "type": row.get("type", "general"),
            "branch": row.get("branch", f"feature/task-{i+1}"),
            "status": "queued",
            "source": "seeded_mission",
            "mission": m.get("name", ""),
            "seeded_mission_id": str(m.get("id", "")),
            "seeded_task_id": str(row.get("id", "")),
        }
        for i, row in enumerate(t)
    ]
    graph.mark_mission_running = lambda mid: _mission_writes.append(("running", mid))
    graph.mark_mission_completed = lambda mid: _mission_writes.append(("completed", mid))
    graph.mark_mission_failed = lambda mid: _mission_writes.append(("failed", mid))
    graph.check_mission_completion = lambda mid: {"status": "in_progress"}
    graph.add_task = lambda t: captured_tasks.append(dict(t))
    graph.load_tasks = lambda **kwargs: existing_tasks + captured_tasks
    graph.remove_tasks = lambda ids: list(ids)

    _first = [None]
    def _get_next():
        return captured_tasks[0] if captured_tasks else None
    graph.get_next_queued_task = _get_next
    graph.update_task_branch = lambda *a, **k: None

    return captured_tasks


#: Mission-status writes captured by the stub, newest last.
_mission_writes: list = []


def _restore_graph_seeded():
    from tools import task_tools
    from tools.seeded_mission_queue import (
        fetch_next_queued_mission,
        fetch_mission_tasks,
        seed_tasks_from_mission,
        mark_mission_running,
        mark_mission_completed,
        mark_mission_failed,
        check_mission_completion,
    )
    graph.fetch_next_queued_mission = fetch_next_queued_mission
    graph.fetch_mission_tasks = fetch_mission_tasks
    graph.seed_tasks_from_mission = seed_tasks_from_mission
    graph.mark_mission_running = mark_mission_running
    graph.mark_mission_completed = mark_mission_completed
    graph.mark_mission_failed = mark_mission_failed
    graph.check_mission_completion = check_mission_completion
    graph.add_task = task_tools.add_task
    graph.load_tasks = task_tools.load_tasks
    graph.remove_tasks = task_tools.remove_tasks
    graph.get_next_queued_task = task_tools.get_next_queued_task
    graph.update_task_branch = task_tools.update_task_branch
    _mission_writes.clear()


_SAMPLE_MISSION = {"id": "m-uuid", "name": "Test Mission", "status": "queued"}
_SAMPLE_TASK_ROWS = [
    {"id": "t-uuid-1", "title": "Task One", "type": "backend", "branch": "feature/t1", "position": 1},
    {"id": "t-uuid-2", "title": "Task Two", "type": "frontend", "branch": "feature/t2", "position": 2},
]


def test_node_disabled_by_config():
    captured = _stub_graph_seeded(mission=_SAMPLE_MISSION, task_rows=_SAMPLE_TASK_ROWS)
    try:
        graph.cfg.seeded_mission_queue_enabled = False
        out = graph.seed_mission_queue_if_needed(_make_state())
        assert out.current_task is None
        assert captured == []
    finally:
        graph.cfg.seeded_mission_queue_enabled = True
        _restore_graph_seeded()


def test_node_no_supabase():
    captured = _stub_graph_seeded(mission=_SAMPLE_MISSION, task_rows=_SAMPLE_TASK_ROWS)
    original_has_supabase = type(graph.cfg).has_supabase.fget
    try:
        graph.cfg.seeded_mission_queue_enabled = True
        # Patch has_supabase property to return False
        type(graph.cfg).has_supabase = property(lambda self: False)
        out = graph.seed_mission_queue_if_needed(_make_state())
        assert out.current_task is None
        assert captured == []
    finally:
        graph.cfg.seeded_mission_queue_enabled = True
        type(graph.cfg).has_supabase = property(original_has_supabase)
        _restore_graph_seeded()


def test_node_no_queued_mission():
    captured = _stub_graph_seeded(mission=None, task_rows=[])
    try:
        graph.cfg.seeded_mission_queue_enabled = True
        type(graph.cfg).has_supabase = property(lambda self: True)
        out = graph.seed_mission_queue_if_needed(_make_state())
        assert out.current_task is None
        assert captured == []
    finally:
        original_has_supabase = property(lambda self: bool(graph.cfg.supabase_url and graph.cfg.supabase_service_role_key))
        type(graph.cfg).has_supabase = original_has_supabase
        _restore_graph_seeded()


def test_node_seeds_tasks_and_loads_first():
    captured = _stub_graph_seeded(mission=_SAMPLE_MISSION, task_rows=_SAMPLE_TASK_ROWS)
    try:
        graph.cfg.seeded_mission_queue_enabled = True
        type(graph.cfg).has_supabase = property(lambda self: True)
        out = graph.seed_mission_queue_if_needed(_make_state(stop_reason="no_queued_tasks"))
        assert len(captured) == 2
        assert out.current_task is not None
        assert out.current_task["title"] == "Task One"
        assert out.current_task_id == out.current_task["id"]
        assert out.stop_reason is None
    finally:
        original_has_supabase = property(lambda self: bool(graph.cfg.supabase_url and graph.cfg.supabase_service_role_key))
        type(graph.cfg).has_supabase = original_has_supabase
        _restore_graph_seeded()


def test_node_skips_when_task_already_loaded():
    captured = _stub_graph_seeded(mission=_SAMPLE_MISSION, task_rows=_SAMPLE_TASK_ROWS)
    try:
        graph.cfg.seeded_mission_queue_enabled = True
        type(graph.cfg).has_supabase = property(lambda self: True)
        state = _make_state(current_task={"id": "existing", "title": "Already there"})
        out = graph.seed_mission_queue_if_needed(state)
        assert out.current_task["id"] == "existing"
        assert captured == []
    finally:
        original_has_supabase = property(lambda self: bool(graph.cfg.supabase_url and graph.cfg.supabase_service_role_key))
        type(graph.cfg).has_supabase = original_has_supabase
        _restore_graph_seeded()


def test_node_never_seeds_a_mission_that_is_already_in_the_local_queue():
    """m4c-03: "Execute: AI Infra" was seeded three times because nothing asked
    whether the mission was already local — 15 rows, ids ai-infra-1..5 three
    times over, and status writes landing on whichever row matched first."""
    already_local = [
        {"id": "task-1", "title": "Task One", "status": "complete",
         "seeded_mission_id": "m-uuid", "seeded_task_id": "t-uuid-1"},
        {"id": "task-2", "title": "Task Two", "status": "complete",
         "seeded_mission_id": "m-uuid", "seeded_task_id": "t-uuid-2"},
    ]
    captured = _stub_graph_seeded(
        mission=_SAMPLE_MISSION, task_rows=_SAMPLE_TASK_ROWS, existing_tasks=already_local,
    )
    try:
        graph.cfg.seeded_mission_queue_enabled = True
        type(graph.cfg).has_supabase = property(lambda self: True)
        out = graph.seed_mission_queue_if_needed(_make_state(stop_reason="no_queued_tasks"))
        assert captured == [], "re-seeding must add nothing"
        assert out.current_task is None
        # The mission must still leave 'queued' in Supabase, or the next poll
        # fetches the same mission again forever.
        assert _mission_writes and _mission_writes[-1][1] == "m-uuid"
    finally:
        original_has_supabase = property(lambda self: bool(graph.cfg.supabase_url and graph.cfg.supabase_service_role_key))
        type(graph.cfg).has_supabase = original_has_supabase
        _restore_graph_seeded()


def test_node_seeds_only_the_mission_task_that_is_actually_missing():
    already_local = [
        {"id": "task-1", "title": "Task One", "status": "complete",
         "seeded_mission_id": "m-uuid", "seeded_task_id": "t-uuid-1"},
    ]
    captured = _stub_graph_seeded(
        mission=_SAMPLE_MISSION, task_rows=_SAMPLE_TASK_ROWS, existing_tasks=already_local,
    )
    try:
        graph.cfg.seeded_mission_queue_enabled = True
        type(graph.cfg).has_supabase = property(lambda self: True)
        graph.seed_mission_queue_if_needed(_make_state(stop_reason="no_queued_tasks"))
        assert [t["seeded_task_id"] for t in captured] == ["t-uuid-2"]
    finally:
        original_has_supabase = property(lambda self: bool(graph.cfg.supabase_url and graph.cfg.supabase_service_role_key))
        type(graph.cfg).has_supabase = original_has_supabase
        _restore_graph_seeded()


def test_node_gives_a_seeded_task_a_unique_id_when_one_is_taken():
    captured = _stub_graph_seeded(
        mission=_SAMPLE_MISSION,
        task_rows=_SAMPLE_TASK_ROWS,
        existing_tasks=[{"id": "task-1", "title": "Unrelated", "status": "queued"}],
    )
    try:
        graph.cfg.seeded_mission_queue_enabled = True
        type(graph.cfg).has_supabase = property(lambda self: True)
        graph.seed_mission_queue_if_needed(_make_state(stop_reason="no_queued_tasks"))
        assert [t["id"] for t in captured] == ["task-1-2", "task-2"]
    finally:
        original_has_supabase = property(lambda self: bool(graph.cfg.supabase_url and graph.cfg.supabase_service_role_key))
        type(graph.cfg).has_supabase = original_has_supabase
        _restore_graph_seeded()


# ---------------------------------------------------------------------------
# Routing
# ---------------------------------------------------------------------------

def test_route_compile_no_task_to_seed_queue():
    s = RunnerState(current_task=None)
    assert graph._route_after_compile_mission(s) == "seed_mission_queue_if_needed"


def test_route_compile_with_task_to_choose_worker():
    s = RunnerState(current_task={"id": "t1", "title": "T"})
    assert graph._route_after_compile_mission(s) == "choose_worker"


def test_route_seed_queue_no_task_to_chatgpt():
    s = RunnerState(current_task=None)
    assert graph._route_after_seed_mission_queue(s) == "ask_chatgpt_for_task_if_needed"


def test_route_seed_queue_with_task_to_choose_worker():
    s = RunnerState(current_task={"id": "t1", "title": "T"})
    assert graph._route_after_seed_mission_queue(s) == "choose_worker"


def test_route_seed_queue_exhausted_to_decide_continue_or_stop():
    """Strict-mode exhaustion must route straight to the stop check, never the planner."""
    s = RunnerState(current_task=None, stop_reason="seeded_queue_exhausted")
    assert graph._route_after_seed_mission_queue(s) == "decide_continue_or_stop"


def test_route_seed_queue_other_stop_reason_still_asks_chatgpt():
    """Non-strict stop reasons (e.g. no_queued_tasks) must still fall through to the planner."""
    s = RunnerState(current_task=None, stop_reason="no_queued_tasks")
    assert graph._route_after_seed_mission_queue(s) == "ask_chatgpt_for_task_if_needed"


# ---------------------------------------------------------------------------
# Graph wiring
# ---------------------------------------------------------------------------

def test_node_is_wired_into_graph():
    nodes = list(graph.build_graph().get_graph().nodes)
    assert "seed_mission_queue_if_needed" in nodes, nodes


def test_compile_still_routes_to_chatgpt_via_seed_node():
    """compile_mission_if_needed → seed_mission_queue_if_needed → ask_chatgpt_for_task_if_needed."""
    g = graph.build_graph().get_graph()
    # Check that there is an edge from compile to seed
    edges = [(e.source, e.target) for e in g.edges]
    sources_from_compile = [t for s, t in edges if s == "compile_mission_if_needed"]
    assert "seed_mission_queue_if_needed" in sources_from_compile, sources_from_compile


# ---------------------------------------------------------------------------
# Strict mode: seeded_mission_queue_strict
# ---------------------------------------------------------------------------

def test_strict_mode_sets_stop_reason_when_no_mission():
    """In strict mode, no queued missions → stop_reason = seeded_queue_exhausted."""
    captured = _stub_graph_seeded(mission=None, task_rows=[])
    try:
        graph.cfg.seeded_mission_queue_enabled = True
        graph.cfg.seeded_mission_queue_strict = True
        type(graph.cfg).has_supabase = property(lambda self: True)
        state = _make_state()
        out = graph.seed_mission_queue_if_needed(state)
        assert out.stop_reason == "seeded_queue_exhausted"
        assert out.current_task is None
        assert captured == []
    finally:
        graph.cfg.seeded_mission_queue_enabled = True
        graph.cfg.seeded_mission_queue_strict = False
        original_has_supabase = property(
            lambda self: bool(graph.cfg.supabase_url and graph.cfg.supabase_service_role_key)
        )
        type(graph.cfg).has_supabase = original_has_supabase
        _restore_graph_seeded()


def test_non_strict_mode_no_stop_reason_when_no_mission():
    """In non-strict mode, no queued missions → falls through without stop_reason."""
    captured = _stub_graph_seeded(mission=None, task_rows=[])
    try:
        graph.cfg.seeded_mission_queue_enabled = True
        graph.cfg.seeded_mission_queue_strict = False
        type(graph.cfg).has_supabase = property(lambda self: True)
        state = _make_state()
        out = graph.seed_mission_queue_if_needed(state)
        assert out.stop_reason is None
        assert out.current_task is None
        assert captured == []
    finally:
        graph.cfg.seeded_mission_queue_enabled = True
        graph.cfg.seeded_mission_queue_strict = False
        original_has_supabase = property(
            lambda self: bool(graph.cfg.supabase_url and graph.cfg.supabase_service_role_key)
        )
        type(graph.cfg).has_supabase = original_has_supabase
        _restore_graph_seeded()


def test_strict_mode_does_not_stop_when_mission_exists():
    """In strict mode, a queued mission is found → seeds tasks normally, no stop_reason."""
    captured = _stub_graph_seeded(mission=_SAMPLE_MISSION, task_rows=_SAMPLE_TASK_ROWS)
    try:
        graph.cfg.seeded_mission_queue_enabled = True
        graph.cfg.seeded_mission_queue_strict = True
        type(graph.cfg).has_supabase = property(lambda self: True)
        out = graph.seed_mission_queue_if_needed(_make_state(stop_reason="no_queued_tasks"))
        assert len(captured) == 2
        assert out.current_task is not None
        assert out.stop_reason is None
    finally:
        graph.cfg.seeded_mission_queue_enabled = True
        graph.cfg.seeded_mission_queue_strict = False
        original_has_supabase = property(
            lambda self: bool(graph.cfg.supabase_url and graph.cfg.supabase_service_role_key)
        )
        type(graph.cfg).has_supabase = original_has_supabase
        _restore_graph_seeded()


def test_ask_chatgpt_next_task_skipped_in_strict_mode():
    """ask_chatgpt_next_task returns immediately when strict seeded queue is active."""
    original_enabled = graph.cfg.seeded_mission_queue_enabled
    original_strict = graph.cfg.seeded_mission_queue_strict
    try:
        graph.cfg.seeded_mission_queue_enabled = True
        graph.cfg.seeded_mission_queue_strict = True
        state = _make_state()
        out = graph.ask_chatgpt_next_task(state)
        # State should be unchanged — the node exits early without calling the planner.
        assert out.stop_reason is None
        assert out.current_task is None
    finally:
        graph.cfg.seeded_mission_queue_enabled = original_enabled
        graph.cfg.seeded_mission_queue_strict = original_strict


def test_ask_chatgpt_next_task_not_skipped_when_strict_disabled():
    """ask_chatgpt_next_task does not skip due to strict flag when it is False."""
    original_enabled = graph.cfg.seeded_mission_queue_enabled
    original_strict = graph.cfg.seeded_mission_queue_strict
    # Stub the planner so it returns None → no task added → no_more_tasks stop_reason.
    original_planner = None
    try:
        graph.cfg.seeded_mission_queue_enabled = True
        graph.cfg.seeded_mission_queue_strict = False
        # Stub get_next_queued_task so queue is empty (planner path is reached)
        original_get_next = graph.get_next_queued_task
        graph.get_next_queued_task = lambda: None

        # Stub ChatGPTWorker to avoid real API calls
        import workers.chatgpt_worker as cw_mod
        original_cls = cw_mod.ChatGPTWorker

        class _FakePlanner:
            def ask_for_next_task(self, *a, **k):
                return None

        cw_mod.ChatGPTWorker = _FakePlanner
        # Also patch graph's reference
        original_graph_chatgpt = getattr(graph, "ChatGPTWorker", None)
        graph.ChatGPTWorker = _FakePlanner

        state = _make_state()
        out = graph.ask_chatgpt_next_task(state)
        # Should have tried the planner (got None) and set no_more_tasks
        assert out.stop_reason == "no_more_tasks"
    finally:
        graph.cfg.seeded_mission_queue_enabled = original_enabled
        graph.cfg.seeded_mission_queue_strict = original_strict
        graph.get_next_queued_task = original_get_next
        cw_mod.ChatGPTWorker = original_cls
        if original_graph_chatgpt is not None:
            graph.ChatGPTWorker = original_graph_chatgpt


def test_ask_chatgpt_for_task_if_needed_skipped_in_strict_mode():
    """ask_chatgpt_for_task_if_needed must never consult the planner in strict mode.

    This is the initial (first-task-of-the-run) planner entry point, distinct
    from ask_chatgpt_next_task. It must honor the strict flag the same way.
    """
    original_enabled = graph.cfg.seeded_mission_queue_enabled
    original_strict = graph.cfg.seeded_mission_queue_strict
    try:
        graph.cfg.seeded_mission_queue_enabled = True
        graph.cfg.seeded_mission_queue_strict = True
        state = _make_state(stop_reason="seeded_queue_exhausted")
        out = graph.ask_chatgpt_for_task_if_needed(state)
        # The node must exit early without calling the planner or touching
        # the stop_reason that seed_mission_queue_if_needed already set.
        assert out.stop_reason == "seeded_queue_exhausted"
        assert out.current_task is None
    finally:
        graph.cfg.seeded_mission_queue_enabled = original_enabled
        graph.cfg.seeded_mission_queue_strict = original_strict


def test_strict_stop_reason_survives_full_routing_without_calling_planner():
    """End-to-end reproduction of the M1 bug: strict mode + exhausted queue must
    stop with seeded_queue_exhausted and never reach the ChatGPT planner, no
    matter how routing chains the two seed/chatgpt nodes together.
    """
    original_enabled = graph.cfg.seeded_mission_queue_enabled
    original_strict = graph.cfg.seeded_mission_queue_strict
    captured = _stub_graph_seeded(mission=None, task_rows=[])

    import workers.chatgpt_worker as cw_mod
    original_cls = cw_mod.ChatGPTWorker
    original_graph_chatgpt = getattr(graph, "ChatGPTWorker", None)
    planner_called = []

    class _FailIfCalledPlanner:
        def ask_for_next_task(self, *a, **k):
            planner_called.append(True)
            return {"id": "should-not-happen", "title": "should not happen"}

    try:
        graph.cfg.seeded_mission_queue_enabled = True
        graph.cfg.seeded_mission_queue_strict = True
        type(graph.cfg).has_supabase = property(lambda self: True)
        cw_mod.ChatGPTWorker = _FailIfCalledPlanner
        graph.ChatGPTWorker = _FailIfCalledPlanner

        state = _make_state()
        state = graph.seed_mission_queue_if_needed(state)
        assert state.stop_reason == "seeded_queue_exhausted"

        next_node = graph._route_after_seed_mission_queue(state)
        assert next_node == "decide_continue_or_stop", (
            "strict-mode exhaustion must route straight to the stop check, "
            "not to ask_chatgpt_for_task_if_needed"
        )
        assert planner_called == [], "planner must never be consulted in strict mode"
        assert state.stop_reason == "seeded_queue_exhausted"
    finally:
        graph.cfg.seeded_mission_queue_enabled = original_enabled
        graph.cfg.seeded_mission_queue_strict = original_strict
        original_has_supabase = property(
            lambda self: bool(graph.cfg.supabase_url and graph.cfg.supabase_service_role_key)
        )
        type(graph.cfg).has_supabase = original_has_supabase
        cw_mod.ChatGPTWorker = original_cls
        if original_graph_chatgpt is not None:
            graph.ChatGPTWorker = original_graph_chatgpt
        _restore_graph_seeded()


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    tests = [
        test_seed_tasks_count,
        test_seed_tasks_titles,
        test_seed_tasks_types,
        test_seed_tasks_status_queued,
        test_seed_tasks_source,
        test_seed_tasks_mission_name,
        test_seed_tasks_seeded_mission_id,
        test_seed_tasks_seeded_task_id,
        test_seed_tasks_custom_branch_preserved,
        test_seed_tasks_auto_branch_when_empty,
        test_seed_tasks_preferred_worker_included,
        test_seed_tasks_no_preferred_worker_excluded,
        test_seed_tasks_uses_db_task_id,
        test_seed_tasks_generates_task_id_when_empty,
        test_seed_tasks_empty_list,
        test_seed_tasks_description_included,
        test_seed_tasks_no_description_excluded,
        test_check_completion_all_complete,
        test_check_completion_one_failed,
        test_check_completion_still_running,
        test_check_completion_queued_still_running,
        test_check_completion_no_rows,
        test_check_completion_blocked_counts_as_terminal,
        test_fetch_next_queued_mission_skips_business_target_when_disabled,
        test_fetch_next_queued_mission_claims_self_target,
        test_fetch_next_queued_mission_prefers_self_over_blocked_business,
        test_fetch_next_queued_mission_none_when_only_business_targets_disabled,
        test_fetch_next_queued_mission_logs_business_mission_blocked,
        test_fetch_next_queued_mission_claims_business_when_fully_configured,
        test_claim_refused_when_business_execution_disabled,
        test_claim_refused_when_missing_business_id,
        test_claim_refused_when_business_not_found,
        test_claim_refused_when_sandbox_not_configured,
        test_claim_refused_when_sandbox_config_absent,
        test_claim_refused_when_only_legacy_business_sandbox_config_populated,
        test_claim_refused_when_github_secret_unresolved,
        test_claim_refused_when_vercel_secret_unresolved,
        test_claim_allowed_when_fully_configured,
        test_business_execution_defaults_off_when_env_unset,
        test_business_execution_only_enabled_by_explicit_true,
        test_node_disabled_by_config,
        test_node_no_supabase,
        test_node_no_queued_mission,
        test_node_seeds_tasks_and_loads_first,
        test_node_skips_when_task_already_loaded,
        test_node_never_seeds_a_mission_that_is_already_in_the_local_queue,
        test_node_seeds_only_the_mission_task_that_is_actually_missing,
        test_node_gives_a_seeded_task_a_unique_id_when_one_is_taken,
        test_route_compile_no_task_to_seed_queue,
        test_route_compile_with_task_to_choose_worker,
        test_route_seed_queue_no_task_to_chatgpt,
        test_route_seed_queue_with_task_to_choose_worker,
        test_route_seed_queue_exhausted_to_decide_continue_or_stop,
        test_route_seed_queue_other_stop_reason_still_asks_chatgpt,
        test_node_is_wired_into_graph,
        test_compile_still_routes_to_chatgpt_via_seed_node,
        test_strict_mode_sets_stop_reason_when_no_mission,
        test_non_strict_mode_no_stop_reason_when_no_mission,
        test_strict_mode_does_not_stop_when_mission_exists,
        test_ask_chatgpt_next_task_skipped_in_strict_mode,
        test_ask_chatgpt_next_task_not_skipped_when_strict_disabled,
        test_ask_chatgpt_for_task_if_needed_skipped_in_strict_mode,
        test_strict_stop_reason_survives_full_routing_without_calling_planner,
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
