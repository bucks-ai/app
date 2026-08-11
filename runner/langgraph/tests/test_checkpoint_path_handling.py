"""Tests for M4c.4: path-string correctness and targeted-add-failure logging.

Covers:
- _to_repo_relative round-trip correctness (completion_evidence and definition_of_done)
- Regression against lstrip-charset truncation
- wip_checkpoint logs an error when targeted git add fails (even when fallback succeeds)
- worktree_files: run_command.strip() strips the leading space of the first porcelain
  line, causing index 0 of the path list to lose its first character — fixed with
  separator-position detection instead of a fixed line[3:] offset.
- All four consumers of the checkpoint file list (wip_checkpointed event, commit
  message body, stop-report, git-add pathspecs) receive the uncorrupted list.
- Targeted git add succeeds against a real temp repo (not a mock) so we can't
  ship a "fix" that only works with mocked git but fails against real pathspecs.

All git calls in the wip_checkpoint tests are mocked — no real repository
operations except for the one integration test that is explicitly labelled.
"""
import os
import subprocess
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from tools.completion_evidence import _to_repo_relative as ce_to_repo_relative
from tools.definition_of_done import _to_repo_relative as dod_to_repo_relative
import tools.wip_checkpoint as wc
from tools.git_autonomy import GitResult, worktree_files
from tools.wip_checkpoint import checkpoint_wip


# ---------------------------------------------------------------------------
# _to_repo_relative — shared helper (tested for both modules)
# ---------------------------------------------------------------------------

REPO_ROOT = "/home/arnav/bucks-ai"

@pytest.mark.parametrize("fn", [ce_to_repo_relative, dod_to_repo_relative])
class TestToRepoRelative:
    def test_repo_relative_with_directory_prefix_unchanged(self, fn):
        """runner/foo.py is already repo-relative and must survive the helper unmodified."""
        assert fn("runner/langgraph/tools/foo.py", REPO_ROOT) == "runner/langgraph/tools/foo.py"

    def test_absolute_path_under_repo_root_converted(self, fn):
        """Absolute path rooted at repo root → correct repo-relative path."""
        assert fn(f"{REPO_ROOT}/runner/langgraph/tools/foo.py", REPO_ROOT) == "runner/langgraph/tools/foo.py"

    def test_lstrip_charset_regression(self, fn):
        """Regression: lstrip('/home/arnav/bucks-ai/') eats leading chars that appear in the charset.

        'r' is in {h,o,m,e,a,r,n,v,b,u,c,k,s,-,i,/} so lstrip would turn
        'runner/x.py' into 'unner/x.py'. startswith-based logic must not do this.
        """
        result = fn("runner/x.py", REPO_ROOT)
        assert result == "runner/x.py", (
            f"lstrip charset regression: got {result!r}, expected 'runner/x.py'. "
            f"Check that repo root is stripped with startswith, not lstrip."
        )

    def test_top_level_file_unaffected(self, fn):
        """A bare filename with no directory prefix passes through unchanged."""
        assert fn("README.md", REPO_ROOT) == "README.md"

    def test_backtick_wrapping_stripped(self, fn):
        """`runner/foo.py` (backtick-wrapped) → runner/foo.py."""
        assert fn("`runner/langgraph/tools/foo.py`", REPO_ROOT) == "runner/langgraph/tools/foo.py"

    def test_dot_slash_prefix_stripped(self, fn):
        """./runner/foo.py → runner/foo.py."""
        assert fn("./runner/foo.py", REPO_ROOT) == "runner/foo.py"

    def test_absolute_not_under_repo_root_stripped_of_leading_slash(self, fn):
        """/etc/other/file.py is not under repo root — leading slash is stripped."""
        result = fn("/etc/other/file.py", REPO_ROOT)
        assert result == "etc/other/file.py"


