"""Tests for M4c.4: path-string correctness and targeted-add-failure logging.

Covers:
- _to_repo_relative round-trip correctness (completion_evidence and definition_of_done)
- Regression against lstrip-charset truncation
- wip_checkpoint logs an error when targeted git add fails (even when fallback succeeds)

All git calls are mocked — no real repository operations.
"""
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

from tools.completion_evidence import _to_repo_relative as ce_to_repo_relative
from tools.definition_of_done import _to_repo_relative as dod_to_repo_relative
import tools.wip_checkpoint as wc
from tools.git_autonomy import GitResult
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


@pytest.fixture(autouse=True)
def _reset_module_state():
    wc.reset_handlers_for_tests()
    yield
    wc.reset_handlers_for_tests()


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
