"""Tests for tools/completion_evidence.py — the M4c completion integrity gate.

The load-bearing test is ``TestAiInfra03Regression``: it replays the exact
worker output and state that got ``ai-infra-03`` scored complete twice with
nothing deployed, and asserts the task is now marked *blocked* and never
synced to Supabase as done.

Everything else covers the two halves of the gate independently:
- ``TestRefusal*`` / ``TestQuestion*`` / ``TestNoOp*`` — the detection patterns
- ``TestFiles/Commit/Deployment Evidence`` — the verifiers, each of which
  consults something outside the worker's own summary
- ``TestGenuineCompletion`` — real work still passes, which is the constraint
  that keeps this gate from being turned off
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

import tools.completion_evidence as ce
from tools.completion_evidence import (
    EVENT_MISSING,
    EVENT_NO_OP_OVERRIDDEN,
    EVENT_VERIFIED,
    EVIDENCE_ARTIFACT,
    EVIDENCE_COMMIT,
    EVIDENCE_DEPLOYMENT,
    EVIDENCE_FILES,
    EVIDENCE_MERGED_PR,
    NO_OP,
    QUESTION,
    REFUSAL,
    detect_refusal,
    evaluate_completion,
    guard_completion_evidence,
    required_evidence,
    verify_commit_evidence,
    verify_deployment_evidence,
    verify_evidence,
    verify_files_evidence,
    verify_merged_pr_evidence,
)

import graph
from state import RunnerState


@pytest.fixture(autouse=True)
def _silence_log_events(monkeypatch):
    events = []
    monkeypatch.setattr(ce, "log_event", lambda et, payload, **kw: events.append((et, payload)))
    yield events


@pytest.fixture
def logged(_silence_log_events):
    return _silence_log_events


def _kinds(signals) -> set:
    return {s["kind"] for s in signals}


def _patterns(signals) -> set:
    return {s["pattern"] for s in signals}


# A summary with real, verifiable work in it — the baseline that must never
# trip the gate. The file genuinely exists in this repo.
_REAL_FILE = "runner/langgraph/tools/completion_evidence.py"
_REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))


def _good_summary(**over) -> dict:
    base = {
        "files_created": [_REAL_FILE],
        "files_modified": [],
        "check_result": True,
        "commit_result": "abc1234",
    }
    base.update(over)
    return base


_GOOD_OUTPUT = """
I added the completion evidence gate and wired it into update_logs_and_state.