# ---------------------------------------------------------------------------
# worktree_files — run_command.strip() truncation bug
#
# git status --porcelain output starts with " M path" when the first file is
# modified but not staged.  run_command calls output.strip(), which strips the
# leading space.  The first line becomes "M path", and the original line[3:]
# offset then starts at index 3 ("u") instead of the path start at index 2
# ("r"), dropping the leading "r" from "runner/…" or "t" from "tools/…".
#
# Only index 0 is affected because output.strip() only eats leading chars of
# the ENTIRE output string — all subsequent lines retain their leading space.
# ---------------------------------------------------------------------------

class _StrippedPortcelainGit:
    """Mock git_run that returns porcelain output AFTER run_command's .strip().

    This is the critical difference from FakeGit in test_wip_checkpoint.py,
    which returns porcelain WITHOUT stripping. The prior mocks passed because
    they never exercised the path that run_command takes in production.
    """

    def __init__(self, dirty):
        self.dirty = list(dirty)
        self.calls = []
        self._add_count = 0

    def __call__(self, args, cwd, timeout=120):
        args = list(args)
        self.calls.append((tuple(args), cwd))
        key = args[0]
        if key == "status":
            # Simulate run_command's output.strip(): the leading space of the
            # first " M path" line is eaten by strip().
            raw = "\n".join(f" M {p}" for p in self.dirty)
            return GitResult(success=True, output=raw.strip(), args=tuple(args))
        if key == "add":
            self._add_count += 1
            return GitResult(success=True, output="", args=tuple(args))
        defaults = {
            "branch": GitResult(success=True, output="feature/m4c4/test"),
            "rev-parse": GitResult(success=True, output="a" * 40),
            "commit": GitResult(success=True, output="[feature 1234567] WIP"),
            "remote": GitResult(success=True, output="git@github.com:bucks-ai/bucks-ai.git"),
            "push": GitResult(success=True, output=""),
            "checkout": GitResult(success=True, output=""),
            "log": GitResult(success=True, output=""),
            "show": GitResult(success=True, output=""),
        }
        return defaults.get(key, GitResult(success=True, output=""))

    def add_pathspecs(self):
        """Return the pathspecs passed to the targeted git add -- call."""
        for args, _ in self.calls:
            a = list(args)
            if a[0] == "add" and "--" in a and "." not in a:
                idx = a.index("--")
                return a[idx + 1:]
        return []


@pytest.fixture(autouse=True)
def _reset_module_state():
    wc.reset_handlers_for_tests()
    yield
    wc.reset_handlers_for_tests()


class TestWorktreeFilesStripRegression:
    """Regression suite: index 0 of the worktree_files list must survive
    run_command's output.strip() with its first character intact."""

    def _make_git(self, dirty):
        return _StrippedPortcelainGit(dirty)

    def test_single_path_round_trips_byte_identical(self):
        paths = ["runner/langgraph/tools/auto_repair_loop.py"]
        result = worktree_files("/repo", git_run=self._make_git(paths))
        assert result == paths, (
            f"1-element round-trip failed: got {result!r}, expected {paths!r}\n"
            "index 0 first char was likely stripped by output.strip() in run_command."
        )

    def test_two_path_list_index_zero_intact(self):
        """Reproduction of the test-fixture evidence: ['ools/x.py', 'NOTES.md']."""
        paths = ["tools/x.py", "NOTES.md"]
        result = worktree_files("/repo", git_run=self._make_git(paths))
        assert result == paths, (
            f"2-element round-trip failed: got {result!r}, expected {paths!r}\n"
            "expected 'tools/x.py' at index 0, leading 't' was stripped."
        )

    def test_six_path_list_index_zero_intact_others_unchanged(self):
        """Reproduction of the 2026-08-11 production incident."""
        paths = [
            "runner/langgraph/README.md",
            "runner/langgraph/config.py",
            "runner/langgraph/graph.py",
            "runner/langgraph/state.py",
            "runner/langgraph/tests/test_mission_briefing.py",
            "runner/langgraph/tools/mission_briefing.py",
        ]
        result = worktree_files("/repo", git_run=self._make_git(paths))
        assert result == paths, (
            f"6-element round-trip failed:\n  got      {result!r}\n  expected {paths!r}\n"
            f"index 0: expected {paths[0]!r}, got {result[0] if result else '(empty)'!r}"
        )
        # Verify indices 1-5 were NEVER affected (the bug was index-0-only)
        for i in range(1, len(paths)):
            assert result[i] == paths[i], f"index {i} should not be affected; got {result[i]!r}"

    def test_runner_prefix_not_truncated_to_unner(self):
        """Direct regression: 'runner/...' must not become 'unner/...'."""
        paths = ["runner/langgraph/tools/auto_repair_loop.py"]
        result = worktree_files("/repo", git_run=self._make_git(paths))
        assert result[0].startswith("runner/"), (
            f"'runner/' prefix was truncated: got {result[0]!r}. "
            "This is the exact production failure from 2026-08-07."
        )

    def test_tools_prefix_not_truncated_to_ools(self):
        """Direct regression: 'tools/...' must not become 'ools/...'."""
        paths = ["tools/some_module.py"]
        result = worktree_files("/repo", git_run=self._make_git(paths))
        assert result[0] == "tools/some_module.py", (
            f"'tools/' prefix was truncated: got {result[0]!r}. "
            "Leading 't' was stripped by the run_command.strip() bug."
        )


