"""Tests for tools/wip_checkpoint.py — M4c.4 crash-safe checkpointing.

Every git call is mocked through the injectable ``git_run`` seam: this module
runs ``git add -A`` / ``git commit`` / ``git push`` for a living, and a test
suite that let any of that reach a real repository would be the second way this
feature could destroy work.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

import tools.wip_checkpoint as wc
from tools.git_autonomy import GitResult
from tools.wip_checkpoint import (
    CheckpointContext,
    PROTECTED_BRANCHES,
    WIP_SUBJECT_PREFIX,
    checkpoint_wip,
    detect_wip_checkpoint,
    format_checkpoint_message,
    format_wip_prompt_notice,
    install_checkpoint_handlers,
    resolve_checkpoint_branch,
    wip_branch_for,
)


# ---------------------------------------------------------------------------
# Fake git
# ---------------------------------------------------------------------------

class FakeGit:
    """Records every git invocation and answers from a per-command script.

    Keys are matched on the first one or two argv tokens ("commit",
    "rev-parse", "checkout"), which is enough to steer every path here without
    the tests having to spell out full argument lists.
    """

    def __init__(self, dirty=("tools/state_self_healing.py", "tests/test_x.py"), **responses):
        self.calls = []
        self.dirty = list(dirty)
        self.responses = responses

    def __call__(self, args, cwd, timeout=120):
        args = list(args)
        self.calls.append((tuple(args), cwd))
        key = args[0]
        if key == "status":
            porcelain = "\n".join(f" M {p}" for p in self.dirty)
            return GitResult(success=True, output=porcelain, args=tuple(args))
        for candidate in (" ".join(args[:2]), key):
            if candidate in self.responses:
                return self.responses[candidate]
        defaults = {
            "branch": GitResult(success=True, output="feature/m4c4/crash-safe"),
            "rev-parse": GitResult(success=True, output="a" * 40),
            "add": GitResult(success=True, output=""),
            "commit": GitResult(success=True, output="[feature 1234567] WIP"),
            "remote": GitResult(success=True, output="git@github.com:bucks-ai/bucks-ai.git"),
            "push": GitResult(success=True, output=""),
            "checkout": GitResult(success=True, output=""),
            "log": GitResult(success=True, output=""),
            "show": GitResult(success=True, output=""),
        }
        return defaults.get(key, GitResult(success=True, output=""))

    def ran(self, *tokens) -> bool:
        return any(tuple(args[: len(tokens)]) == tokens for args, _ in self.calls)

    def args_for(self, *tokens):
        for args, _ in self.calls:
            if tuple(args[: len(tokens)]) == tokens:
                return list(args)
        return None


@pytest.fixture(autouse=True)
def _reset_module_state():
    wc.reset_handlers_for_tests()
    yield
    wc.reset_handlers_for_tests()


@pytest.fixture
def events(monkeypatch):
    recorded = []
    monkeypatch.setattr(wc, "log_event", lambda t, p, task_id=None: recorded.append((t, p)))
    return recorded


def _types(events):
    return [t for t, _ in events]


def _payload(events, event_type):
    for t, p in events:
        if t == event_type:
            return p
    return None


# ---------------------------------------------------------------------------
# Branch resolution — never onto a protected branch
# ---------------------------------------------------------------------------

class TestBranchResolution:
    def test_feature_branch_is_used_as_is(self):
        resolved = resolve_checkpoint_branch("feature/m4c4/crash-safe", "m4c-04")
        assert resolved == {
            "branch": "feature/m4c4/crash-safe",
            "redirected": False,
            "reason": "",
            "current": "feature/m4c4/crash-safe",
        }

    @pytest.mark.parametrize("branch", sorted(PROTECTED_BRANCHES))
    def test_every_protected_branch_redirects_to_a_wip_branch(self, branch):
        resolved = resolve_checkpoint_branch(branch, "m4c-04")
        assert resolved["branch"] == "wip/m4c-04"
        assert resolved["redirected"] is True
        assert resolved["reason"] == "protected_branch"

    def test_protected_branch_check_is_case_insensitive(self):
        assert resolve_checkpoint_branch("MAIN", "m4c-04")["redirected"] is True

    @pytest.mark.parametrize("branch", ["", None, "unknown", "HEAD"])
    def test_detached_or_unknown_head_redirects(self, branch):
        resolved = resolve_checkpoint_branch(branch, "m4c-04")
        assert resolved["branch"] == "wip/m4c-04"
        assert resolved["reason"] == "unresolved_branch"

    def test_task_id_is_slugified_into_the_branch_name(self):
        assert wip_branch_for("M4c.4 — never lose work!") == "wip/M4c.4-never-lose-work"
        assert wip_branch_for(None) == "wip/unknown-task"
        assert wip_branch_for("   ") == "wip/unknown-task"


# ---------------------------------------------------------------------------
# The commit path
# ---------------------------------------------------------------------------

class TestCheckpointCommit:
    def test_checkpoints_a_dirty_tree_and_reports_the_sha(self, events):
        git = FakeGit()
        result = checkpoint_wip(
            "/repo", task_id="m4c-04", stop_reason="sigterm",
            trigger="signal:SIGTERM", git_run=git,
        )

        assert result["checkpointed"] is True
        assert result["sha"] == "a" * 40
        assert result["short_sha"] == "a" * 12
        assert result["branch"] == "feature/m4c4/crash-safe"
        assert result["file_count"] == 2
        assert result["files"] == ["tools/state_self_healing.py", "tests/test_x.py"]
        assert git.ran("add", "-A")
        assert git.ran("commit")

    def test_commit_message_names_task_reason_and_timestamp(self):
        git = FakeGit()
        checkpoint_wip(
            "/repo", task_id="m4c-04", stop_reason="awaiting_resources",
            trigger="guard_stop", git_run=git,
        )
        message = git.args_for("commit")[2]
        subject = message.splitlines()[0]

        assert subject.startswith(WIP_SUBJECT_PREFIX)
        assert "m4c-04" in subject
        assert "awaiting_resources" in subject
        assert "T" in subject  # ISO-8601 timestamp
        assert "guard_stop" in message
        assert "tools/state_self_healing.py" in message

    def test_logs_the_checkpoint_event_with_sha_and_file_list(self, events):
        checkpoint_wip("/repo", task_id="m4c-04", trigger="guard_stop", git_run=FakeGit())

        payload = _payload(events, wc.CHECKPOINT_EVENT)
        assert payload["sha"] == "a" * 40
        assert payload["files"] == ["tools/state_self_healing.py", "tests/test_x.py"]
        assert payload["file_count"] == 2
        assert payload["recover_with"].startswith("git -C /repo checkout ")

    def test_add_is_anchored_at_the_repo_root(self):
        """`git add -A -- .` cannot stage anything above the repo."""
        git = FakeGit()
        checkpoint_wip("/repo", task_id="m4c-04", trigger="guard_stop", git_run=git)
        assert git.args_for("add") == ["add", "-A", "--", "."]

    def test_never_bypasses_commit_hooks(self):
        git = FakeGit()
        checkpoint_wip("/repo", task_id="m4c-04", trigger="guard_stop", git_run=git)
        assert all("--no-verify" not in args for args, _ in git.calls)

    def test_pushes_to_the_task_branch_without_forcing(self):
        git = FakeGit()
        result = checkpoint_wip("/repo", task_id="m4c-04", trigger="guard_stop", git_run=git)

        assert result["pushed"] is True
        assert git.args_for("push") == ["push", "-u", "origin", "feature/m4c4/crash-safe"]
        assert all(
            not any(a.startswith("--force") for a in args) for args, _ in git.calls
        )

    def test_no_push_when_there_is_no_remote(self):
        git = FakeGit(**{"remote": GitResult(success=False, output="no such remote")})
        result = checkpoint_wip("/repo", task_id="m4c-04", trigger="guard_stop", git_run=git)

        assert result["checkpointed"] is True
        assert result["pushed"] is False
        assert not git.ran("push")

    def test_push_disabled_still_commits(self):
        git = FakeGit()
        result = checkpoint_wip(
            "/repo", task_id="m4c-04", trigger="guard_stop", push=False, git_run=git,
        )
        assert result["checkpointed"] is True
        assert not git.ran("push")

    def test_a_failed_push_does_not_undo_the_commit(self, events):
        git = FakeGit(**{"push": GitResult(success=False, output="rejected: non-fast-forward")})
        result = checkpoint_wip("/repo", task_id="m4c-04", trigger="guard_stop", git_run=git)

        assert result["checkpointed"] is True
        assert result["pushed"] is False
        assert "non-fast-forward" in result["push_error"]


class TestCleanTree:
    def test_clean_tree_is_a_no_op(self, events):
        git = FakeGit(dirty=())
        result = checkpoint_wip("/repo", task_id="m4c-04", trigger="atexit", git_run=git)

        assert result["checkpointed"] is False
        assert result["reason"] == "clean_tree"
        assert result["sha"] == ""
        assert not git.ran("add")
        assert not git.ran("commit")
        assert not git.ran("push")
        assert _types(events) == [wc.CHECKPOINT_SKIPPED_EVENT]

    def test_only_ignored_files_dirty_is_not_a_failure(self, events):
        git = FakeGit(**{"commit": GitResult(success=False, output="nothing to commit, working tree clean")})
        result = checkpoint_wip("/repo", task_id="m4c-04", trigger="atexit", git_run=git)

        assert result["checkpointed"] is False
        assert result["reason"] == "nothing_to_commit"
        assert wc.CHECKPOINT_FAILED_EVENT not in _types(events)


class TestProtectedBranchRedirect:
    def test_checkpoint_on_main_lands_on_a_wip_branch(self, events):
        git = FakeGit(**{"branch": GitResult(success=True, output="main"),
                         "rev-parse --verify": GitResult(success=False, output="")})
        result = checkpoint_wip("/repo", task_id="m4c-04", trigger="guard_stop", git_run=git)

        assert result["checkpointed"] is True
        assert result["branch"] == "wip/m4c-04"
        assert result["redirected"] is True
        assert git.args_for("checkout") == ["checkout", "-b", "wip/m4c-04"]
        assert git.args_for("push") == ["push", "-u", "origin", "wip/m4c-04"]

    def test_existing_wip_branch_is_checked_out_not_recreated(self):
        git = FakeGit(**{"branch": GitResult(success=True, output="main"),
                         "rev-parse --verify": GitResult(success=True, output="b" * 40)})
        checkpoint_wip("/repo", task_id="m4c-04", trigger="guard_stop", git_run=git)

        assert git.args_for("checkout") == ["checkout", "wip/m4c-04"]

    def test_nothing_is_committed_when_the_redirect_fails(self, events):
        """Falling back to the current branch would commit to main — never."""
        git = FakeGit(**{
            "branch": GitResult(success=True, output="main"),
            "rev-parse --verify": GitResult(success=False, output=""),
            "checkout": GitResult(success=False, output="error: would overwrite local changes"),
        })
        result = checkpoint_wip("/repo", task_id="m4c-04", trigger="guard_stop", git_run=git)

        assert result["checkpointed"] is False
        assert result["reason"] == "redirect_failed"
        assert not git.ran("commit")
        assert wc.CHECKPOINT_FAILED_EVENT in _types(events)


# ---------------------------------------------------------------------------
# Failure must never block the exit
# ---------------------------------------------------------------------------

class TestFailureDoesNotBlockExit:
    @pytest.mark.parametrize("failing,expected_reason", [
        ("add", "add_failed"),
        ("commit", "commit_failed"),
    ])
    def test_git_failures_are_returned_not_raised(self, failing, expected_reason, events):
        git = FakeGit(**{failing: GitResult(success=False, output="fatal: disk full")})
        result = checkpoint_wip("/repo", task_id="m4c-04", trigger="atexit", git_run=git)

        assert result["checkpointed"] is False
        assert result["reason"] == expected_reason
        assert "disk full" in result["error"]

        failure = _payload(events, wc.CHECKPOINT_FAILED_EVENT)
        assert failure is not None, "a failed checkpoint must be loud"
        assert "still only in the working tree" in failure["message"]

    def test_an_exploding_git_never_escapes(self, events):
        def boom(args, cwd, timeout=120):
            raise RuntimeError("git binary vanished")

        result = checkpoint_wip("/repo", task_id="m4c-04", trigger="atexit", git_run=boom)

        assert result["checkpointed"] is False
        assert result["reason"] == "exception"
        assert "git binary vanished" in result["error"]
        assert wc.CHECKPOINT_FAILED_EVENT in _types(events)

    def test_missing_repo_path_is_reported_not_raised(self, events):
        result = checkpoint_wip("", task_id="m4c-04", trigger="atexit", git_run=FakeGit())
        assert result["reason"] == "no_repo_path"
        assert wc.CHECKPOINT_FAILED_EVENT in _types(events)

    def test_a_reentrant_call_does_not_start_a_second_commit(self, monkeypatch):
        monkeypatch.setattr(wc, "_in_progress", True)
        git = FakeGit()
        result = checkpoint_wip("/repo", task_id="m4c-04", trigger="atexit", git_run=git)

        assert result["reason"] == "already_in_progress"
        assert git.calls == []


# ---------------------------------------------------------------------------
# Startup detection
# ---------------------------------------------------------------------------

_LOG = (
    "cafe1234cafe1234cafe1234cafe1234cafe1234\x1fWIP checkpoint [m4c-03]: "
    "awaiting_resources @ 2026-08-04T09:12:00\x1f2026-08-04T09:12:00+00:00"
)


class TestStartupDetection:
    def test_finds_a_wip_commit_on_the_task_branch(self):
        git = FakeGit(**{
            "log": GitResult(success=True, output=_LOG),
            "show": GitResult(success=True, output="tools/state_self_healing.py\ntests/test_state_self_healing.py\n"),
        })
        found = detect_wip_checkpoint("/repo", "feature/m4c3/self-healing", git_run=git)

        assert found["found"] is True
        assert found["sha"].startswith("cafe1234")
        assert found["short_sha"] == "cafe1234cafe"
        assert found["committed_at"] == "2026-08-04T09:12:00+00:00"
        assert found["files"] == [
            "tools/state_self_healing.py", "tests/test_state_self_healing.py",
        ]
        assert found["commits_since"] == 0

    def test_reports_how_many_commits_sit_on_top(self):
        ordinary = "1111111111111111111111111111111111111111\x1fAdd retry backoff\x1f2026-08-05T10:00:00+00:00"
        git = FakeGit(**{"log": GitResult(success=True, output=f"{ordinary}\n{_LOG}")})
        found = detect_wip_checkpoint("/repo", "feature/x", git_run=git)

        assert found["found"] is True
        assert found["commits_since"] == 1

    def test_no_wip_commit_is_not_found(self):
        git = FakeGit(**{"log": GitResult(
            success=True,
            output="1111111111111111111111111111111111111111\x1fAdd retry backoff\x1f2026-08-05T10:00:00+00:00",
        )})
        assert detect_wip_checkpoint("/repo", "feature/x", git_run=git)["found"] is False

    @pytest.mark.parametrize("branch", [None, ""])
    def test_no_branch_is_not_found(self, branch):
        assert detect_wip_checkpoint("/repo", branch, git_run=FakeGit())["found"] is False

    def test_a_missing_branch_reads_as_not_found(self):
        git = FakeGit(**{"log": GitResult(success=False, output="unknown revision")})
        assert detect_wip_checkpoint("/repo", "feature/gone", git_run=git)["found"] is False

    def test_detection_never_raises(self):
        def boom(args, cwd, timeout=120):
            raise RuntimeError("git exploded")

        assert detect_wip_checkpoint("/repo", "feature/x", git_run=boom)["found"] is False


class TestPromptNotice:
    def test_notice_tells_the_worker_to_continue_not_restart(self):
        git = FakeGit(**{
            "log": GitResult(success=True, output=_LOG),
            "show": GitResult(success=True, output="tools/state_self_healing.py\n"),
        })
        notice = format_wip_prompt_notice(
            detect_wip_checkpoint("/repo", "feature/m4c3/self-healing", git_run=git)
        )

        assert "CONTINUE IT, DO NOT RESTART" in notice
        assert "cafe1234cafe" in notice
        assert "feature/m4c3/self-healing" in notice
        assert "tools/state_self_healing.py" in notice

    def test_no_notice_when_nothing_was_checkpointed(self):
        assert format_wip_prompt_notice({"found": False}) == ""
        assert format_wip_prompt_notice({}) == ""
        assert format_wip_prompt_notice(None) == ""


# ---------------------------------------------------------------------------
# Exit-path handlers
# ---------------------------------------------------------------------------

class FakeSignal:
    SIGINT = 2
    SIGTERM = 15

    def __init__(self):
        self.handlers = {}

    def signal(self, signum, handler):
        self.handlers[signum] = handler


class Recorder:
    """Stands in for checkpoint_wip and records how it was invoked."""

    def __init__(self):
        self.calls = []

    def __call__(self, repo_path, **kwargs):
        self.calls.append({"repo_path": repo_path, **kwargs})
        return {"checkpointed": True, "sha": "a" * 40, "reason": "committed"}


def _install(context, checkpoint=None, **kwargs):
    sig, hooks = FakeSignal(), []
    checkpoint = checkpoint or Recorder()
    installed = install_checkpoint_handlers(
        context if callable(context) else (lambda: context),
        checkpoint=checkpoint,
        signal_module=sig,
        atexit_register=hooks.append,
        exit_fn=lambda code: None,
        **kwargs,
    )
    return installed, sig, hooks, checkpoint


class TestExitHandlers:
    def test_sigterm_checkpoints_before_exiting(self):
        ctx = CheckpointContext(repo_path="/repo", task_id="m4c-04")
        _, sig, _, recorder = _install(ctx)

        sig.handlers[FakeSignal.SIGTERM](FakeSignal.SIGTERM, None)

        assert len(recorder.calls) == 1
        call = recorder.calls[0]
        assert call["repo_path"] == "/repo"
        assert call["task_id"] == "m4c-04"
        assert call["trigger"] == "signal:SIGTERM"
        assert call["stop_reason"] == "sigterm"

    def test_sigterm_still_exits_after_checkpointing(self):
        exits = []
        sig, hooks = FakeSignal(), []
        install_checkpoint_handlers(
            lambda: CheckpointContext(repo_path="/repo"),
            checkpoint=Recorder(),
            signal_module=sig,
            atexit_register=hooks.append,
            exit_fn=exits.append,
        )
        sig.handlers[FakeSignal.SIGTERM](FakeSignal.SIGTERM, None)

        assert exits == [128 + 15]

    def test_sigint_still_raises_keyboardinterrupt(self):
        _, sig, _, recorder = _install(CheckpointContext(repo_path="/repo", task_id="m4c-04"))

        with pytest.raises(KeyboardInterrupt):
            sig.handlers[FakeSignal.SIGINT](FakeSignal.SIGINT, None)

        assert recorder.calls[0]["trigger"] == "signal:SIGINT"

    def test_atexit_hook_covers_unhandled_exceptions_and_plain_returns(self):
        _, _, hooks, recorder = _install(CheckpointContext(repo_path="/repo", task_id="m4c-04"))

        assert len(hooks) == 1
        hooks[0]()

        assert recorder.calls[0]["trigger"] == "atexit"

    def test_context_is_read_at_exit_time_not_install_time(self):
        """The task in flight when the signal lands is the one to checkpoint."""
        live = {"task_id": "task-1"}
        _, sig, _, recorder = _install(
            lambda: CheckpointContext(repo_path="/repo", task_id=live["task_id"])
        )

        live["task_id"] = "task-9"
        sig.handlers[FakeSignal.SIGTERM](FakeSignal.SIGTERM, None)

        assert recorder.calls[0]["task_id"] == "task-9"

    def test_guard_stop_reason_reaches_the_checkpoint(self):
        _, _, hooks, recorder = _install(
            CheckpointContext(repo_path="/repo", task_id="m4c-04", stop_reason="awaiting_resources")
        )
        hooks[0]()

        assert recorder.calls[0]["stop_reason"] == "awaiting_resources"

    def test_a_broken_context_provider_does_not_block_the_exit(self, events):
        def boom():
            raise RuntimeError("state file corrupt")

        recorder = Recorder()
        _, _, hooks, _ = _install(boom, checkpoint=recorder)
        hooks[0]()  # must not raise

        assert recorder.calls == []
        assert wc.CHECKPOINT_FAILED_EVENT in _types(events)

    def test_a_failing_checkpoint_does_not_block_the_exit(self):
        def failing(repo_path, **kwargs):
            return {"checkpointed": False, "reason": "commit_failed", "error": "hook rejected"}

        _, sig, hooks, _ = _install(CheckpointContext(repo_path="/repo"), checkpoint=failing)

        hooks[0]()  # atexit: returns normally
        with pytest.raises(KeyboardInterrupt):
            sig.handlers[FakeSignal.SIGINT](FakeSignal.SIGINT, None)

    def test_handlers_install_once(self):
        installed, _, _, _ = _install(CheckpointContext(repo_path="/repo"))
        assert installed["signals"] == ["SIGINT", "SIGTERM"]
        assert installed["atexit"] is True

        again, _, hooks, _ = _install(CheckpointContext(repo_path="/repo"))
        assert again["already_installed"] is True
        assert hooks == []

    def test_a_platform_without_signals_still_gets_the_atexit_hook(self):
        class NoSignals:
            pass

        hooks = []
        installed = install_checkpoint_handlers(
            lambda: CheckpointContext(repo_path="/repo"),
            checkpoint=Recorder(),
            signal_module=NoSignals(),
            atexit_register=hooks.append,
        )
        assert installed["signals"] == []
        assert len(hooks) == 1

    def test_context_accepts_a_plain_dict(self):
        _, _, hooks, recorder = _install({"repo_path": "/repo", "task_id": "m4c-04"})
        hooks[0]()
        assert recorder.calls[0]["task_id"] == "m4c-04"


# ---------------------------------------------------------------------------
# Message formatting
# ---------------------------------------------------------------------------

class TestMessageFormatting:
    def test_message_is_unmistakably_unfinished_work(self):
        message = format_checkpoint_message(
            task_id="m4c-04", stop_reason="stale_run", trigger="signal:SIGTERM",
            branch="feature/x", files=["a.py"], timestamp="2026-08-06T12:00:00",
        )
        assert message.startswith(f"{WIP_SUBJECT_PREFIX} [m4c-04]: stale_run @ 2026-08-06T12:00:00")
        assert "UNFINISHED" in message
        assert "do not" in message.lower()

    def test_a_huge_file_list_is_capped_but_counted(self):
        files = [f"src/file_{i}.py" for i in range(200)]
        message = format_checkpoint_message(
            task_id="m4c-04", stop_reason=None, trigger="atexit",
            branch="feature/x", files=files,
        )
        assert f"Files       : {len(files)}" in message
        assert f"... and {200 - wc.MAX_LISTED_FILES} more" in message

    def test_missing_task_and_reason_still_produce_a_usable_subject(self):
        subject = format_checkpoint_message(
            task_id=None, stop_reason=None, trigger="atexit", branch="feature/x", files=["a.py"],
        ).splitlines()[0]
        assert subject.startswith(f"{WIP_SUBJECT_PREFIX} [no-task]: atexit @ ")


# ---------------------------------------------------------------------------
# Wiring — the guard-stop path, the worker prompt, the stop report
# ---------------------------------------------------------------------------

class TestGuardStopWiring:
    """(b) a guard setting a stop reason checkpoints before the loop unwinds."""

    def _stopped_state(self, monkeypatch, **overrides):
        import graph as graph_module
        from state import RunnerState

        monkeypatch.setattr(graph_module, "log_event", lambda *a, **k: None)
        monkeypatch.setattr(graph_module, "update_state", lambda *a, **k: None)
        monkeypatch.setattr(graph_module.cfg, "wip_checkpoint_enabled", True)

        calls = []

        def fake_checkpoint(repo_path, **kwargs):
            calls.append({"repo_path": repo_path, **kwargs})
            return {"checkpointed": True, "sha": "f" * 40, "short_sha": "f" * 12,
                    "reason": "committed", "file_count": 3, "files": ["a.py"],
                    "branch": "feature/x", "pushed": True}

        monkeypatch.setattr(graph_module, "checkpoint_wip", fake_checkpoint)

        state = RunnerState(**{"current_task_id": "m4c-04", **overrides})
        return graph_module, state, calls

    def test_a_guard_stop_reason_checkpoints_the_tree(self, monkeypatch):
        graph_module, state, calls = self._stopped_state(
            monkeypatch, stop_reason="awaiting_resources",
        )
        out = graph_module.decide_continue_or_stop(state)

        assert len(calls) == 1
        assert calls[0]["task_id"] == "m4c-04"
        assert calls[0]["stop_reason"] == "awaiting_resources"
        assert calls[0]["trigger"] == "guard_stop"
        assert out.wip_checkpoint["sha"] == "f" * 40

    def test_a_budget_stop_checkpoints_too(self, monkeypatch):
        graph_module, state, calls = self._stopped_state(monkeypatch, loop_count=999)
        out = graph_module.decide_continue_or_stop(state)

        assert out.stop_reason == "max_loop_tasks"
        assert calls[0]["stop_reason"] == "max_loop_tasks"

    def test_a_continuing_loop_does_not_checkpoint(self, monkeypatch):
        graph_module, state, calls = self._stopped_state(monkeypatch, loop_count=0)
        out = graph_module.decide_continue_or_stop(state)

        assert out.status == "running"
        assert calls == []

    def test_the_checkpoint_can_be_switched_off(self, monkeypatch):
        graph_module, state, calls = self._stopped_state(
            monkeypatch, stop_reason="awaiting_resources",
        )
        monkeypatch.setattr(graph_module.cfg, "wip_checkpoint_enabled", False)
        graph_module.decide_continue_or_stop(state)

        assert calls == []


class TestPromptWiring:
    """(d) a resumed task is told the partial work exists."""

    def test_worker_prompt_leads_with_the_wip_notice(self, monkeypatch):
        import graph as graph_module
        from state import RunnerState

        monkeypatch.setattr(graph_module, "log_event", lambda *a, **k: None)
        monkeypatch.setattr(graph_module, "update_state", lambda *a, **k: None)
        monkeypatch.setattr(graph_module.cfg, "wip_checkpoint_enabled", True)
        monkeypatch.setattr(graph_module, "detect_wip_checkpoint", lambda repo, branch: {
            "found": True, "branch": branch, "sha": "c" * 40, "short_sha": "c" * 12,
            "subject": f"{WIP_SUBJECT_PREFIX} [m4c-03]: awaiting_resources @ 2026-08-04T09:12:00",
            "committed_at": "2026-08-04T09:12:00+00:00",
            "files": ["tools/state_self_healing.py"], "commits_since": 0,
        })

        state = RunnerState(
            current_task_id="m4c-03",
            current_task={"id": "m4c-03", "title": "Self-healing", "branch": "feature/m4c3/self-healing"},
        )
        out = graph_module.generate_worker_prompt(state)
        prompt = out.messages[-1]["content"]

        assert prompt.startswith("PARTIAL WORK ALREADY EXISTS")
        assert "tools/state_self_healing.py" in prompt
        assert "Task: Self-healing" in prompt

    def test_prompt_is_unchanged_when_no_checkpoint_exists(self, monkeypatch):
        import graph as graph_module
        from state import RunnerState

        monkeypatch.setattr(graph_module, "log_event", lambda *a, **k: None)
        monkeypatch.setattr(graph_module, "update_state", lambda *a, **k: None)
        monkeypatch.setattr(graph_module, "detect_wip_checkpoint", lambda repo, branch: {"found": False})

        state = RunnerState(
            current_task_id="m4c-04",
            current_task={"id": "m4c-04", "title": "Checkpointing", "branch": "feature/m4c4/x"},
        )
        prompt = graph_module.generate_worker_prompt(state).messages[-1]["content"]

        assert "PARTIAL WORK" not in prompt
        assert prompt.startswith("You are working inside the bucks.ai repo")

    def test_a_detection_failure_never_blocks_dispatch(self, monkeypatch):
        import graph as graph_module
        from state import RunnerState

        monkeypatch.setattr(graph_module, "log_event", lambda *a, **k: None)
        monkeypatch.setattr(graph_module, "update_state", lambda *a, **k: None)

        def boom(repo, branch):
            raise RuntimeError("git exploded")

        monkeypatch.setattr(graph_module, "detect_wip_checkpoint", boom)
        state = RunnerState(
            current_task_id="m4c-04",
            current_task={"id": "m4c-04", "title": "Checkpointing", "branch": "feature/m4c4/x"},
        )
        assert graph_module.generate_worker_prompt(state).messages[-1]["content"]


class TestStopReportWiring:
    """(c) the sha reaches the founder in the report they actually read."""

    def _diagnostics(self, checkpoint):
        from tools.stop_diagnostics import build_stop_diagnostics

        return build_stop_diagnostics(
            stop_reason="awaiting_resources",
            session_state={"loop_count": 1, "wip_checkpoint": checkpoint},
            config_report={},
            events=[],
        )

    def test_report_quotes_the_sha_and_the_recovery_command(self):
        diagnostics = self._diagnostics({
            "checkpointed": True, "reason": "committed", "sha": "d" * 40,
            "short_sha": "d" * 12, "branch": "wip/m4c-04", "redirected": True,
            "pushed": True, "file_count": 2, "files": ["a.py", "b.py"],
        })

        assert "d" * 12 in diagnostics["report"]
        assert f"Recover with : git checkout {'d' * 12}" in diagnostics["report"]
        assert "redirected off a protected branch" in diagnostics["report"]
        assert "a.py" in diagnostics["report"]
        assert "d" * 12 in diagnostics["slack_message"]

    def test_report_says_so_when_the_tree_was_clean(self):
        diagnostics = self._diagnostics({"checkpointed": False, "reason": "clean_tree"})

        assert "Working tree was clean" in diagnostics["report"]
        assert "WIP checkpointed" not in diagnostics["slack_message"]

    def test_a_failed_checkpoint_shouts_in_both_channels(self):
        diagnostics = self._diagnostics({
            "checkpointed": False, "reason": "commit_failed",
            "error": "pre-commit hook rejected", "file_count": 11, "files": [],
        })

        assert "CHECKPOINT FAILED" in diagnostics["report"]
        assert "STILL ONLY IN THE WORKING TREE" in diagnostics["report"]
        assert "WIP checkpoint FAILED" in diagnostics["slack_message"]

    def test_no_section_when_no_checkpoint_ran(self):
        diagnostics = self._diagnostics(None)
        assert "UNCOMMITTED WORK AT THE STOP" not in diagnostics["report"]


class TestConfig:
    def test_defaults_are_on(self):
        from config import RunnerConfig

        cfg = RunnerConfig()
        assert cfg.wip_checkpoint_enabled is True
        assert cfg.wip_checkpoint_push is True
        assert "wip_checkpoint_enabled" in cfg.report()
        assert "wip_checkpoint_push" in cfg.report()

    def test_env_vars_are_documented_in_the_readme(self):
        """CLAUDE.md's three-place rule: config.py, the README env table, a test."""
        readme = os.path.join(os.path.dirname(__file__), "..", "README.md")
        with open(readme, encoding="utf-8") as fh:
            text = fh.read()
        for var in ("WIP_CHECKPOINT", "WIP_CHECKPOINT_PUSH"):
            assert f"`{var}`" in text, f"{var} is missing from the README env table"

    def test_a_failed_checkpoint_reaches_a_human(self):
        import config as config_module

        assert wc.CHECKPOINT_FAILED_EVENT in config_module._DEFAULT_SLACK_EVENTS