- Files Created: runner/langgraph/tools/completion_evidence.py
- Check Result: pass
- Commit Result: abc1234
"""


# ---------------------------------------------------------------------------
# Refusal detection
# ---------------------------------------------------------------------------

class TestRefusalPatterns:
    @pytest.mark.parametrize("output", [
        "I am not going to run this deployment without confirmation.",
        "I'm not going to execute that command.",
        "I will not deploy this to production.",
        "I would not execute this without a review.",
        "I am unable to complete this task as specified.",
        "I'm not able to proceed with the deploy.",
        "I cannot complete this task.",
        "I can't proceed with the requested change.",
        "I am refusing to run a destructive migration.",
        "I did not actually deploy anything.",
        "I have not committed these changes.",
        "No changes were made to the repository.",
    ])
    def test_each_refusal_phrase_is_detected(self, output):
        signals = detect_refusal(output, _good_summary())
        assert REFUSAL in _kinds(signals), f"not detected as a refusal: {output!r}"

    def test_a_refusal_blocks_even_with_verified_evidence(self):
        """A refusal is a statement that the work was not done. Ambient
        evidence — a file that happened to already exist — does not overrule it."""
        verdict = evaluate_completion(
            _good_summary(),
            {"id": "t1", "type": "backend"},
            "I am not going to make this change.",
            repo_path=_REPO,
        )
        assert verdict["blocked"] is True
        assert verdict["complete"] is False
        assert any("refusal" in r for r in verdict["reasons"])

    def test_refusal_inside_a_code_fence_is_not_the_workers_voice(self):
        output = _GOOD_OUTPUT + "\nThe old prompt said:\n```\nI am not going to do that\n```\n"
        assert REFUSAL not in _kinds(detect_refusal(output, _good_summary()))


# ---------------------------------------------------------------------------
# Question detection — "a worker whose output is a question is blocked"
# ---------------------------------------------------------------------------

class TestQuestionPatterns:
    @pytest.mark.parametrize("output", [
        "So, do you want me to: 1. Execute it 2. Just summarize the plan",
        "Would you like me to apply the migration now.",
        "Should I proceed with the deploy.",
        "Let me know which approach you prefer.",
        "Please confirm before I continue.",
        "Which option do you want here.",
        "Waiting for your confirmation before deploying.",
    ])
    def test_each_question_phrase_is_detected(self, output):
        signals = detect_refusal(output, _good_summary())
        assert QUESTION in _kinds(signals), f"not detected as a question: {output!r}"

    def test_output_ending_in_a_question_mark_is_a_question(self):
        signals = detect_refusal(_GOOD_OUTPUT + "\nShall I continue with the next step?", _good_summary())
        assert QUESTION in _kinds(signals)
        assert "output ends with a question" in _patterns(signals)

    def test_a_question_blocks_by_definition(self):
        verdict = evaluate_completion(
            _good_summary(),
            {"id": "t1", "type": "backend"},
            "do you want me to: 1. Execute it... 2. Just summarize...",
            repo_path=_REPO,
        )
        assert verdict["blocked"] is True
        assert any("question" in r for r in verdict["reasons"])

    def test_a_normal_report_is_not_a_question(self):
        assert QUESTION not in _kinds(detect_refusal(_GOOD_OUTPUT, _good_summary()))


# ---------------------------------------------------------------------------
# No-op detection — reported, but overrulable by real evidence
# ---------------------------------------------------------------------------

class TestNoOpPatterns:
    def test_zero_created_and_zero_modified(self):
        signals = detect_refusal("Ran the analysis.", {"files_created": [], "files_modified": []})
        assert "zero files created and zero modified" in _patterns(signals)

    def test_none_placeholders_count_as_zero(self):
        signals = detect_refusal("Ran it.", {"files_created": ["none"], "files_modified": ["N/A"]})
        assert "zero files created and zero modified" in _patterns(signals)

    def test_commit_result_skipped(self):
        signals = detect_refusal("Done.", _good_summary(commit_result="skipped"))
        assert "Commit Result: skipped" in _patterns(signals)

    def test_missing_commit_result_counts_as_skipped(self):
        signals = detect_refusal("Done.", _good_summary(commit_result=None))
        assert "Commit Result: skipped" in _patterns(signals)

    @pytest.mark.parametrize("phrase,expected", [
        ("There is no new commit on this branch.", "no new commit"),
        ("git reported nothing to commit, working tree clean.", "nothing to commit"),
    ])
    def test_no_commit_phrases(self, phrase, expected):
        assert expected in _patterns(detect_refusal(phrase, _good_summary()))

    def test_no_op_signal_does_not_block_when_evidence_verifies(self):
        """Evidence beats self-report: a worker that under-reported its own
        summary but left a real file on disk is complete, not blocked."""
        verdict = evaluate_completion(
            _good_summary(commit_result="skipped"),
            {"id": "t1", "type": "backend"},
            _GOOD_OUTPUT,
            repo_path=_REPO,
        )
        assert verdict["complete"] is True
        assert NO_OP in _kinds(verdict["signals"])

    def test_no_op_override_is_logged(self, logged):
        guard_completion_evidence(
            summary=_good_summary(commit_result="skipped"),
            task={"id": "t1", "type": "backend"},
            raw_output=_GOOD_OUTPUT,
            repo_path=_REPO,
        )
        assert EVENT_NO_OP_OVERRIDDEN in [e for e, _ in logged]


# ---------------------------------------------------------------------------
# Evidence type: a file that exists on disk
# ---------------------------------------------------------------------------

class TestFilesEvidence:
    def test_a_file_that_exists_is_evidence(self):
        ev = verify_files_evidence({"files_created": [_REAL_FILE]}, _REPO)
        assert ev["verified"] is True
        assert _REAL_FILE in ev["detail"]

    def test_a_file_that_does_not_exist_is_not_evidence(self):
        ev = verify_files_evidence({"files_created": ["totally/made/up.py"]}, _REPO)
        assert ev["verified"] is False
        assert "totally/made/up.py" in ev["detail"]

    def test_leading_dot_slash_is_tolerated(self):
        assert verify_files_evidence({"files_modified": [f"./{_REAL_FILE}"]}, _REPO)["verified"] is True

    def test_no_claims_is_not_evidence(self):
        assert verify_files_evidence({"files_created": [], "files_modified": []}, _REPO)["verified"] is False

    def test_partial_miss_still_counts_but_is_reported(self):
        ev = verify_files_evidence({"files_created": [_REAL_FILE, "nope.py"]}, _REPO)
        assert ev["verified"] is True
        assert "nope.py" in ev["detail"]

    def test_without_a_repo_path_nothing_can_be_confirmed(self):
        assert verify_files_evidence({"files_created": [_REAL_FILE]}, "")["verified"] is False


# ---------------------------------------------------------------------------
# Evidence type: a commit sha that exists in the expected remote
# ---------------------------------------------------------------------------

def _git_stub(*, exists=True, remote_branches="  origin/feature/x\n"):
    """Stand in for git. Returns (ok, output) per invocation."""
    def runner(args, cwd):
        if args[0] == "cat-file":
            return exists, ""
        if args[0] == "branch":
            return True, remote_branches
        raise AssertionError(f"unexpected git call: {args}")
    return runner


class TestCommitEvidence:
    def test_a_pushed_commit_is_evidence(self):
        ev = verify_commit_evidence({"sha": "deadbeefcafe"}, "/repo", git_runner=_git_stub())
        assert ev["verified"] is True
        assert "deadbeefcafe"[:12] in ev["detail"]

    def test_a_commit_that_does_not_exist_is_not_evidence(self):
        ev = verify_commit_evidence({"sha": "deadbeefcafe"}, "/repo", git_runner=_git_stub(exists=False))
        assert ev["verified"] is False
        assert "does not exist" in ev["detail"]

    def test_an_unpushed_commit_is_not_evidence(self):
        """It exists locally but no remote branch contains it, so nothing
        outside this machine can confirm the work."""
        ev = verify_commit_evidence({"sha": "deadbeefcafe"}, "/repo", git_runner=_git_stub(remote_branches=""))
        assert ev["verified"] is False
        assert "never pushed" in ev["detail"]

    def test_a_commit_on_a_different_remote_is_not_evidence(self):
        ev = verify_commit_evidence(
            {"sha": "deadbeefcafe"}, "/repo",
            remote="origin", git_runner=_git_stub(remote_branches="  upstream/main\n"),
        )
        assert ev["verified"] is False

    def test_nothing_to_commit_is_never_evidence(self):
        """``commit_all`` reports a clean tree as "landed" and hands back the
        pre-existing HEAD so deploys aren't skipped. That sha predates the task
        — it is exactly what ai-infra-03 carried into its deploy."""
        ev = verify_commit_evidence(
            {"sha": "deadbeefcafe", "nothing_to_commit": True, "committed": True},
            "/repo", git_runner=_git_stub(),
        )
        assert ev["verified"] is False
        assert "predates this task" in ev["detail"]

    def test_no_sha_is_not_evidence(self):
        assert verify_commit_evidence({}, "/repo", git_runner=_git_stub())["verified"] is False

    def test_no_repo_path_cannot_confirm(self):
        assert verify_commit_evidence({"sha": "abc123"}, "", git_runner=_git_stub())["verified"] is False


# ---------------------------------------------------------------------------
# Evidence type: a successfully merged PR (M4c.4)
# ---------------------------------------------------------------------------

_MERGE_RESULT = {"success": True, "sha": "deadbeefcafe", "pr_number": 107}


class TestMergedPrEvidence:
    def test_a_successful_merge_with_sha_is_evidence(self):
        ev = verify_merged_pr_evidence(_MERGE_RESULT)
        assert ev["verified"] is True
        assert "107" in ev["detail"]
        assert "deadbeefcafe"[:12] in ev["detail"]

    def test_detail_includes_pr_number_when_present(self):
        ev = verify_merged_pr_evidence({"success": True, "sha": "abc123", "pr_number": 42})
        assert "PR #42" in ev["detail"]

    def test_no_merge_result_is_not_evidence(self):
        ev = verify_merged_pr_evidence(None)
        assert ev["verified"] is False
        assert "no merge result" in ev["detail"]

    def test_a_failed_merge_is_not_evidence(self):
        ev = verify_merged_pr_evidence({"success": False, "sha": "deadbeefcafe"})
        assert ev["verified"] is False
        assert "not successful" in ev["detail"]

    def test_a_merge_with_no_sha_is_not_evidence(self):
        ev = verify_merged_pr_evidence({"success": True, "sha": ""})
        assert ev["verified"] is False

    def test_merged_pr_satisfies_artifact_evidence(self):
        """A merged PR is accepted as artifact evidence even when no files are
        on disk and the commit sha is not checked (working tree clean, branch gone)."""
        ev = verify_evidence(
            {"files_created": [], "files_modified": []},
            repo_path="/nonexistent",
            commit={"sha": "abc123", "nothing_to_commit": True},
            merge_result=_MERGE_RESULT,
            git_runner=_git_stub(),
        )
        assert ev[EVIDENCE_MERGED_PR]["verified"] is True
        assert ev[EVIDENCE_ARTIFACT]["verified"] is True
        assert "deadbeefcafe"[:12] in ev[EVIDENCE_ARTIFACT]["detail"]

    def test_merged_pr_does_not_rescue_a_refusal(self):
        """A hard signal (refusal/question) blocks even with a merged PR sha — the
        gate cannot know if the merge was from a different run or a stale branch."""
        verdict = evaluate_completion(
            {"files_created": [], "files_modified": []},
            {"id": "t1", "type": "backend"},
            "I am not going to make this change.",
            repo_path="/nonexistent",
            merge_result=_MERGE_RESULT,
            git_runner=_git_stub(),
        )
        assert verdict["blocked"] is True
        assert any("refusal" in r for r in verdict["reasons"])

    def test_a_task_that_produced_nothing_is_still_blocked(self):
        """No merge result AND no files AND commit is nothing_to_commit: blocked."""
        verdict = evaluate_completion(
            {"files_created": [], "files_modified": []},
            {"id": "t1", "type": "backend"},
            "Ran the analysis, no changes needed.",
            repo_path=_REPO,
            commit={"sha": "abc123", "nothing_to_commit": True},
            merge_result=None,
            git_runner=_git_stub(),
        )
        assert verdict["blocked"] is True
        assert verdict["evidence"][EVIDENCE_ARTIFACT]["verified"] is False

    def test_artifact_can_be_satisfied_by_merged_pr_alone(self):
        """evaluate_completion accepts merged PR as evidence for a backend task."""
        verdict = evaluate_completion(
            {"files_created": [], "files_modified": []},
            {"id": "t1", "type": "backend"},
            "Completed the work and pushed.\n- Check Result: pass\n- Commit Result: abc1234",
            repo_path="/nonexistent",
            merge_result=_MERGE_RESULT,
            git_runner=_git_stub(),
        )
        assert verdict["complete"] is True, verdict["reasons"]
        assert EVIDENCE_ARTIFACT in verdict["satisfied"]


# ---------------------------------------------------------------------------
# Evidence type: a deployment that responds to a real request
# ---------------------------------------------------------------------------

def _probe(ok=True, detail="HTTP 200"):
    def probe(url):
        probe.called_with = url
        return ok, detail
    probe.called_with = None
    return probe


_READY = {"ready": True, "state": "READY", "deployment": {"uid": "dpl_1", "url": "app.vercel.app"}}


class TestDeploymentEvidence:
    def test_a_ready_deployment_that_answers_is_evidence(self):
        probe = _probe()
        ev = verify_deployment_evidence({"url": "https://app.vercel.app", "poll": _READY}, http_probe=probe)
        assert ev["verified"] is True
        assert probe.called_with == "https://app.vercel.app"

    def test_a_bare_hostname_is_probed_over_https(self):
        probe = _probe()
        verify_deployment_evidence({"url": "app.vercel.app", "poll": _READY}, http_probe=probe)
        assert probe.called_with == "https://app.vercel.app"

    def test_a_url_that_does_not_answer_is_not_evidence(self):
        ev = verify_deployment_evidence(
            {"url": "https://app.vercel.app", "poll": _READY},
            http_probe=_probe(ok=False, detail="ConnectionError: refused"),
        )
        assert ev["verified"] is False
        assert "did not answer" in ev["detail"]

    def test_a_deployment_that_never_went_ready_is_not_evidence(self):
        ev = verify_deployment_evidence(
            {"url": "https://app.vercel.app", "poll": {"ready": False, "state": "ERROR"}},
            http_probe=_probe(),
        )
        assert ev["verified"] is False
        assert "ERROR" in ev["detail"]

    def test_a_null_deploy_result_is_not_evidence(self):
        ev = verify_deployment_evidence(None, http_probe=_probe())
        assert ev["verified"] is False
        assert "nothing was deployed" in ev["detail"]

    def test_a_deploy_result_with_no_id_or_url_is_not_evidence(self):
        assert verify_deployment_evidence({"success": True}, http_probe=_probe())["verified"] is False

    def test_the_probe_is_never_called_for_an_unready_deployment(self):
        probe = _probe()
        verify_deployment_evidence({"url": "https://x.dev", "poll": {"ready": False}}, http_probe=probe)
        assert probe.called_with is None


# ---------------------------------------------------------------------------
# Which evidence a task type owes
# ---------------------------------------------------------------------------

class TestRequiredEvidence:
    @pytest.mark.parametrize("task", [
        {"type": "deploy"},
        {"type": "deployment"},
        {"type": "release"},
        {"type": "infra", "title": "Deploy the scaffolded app"},
        {"type": "general", "description": "Ship the new landing page to production"},
    ])
    def test_deploy_tasks_owe_a_deployment(self, task):
        assert required_evidence(task) == [EVIDENCE_DEPLOYMENT]

    @pytest.mark.parametrize("task", [
        {"type": "backend", "title": "Add a completion evidence gate"},
        {"type": "frontend", "title": "Fix the header spacing"},
        {"type": "infra", "title": "Rotate the CI cache key"},
        {},
    ])
    def test_everything_else_owes_an_artifact(self, task):
        assert required_evidence(task) == [EVIDENCE_ARTIFACT]

    @pytest.mark.parametrize("title", [
        "Fix the deploy script",
        "Update the deployment config",
        "Document the release process",
        "Rotate the deploy token",
        "Add a deploy workflow",
    ])
    def test_tasks_about_deploy_tooling_owe_only_an_artifact(self, title):
        """Their deliverable is a diff, not a running site — the word is a noun."""
        assert required_evidence({"type": "infra", "title": title}) == [EVIDENCE_ARTIFACT]

    def test_a_deploy_task_falls_back_to_artifact_when_deploys_are_off(self):
        """With AUTO_DEPLOY off or no Vercel token the runner never attempts a
        deploy, so demanding deployment evidence would block the task forever."""
        task = {"type": "deploy", "title": "Deploy the scaffolded app"}
        assert required_evidence(task, deploy_available=False) == [EVIDENCE_ARTIFACT]
        assert required_evidence(task, deploy_available=True) == [EVIDENCE_DEPLOYMENT]

    def test_a_real_deploy_task_still_completes_on_its_diff_when_deploys_are_off(self):
        verdict = evaluate_completion(
            _good_summary(),
            {"id": "d1", "type": "deploy", "title": "Deploy the scaffolded app"},
            _GOOD_OUTPUT,
            repo_path=_REPO,
            deploy_available=False,
        )
        assert verdict["complete"] is True, verdict["reasons"]

    def test_the_fallback_still_blocks_ai_infra_03(self):
        """The escape hatch must not reopen the hole: ai-infra-03 produced no
        artifact either, so it stays blocked even with deploys unavailable."""
        verdict = evaluate_completion(
            _AI_INFRA_03_SUMMARY,
            _AI_INFRA_03_TASK,
            _AI_INFRA_03_OUTPUT,
            repo_path=_REPO,
            commit={"sha": "abc1234", "nothing_to_commit": True, "committed": True},
            deploy_available=False,
        )
        assert verdict["blocked"] is True
        assert verdict["required"] == [EVIDENCE_ARTIFACT]
        assert verdict["satisfied"] == []

    def test_artifact_is_satisfied_by_files_or_by_commit(self):
        by_files = verify_evidence(_good_summary(), repo_path=_REPO, commit=None)
        assert by_files[EVIDENCE_ARTIFACT]["verified"] is True

        by_commit = verify_evidence(
            {"files_created": [], "files_modified": []},
            repo_path="/repo",
            commit={"sha": "deadbeefcafe"},
            git_runner=_git_stub(),
        )
        assert by_commit[EVIDENCE_FILES]["verified"] is False
        assert by_commit[EVIDENCE_COMMIT]["verified"] is True
        assert by_commit[EVIDENCE_ARTIFACT]["verified"] is True

    def test_artifact_fails_when_neither_holds(self):
        ev = verify_evidence({"files_created": ["ghost.py"]}, repo_path=_REPO, commit={})
        assert ev[EVIDENCE_ARTIFACT]["verified"] is False


# ---------------------------------------------------------------------------
# A genuine completion still passes
# ---------------------------------------------------------------------------

class TestGenuineCompletion:
    def test_a_real_code_task_completes(self):
        verdict = evaluate_completion(
            _good_summary(),
            {"id": "m4c-01", "type": "backend", "title": "Add a completion evidence gate"},
            _GOOD_OUTPUT,
            repo_path=_REPO,
        )
        assert verdict["complete"] is True, verdict["reasons"]
        assert verdict["blocked"] is False
        assert verdict["reasons"] == []
        assert verdict["satisfied"] == [EVIDENCE_ARTIFACT]

    def test_a_real_deploy_task_completes(self):
        verdict = evaluate_completion(
            {"files_created": [], "files_modified": [], "commit_result": "abc1234"},
            {"id": "d1", "type": "deploy", "title": "Deploy the app"},
            "Deployed to production and verified the build.\n- Check Result: pass",
            repo_path=_REPO,
            deploy_result={"url": "https://app.vercel.app", "poll": _READY},
            http_probe=_probe(),
        )
        assert verdict["complete"] is True, verdict["reasons"]
        assert verdict["satisfied"] == [EVIDENCE_DEPLOYMENT]

    def test_a_real_completion_completes_via_commit_alone(self):
        verdict = evaluate_completion(
            {"files_created": [], "files_modified": [], "commit_result": "deadbeefcafe"},
            {"id": "m4c-02", "type": "backend", "title": "Tidy the config"},
            "Committed and pushed the change.\n- Check Result: pass",
            repo_path="/repo",
            commit={"sha": "deadbeefcafe"},
            git_runner=_git_stub(),
        )
        assert verdict["complete"] is True, verdict["reasons"]

    def test_a_verified_completion_is_logged_as_such(self, logged):
        guard_completion_evidence(
            summary=_good_summary(),
            task={"id": "t1", "type": "backend"},
            raw_output=_GOOD_OUTPUT,
            context="unit",
            repo_path=_REPO,
        )
        assert EVENT_VERIFIED in [e for e, _ in logged]

    def test_a_blocked_completion_is_logged_with_its_reasons(self, logged):
        guard_completion_evidence(
            summary={"files_created": [], "files_modified": []},
            task={"id": "t1", "type": "backend"},
            raw_output="do you want me to proceed",
            context="unit",
            repo_path=_REPO,
        )
        missing = [p for e, p in logged if e == EVENT_MISSING]
        assert len(missing) == 1
        assert missing[0]["reasons"]
        assert missing[0]["task_id"] == "t1"


# ---------------------------------------------------------------------------
# The ai-infra-03 regression, end to end through the graph node
# ---------------------------------------------------------------------------

# Verbatim shape of the output that was scored complete on 2026-07-30 03:34 and
# again on 2026-07-31 02:29 (logs/runs.jsonl).
_AI_INFRA_03_OUTPUT = """
I've reviewed the repo and the Vercel project configuration. The deploy script
is ready but I have not run it.