# ---------------------------------------------------------------------------
# Four-consumer test: all downstream consumers receive the uncorrupted list
# ---------------------------------------------------------------------------

class TestFourConsumersReceiveUncorruptedList:
    """Consumer 1: wip_checkpointed event payload (files list in PostHog/Slack).
    Consumer 2: checkpoint commit message body (files listed under 'Files :').
    Consumer 3: result["files"] — what stop_diagnostics reads for the report.
    Consumer 4: git add pathspecs — the targeted git add -- <paths> call.

    All four read from the same list returned by worktree_files(); a single fix
    there propagates to all of them.
    """

    PATHS = [
        "runner/langgraph/README.md",
        "runner/langgraph/config.py",
        "runner/langgraph/graph.py",
        "runner/langgraph/state.py",
        "runner/langgraph/tests/test_mission_briefing.py",
        "runner/langgraph/tools/mission_briefing.py",
    ]

    def _run_checkpoint(self, monkeypatch, tmp_path):
        recorded = []
        monkeypatch.setattr(wc, "log_event", lambda t, p, task_id=None: recorded.append((t, p)))
        fake_git = _StrippedPortcelainGit(dirty=self.PATHS)
        result = checkpoint_wip(
            str(tmp_path),
            task_id="m4c4-refix",
            trigger="test",
            push=False,
            git_run=fake_git,
        )
        return result, fake_git, recorded

    def test_consumer1_event_payload_files_index_zero(self, monkeypatch, tmp_path):
        """wip_checkpointed event payload must have the uncorrupted file list."""
        result, _, recorded = self._run_checkpoint(monkeypatch, tmp_path)
        events = [(t, p) for t, p in recorded if t == wc.CHECKPOINT_EVENT]
        assert events, f"wip_checkpointed event not found; got {[t for t, _ in recorded]}"
        files = events[0][1].get("files", [])
        assert files[0] == self.PATHS[0], (
            f"Consumer 1 (event payload): index 0 = {files[0]!r}, expected {self.PATHS[0]!r}"
        )

    def test_consumer2_commit_message_contains_correct_first_path(self, monkeypatch, tmp_path):
        """Commit message body must list the uncorrupted first path."""
        result, fake_git, _ = self._run_checkpoint(monkeypatch, tmp_path)
        commit_calls = [list(a) for a, _ in fake_git.calls if a[0] == "commit"]
        assert commit_calls, "no commit call was made"
        msg_idx = commit_calls[0].index("-m") + 1
        commit_msg = commit_calls[0][msg_idx]
        assert self.PATHS[0] in commit_msg, (
            f"Consumer 2 (commit message): {self.PATHS[0]!r} not found in commit message body"
        )

    def test_consumer3_result_files_index_zero(self, monkeypatch, tmp_path):
        """result['files'] (what stop_diagnostics reads) must have the correct index 0."""
        result, _, _ = self._run_checkpoint(monkeypatch, tmp_path)
        files = result.get("files", [])
        assert files[0] == self.PATHS[0], (
            f"Consumer 3 (result files / stop report): index 0 = {files[0]!r}, "
            f"expected {self.PATHS[0]!r}"
        )

    def test_consumer4_git_add_pathspecs_index_zero(self, monkeypatch, tmp_path):
        """The targeted git add -- <paths> must include the correct first path."""
        result, fake_git, _ = self._run_checkpoint(monkeypatch, tmp_path)
        pathspecs = fake_git.add_pathspecs()
        assert pathspecs, "no targeted git add call found"
        assert pathspecs[0] == self.PATHS[0], (
            f"Consumer 4 (git add pathspecs): index 0 = {pathspecs[0]!r}, "
            f"expected {self.PATHS[0]!r}"
        )


# ---------------------------------------------------------------------------
# Integration test: targeted git add against a real temp repo
#
# This test does NOT mock git. It creates an actual git repo, creates files
# whose names start with characters that appear in the repo path (exercising
# the strip() bug path), calls worktree_files() with real git, and then runs
# a real "git add -- <paths>" to confirm the paths are valid pathspecs.
#
# This is the test that would have caught m4c4-07's miss: the mock tests
# passed because mocks bypassed run_command.strip(). This test cannot pass
# on mocked git — it runs against a real subprocess.
# ---------------------------------------------------------------------------

@pytest.mark.integration
class TestTargetedGitAddRealRepo:

    def _init_repo(self, path, files: dict):
        """Create a git repo with an initial commit containing the given files.

        files: {relative_path: content} — all files are committed in one shot
        so subsequent modifications show up as " M path" in git status
        (the exact format that triggers the run_command.strip() bug).
        """
        for cmd in [
            ["git", "init"],
            ["git", "config", "user.email", "ci@test"],
            ["git", "config", "user.name", "CI"],
        ]:
            subprocess.run(cmd, cwd=path, check=True, capture_output=True)
        for rel, content in files.items():
            dest = path / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_text(content)
        subprocess.run(["git", "add", "-A"], cwd=path, check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "init"], cwd=path, check=True, capture_output=True)

    def test_worktree_files_produces_valid_pathspecs(self, tmp_path):
        """worktree_files must return paths that git add can actually use.

        Files are committed first and then MODIFIED so they show up as " M path"
        in git status --porcelain — the exact format where run_command.strip()
        eats the leading space and causes line[3:] to drop the first char.

        Uses 'runner/' and 'tools/' prefixes because 'r' and 't' are the
        chars lost by the bug on the first porcelain line.
        """
        initial = {
            "runner/langgraph/README.md": "v1",
            "tools/helper.py": "# v1",
        }
        self._init_repo(tmp_path, initial)

        # Modify both files — they will now appear as " M path" in porcelain
        (tmp_path / "runner" / "langgraph" / "README.md").write_text("v2")
        (tmp_path / "tools" / "helper.py").write_text("# v2")

        dirty = worktree_files(str(tmp_path))

        assert len(dirty) == 2, f"expected 2 dirty files, got {dirty!r}"
        assert "runner/langgraph/README.md" in dirty, (
            f"'runner/langgraph/README.md' missing or corrupted in {dirty!r}; "
            "the leading 'r' may have been stripped by run_command.strip()."
        )
        assert "tools/helper.py" in dirty, (
            f"'tools/helper.py' missing or corrupted in {dirty!r}; "
            "the leading 't' may have been stripped."
        )

        # The critical assertion: git add with these paths must SUCCEED.
        # If the paths are corrupted (e.g. 'unner/…'), git returns
        # returncode=128 with "fatal: pathspec did not match any files".
        add_result = subprocess.run(
            ["git", "add", "-A", "--"] + dirty,
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
        )
        assert add_result.returncode == 0, (
            f"git add failed — paths from worktree_files are invalid pathspecs:\n"
            f"  paths: {dirty!r}\n"
            f"  stderr: {add_result.stderr.strip()}\n"
            "This is the exact failure the targeted-add fallback has been hiding."
        )

    def test_single_runner_file_at_index_zero_real_git(self, tmp_path):
        """Regression: single 'runner/…' file, index 0, real git, targeted add succeeds."""
        self._init_repo(tmp_path, {"runner/state.py": "# v1"})
        (tmp_path / "runner" / "state.py").write_text("# v2")

        dirty = worktree_files(str(tmp_path))
        assert len(dirty) == 1
        assert dirty[0] == "runner/state.py", (
            f"Expected 'runner/state.py', got {dirty[0]!r}. "
            "Leading 'r' stripped by run_command.strip() bug."
        )
        add_result = subprocess.run(
            ["git", "add", "-A", "--"] + dirty,
            cwd=str(tmp_path),
            capture_output=True,
            text=True,
        )
        assert add_result.returncode == 0, (
            f"git add failed for {dirty!r}: {add_result.stderr.strip()}"
        )