So, do you want me to:
1. Execute it now against the production project
2. Just summarize what it would do
"""

_AI_INFRA_03_SUMMARY = {
    "files_created": [],
    "files_modified": [],
    "check_result": None,
    "commit_result": None,
}

_AI_INFRA_03_TASK = {
    "id": "ai-infra-03",
    "title": "Deploy the scaffolded app",
    "type": "infra",
    "branch": "feature/ai-infra/deploy",
    "description": (
        "Deploy the fresh scaffolded repo (Node.js, React, AWS for cloud "
        "infrastructure) to its Vercel project and verify the production build."
    ),
}


class TestAiInfra03Regression:
    def test_the_verdict_is_blocked_not_complete(self):
        verdict = evaluate_completion(
            _AI_INFRA_03_SUMMARY,
            _AI_INFRA_03_TASK,
            _AI_INFRA_03_OUTPUT,
            repo_path=_REPO,
            commit={"sha": "abc1234", "nothing_to_commit": True, "committed": True},
            deploy_result=None,
        )
        assert verdict["complete"] is False
        assert verdict["blocked"] is True
        assert QUESTION in _kinds(verdict["signals"])
        assert NO_OP in _kinds(verdict["signals"])
        assert verdict["required"] == [EVIDENCE_DEPLOYMENT]
        assert verdict["satisfied"] == []

    def test_a_ready_looking_deploy_result_does_not_rescue_it(self):
        """The second run *did* have a READY deploy_result — for a URL that
        predated the task. The question in the output blocks regardless."""
        verdict = evaluate_completion(
            _AI_INFRA_03_SUMMARY,
            _AI_INFRA_03_TASK,
            _AI_INFRA_03_OUTPUT,
            repo_path=_REPO,
            deploy_result={"url": "https://bucks-ai-app-archive.vercel.app/", "poll": _READY},
            http_probe=_probe(),
        )
        assert verdict["blocked"] is True


class TestUpdateLogsAndStateIntegration:
    """The gate must bite in graph.update_logs_and_state, which is the only
    place that can say 'complete'."""

    def _run(self, state, monkeypatch, gate_enabled=True):
        calls = {"complete": [], "failed": [], "blocked": []}
        monkeypatch.setattr(graph, "mark_task_complete", lambda tid, s: calls["complete"].append((tid, s)))
        monkeypatch.setattr(graph, "mark_task_failed", lambda tid, e: calls["failed"].append((tid, e)))
        monkeypatch.setattr(graph, "mark_task_blocked", lambda tid, r: calls["blocked"].append((tid, r)))
        monkeypatch.setattr(graph, "update_state", lambda *a, **k: None)
        monkeypatch.setattr(graph, "log_event", lambda *a, **k: None)
        monkeypatch.setattr(graph.cfg, "failure_guard_enabled", False)
        monkeypatch.setattr(graph.cfg, "cost_budget_guard_enabled", False)
        monkeypatch.setattr(graph.cfg, "stale_run_watchdog_enabled", False)
        monkeypatch.setattr(graph.cfg, "worker_timeout_guard_enabled", False)
        monkeypatch.setattr(graph.cfg, "completion_evidence_gate_enabled", gate_enabled)
        return graph.update_logs_and_state(state), calls

    def _refusal_state(self):
        return RunnerState(
            current_task_id="ai-infra-03",
            current_task=dict(_AI_INFRA_03_TASK),
            worker_result={"success": True, "output": _AI_INFRA_03_OUTPUT},
            worker_summary=dict(_AI_INFRA_03_SUMMARY),
            last_commit="abc1234",
            last_commit_result={"sha": "abc1234", "nothing_to_commit": True, "committed": True},
        )

    def test_a_refusal_is_blocked_never_completed(self, monkeypatch):
        out, calls = self._run(self._refusal_state(), monkeypatch)
        assert calls["complete"] == [], "a refusal was scored as a completion"
        assert len(calls["blocked"]) == 1
        assert calls["blocked"][0][0] == "ai-infra-03"
        assert "no evidence of completion" in calls["blocked"][0][1]
        assert out.completion_evidence_status == "blocked"

    def test_a_refusal_is_not_scored_as_a_failure_either(self, monkeypatch):
        """Nothing broke — work was left undone. Marking it failed would trip
        the circuit breaker and reset counters that belong to real failures."""
        state = self._refusal_state()
        state.consecutive_failures = 2
        out, calls = self._run(state, monkeypatch)
        assert calls["failed"] == []
        assert out.consecutive_failures == 2

    def test_the_loop_keeps_going_because_the_block_is_task_scoped(self, monkeypatch):
        out, _ = self._run(self._refusal_state(), monkeypatch)
        assert out.stop_reason is None, out.stop_reason

    def test_real_work_still_completes_through_the_node(self, monkeypatch):
        state = RunnerState(
            current_task_id="m4c-01",
            current_task={"id": "m4c-01", "type": "backend", "title": "Add the gate"},
            worker_result={"success": True, "output": _GOOD_OUTPUT},
            worker_summary=_good_summary(),
            worker_summary_digest="Task: Add the gate\nCheck: pass",
        )
        out, calls = self._run(state, monkeypatch)
        assert calls["blocked"] == []
        assert calls["complete"] == [("m4c-01", "Task: Add the gate\nCheck: pass")]
        assert out.completion_evidence_status == "verified"
        assert out.consecutive_failures == 0

    def test_evidence_is_cleared_before_the_next_task_runs(self):
        """Otherwise a refusing task inherits the previous task's commit and is
        'proved' complete by work it never did."""
        state = RunnerState(
            last_commit_result={"sha": "deadbeefcafe", "committed": True},
            completion_evidence={"complete": True},
            completion_evidence_status="verified",
        )
        graph._reset_task_scoped_state(state)
        assert state.last_commit_result is None
        assert state.completion_evidence is None
        assert state.completion_evidence_status is None

    def test_a_refusal_is_not_rescued_by_a_previous_tasks_commit(self, monkeypatch):
        """The end-to-end consequence of the reset above: a genuine pushed commit
        left over from the prior task must not complete this one."""
        state = self._refusal_state()
        graph._reset_task_scoped_state(state)
        state.current_task_id = "ai-infra-03"
        state.current_task = dict(_AI_INFRA_03_TASK)
        state.worker_result = {"success": True, "output": _AI_INFRA_03_OUTPUT}
        state.worker_summary = dict(_AI_INFRA_03_SUMMARY)
        out, calls = self._run(state, monkeypatch)
        assert calls["complete"] == []
        assert len(calls["blocked"]) == 1
        assert out.completion_evidence_status == "blocked"

    def test_disabling_the_gate_restores_the_old_behaviour(self, monkeypatch):
        out, calls = self._run(self._refusal_state(), monkeypatch, gate_enabled=False)
        assert len(calls["complete"]) == 1
        assert out.completion_evidence_status == "skipped"

    def _busy_deploy_state(self, **task_over) -> RunnerState:
        """A deploy task that edited one real file and deployed nothing. Its
        artifact evidence verifies; only the deployment requirement can block it."""
        task = {"id": "ai-infra-03", "type": "infra", "title": "Deploy the scaffolded app"}
        task.update(task_over)
        return RunnerState(
            current_task_id=task["id"],
            current_task=task,
            worker_result={"success": True, "output": "Adjusted the deploy config file.\n- Check Result: pass"},
            worker_summary=_good_summary(commit_result="abc1234"),
            worker_summary_digest="Task: Deploy\nCheck: pass",
            deploy_result=None,
        )

    def test_a_business_deploy_task_still_owes_a_deployment_without_a_runner_token(self, monkeypatch):
        """A business mission deploys with the *business's* own scoped token, so
        the runner's own VERCEL_TOKEN says nothing about whether its deploy was
        possible. Reading its absence as 'no deploy available' would drop
        ai-infra-03 back to artifact evidence, which one stray file satisfies."""
        monkeypatch.setattr(graph.cfg, "auto_deploy", True)
        monkeypatch.setattr(graph.cfg, "vercel_token", "")
        state = self._busy_deploy_state(business_id="biz-1")
        out, calls = self._run(state, monkeypatch)
        assert calls["complete"] == [], "a business deploy task completed with nothing deployed"
        assert len(calls["blocked"]) == 1
        assert out.completion_evidence["required"] == [EVIDENCE_DEPLOYMENT]

    def test_a_bucks_ai_deploy_task_falls_back_to_artifact_without_a_token(self, monkeypatch):
        """The other side of the same condition: a non-business deploy task
        genuinely cannot deploy without the runner's token, so it must not be
        held to a bar it can never clear."""
        monkeypatch.setattr(graph.cfg, "auto_deploy", True)
        monkeypatch.setattr(graph.cfg, "vercel_token", "")
        out, calls = self._run(self._busy_deploy_state(), monkeypatch)
        assert len(calls["complete"]) == 1
        assert out.completion_evidence["required"] == [EVIDENCE_ARTIFACT]


class TestConfigAndRegistry:
    def test_the_gate_is_on_by_default(self, monkeypatch):
        from config import RunnerConfig

        monkeypatch.delenv("COMPLETION_EVIDENCE_GATE_ENABLED", raising=False)
        assert RunnerConfig().completion_evidence_gate_enabled is True

    def test_the_gate_can_be_turned_off_by_env(self, monkeypatch):
        from config import RunnerConfig

        monkeypatch.setenv("COMPLETION_EVIDENCE_GATE_ENABLED", "false")
        assert RunnerConfig().completion_evidence_gate_enabled is False

    def test_it_is_registered_as_a_task_scoped_gate(self):
        from tools.gate_authority import SCOPE_TASK, gate_authority

        entry = gate_authority("completion_evidence")
        assert entry["known"] is True
        assert entry["scope"] == SCOPE_TASK
        assert entry["external"] is True

    def test_its_stop_reason_has_a_diagnostic_handler(self):
        from tools.stop_diagnostics import get_handler

        handler = get_handler("no_completion_evidence")
        assert handler is not None
        assert handler.gate == "completion_evidence"