# ---------------------------------------------------------------------------
# wip_checkpoint — targeted git add failure must be logged at error level
# ---------------------------------------------------------------------------

class FailFirstAddGit:
    """FakeGit whose first `add` call fails; subsequent adds and everything else succeed."""

    def __init__(self, dirty):
        self.calls = []
        self.dirty = list(dirty)
        self._add_count = 0

    def __call__(self, args, cwd, timeout=120):
        args = list(args)
        self.calls.append((tuple(args), cwd))
        key = args[0]
        if key == "status":
            porcelain = "\n".join(f" M {p}" for p in self.dirty)
            return GitResult(success=True, output=porcelain, args=tuple(args))
        if key == "add":
            self._add_count += 1
            if self._add_count == 1:
                return GitResult(
                    success=False,
                    output="fatal: pathspec 'unner/foo.py' did not match any files",
                    args=tuple(args),
                )
            return GitResult(success=True, output="", args=tuple(args))
        defaults = {
            "branch": GitResult(success=True, output="feature/m4c4/test"),
            "rev-parse": GitResult(success=True, output="a" * 40),
            "commit": GitResult(success=True, output="[feature 1234567] WIP"),
            "remote": GitResult(success=True, output="git@github.com:bucks-ai/bucks-ai.git"),
            "push": GitResult(success=True, output=""),
            "checkout": GitResult(success=True, output=""),
            "log": GitResult(success=True, output=""),
            "show": GitResult(success=True, output=""),
        }
        return defaults.get(key, GitResult(success=True, output=""))

    def ran(self, *tokens):
        return any(tuple(a[: len(tokens)]) == tokens for a, _ in self.calls)


def test_targeted_add_failure_logged_even_when_fallback_succeeds(monkeypatch, tmp_path):
    """When targeted git add fails, an error event is logged even if the fallback succeeds.

    This is the logging requirement from M4c.4: a targeted-add failure using paths
    the runner itself generated is an internal inconsistency and must not be silently
    swallowed by a successful fallback.
    """
    recorded = []
    monkeypatch.setattr(wc, "log_event", lambda t, p, task_id=None: recorded.append((t, p)))

    fake_git = FailFirstAddGit(dirty=["runner/foo.py"])
    result = checkpoint_wip(
        str(tmp_path),
        task_id="m4c4-test",
        trigger="test",
        push=False,
        git_run=fake_git,
    )

    error_events = [t for t, _ in recorded if t == "wip_checkpoint_add_targeted_failed"]
    assert error_events, (
        f"Expected 'wip_checkpoint_add_targeted_failed' event but got events: {[t for t, _ in recorded]}"
    )

    # Fallback add was attempted (second add call)
    assert fake_git._add_count == 2, (
        f"Expected 2 add calls (targeted then fallback), got {fake_git._add_count}"
    )

    # Overall checkpoint should succeed (fallback worked)
    assert result.get("reason") not in ("add_failed", "exception"), (
        f"Checkpoint should succeed via fallback; got reason={result.get('reason')!r}"
    )
