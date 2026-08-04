"""tools/git_autonomy.py — M4c full git/PR autonomy.

Three groups, in order of how much damage a regression would do:

1. **Conflict classification.** A false ``trivial`` verdict silently corrupts
   code, so most of these tests are traps: cases that *look* like reformatting
   to a naive whitespace-stripping comparison but are not. The classifier must
   call every one of them ``semantic``.
2. **Worktree safety.** Founder work must survive every branch operation, and
   an un-restorable stash must be reported rather than dropped.
3. **Divergence + check-wake orchestration.** Driven through a fully injected
   git runner (no git binary, no network) — the convention from
   ``tests/test_foreign_repo_workspace.py`` — plus a handful of real-git
   integration tests at the end that prove the mocked command sequences match
   what git actually does.
"""
import os
import subprocess

import pytest

from tools.git_autonomy import (
    SEMANTIC,
    TRIVIAL,
    GitResult,
    WorkGuard,
    auto_resolve_conflicts,
    classify_conflict,
    parse_conflict_hunks,
    path_in_scope,
    protect_uncommitted_work,
    rebase_onto,
    resolve_conflict_text,
    restore_protected_work,
    safe_checkout,
    scope_from_task,
    sync_with_base,
    wake_pr_checks,
    worktree_files,
)


# ==========================================================================
# Scripted git runner
# ==========================================================================

class ScriptedGit:
    """Injectable ``git_run`` that records every invocation and replies from a
    per-command script. Anything unscripted succeeds with empty output."""

    def __init__(self, script=None, head="feature/x"):
        self.calls: list[list[str]] = []
        self.script = {k: list(v) for k, v in (script or {}).items()}
        self.head = head  # answer to `git branch --show-current`

    @staticmethod
    def keys(args: list[str]) -> list[str]:
        """Script keys for a command, most specific first, ignoring leading
        ``-c key=value`` pairs: ``rebase --continue`` then ``rebase``."""
        i = 0
        while i + 1 < len(args) and args[i] == "-c":
            i += 2
        rest = args[i:]
        if not rest:
            return []
        return [" ".join(rest[:2]), rest[0]] if len(rest) > 1 else [rest[0]]

    def __call__(self, args, cwd, timeout=120):
        args = list(args)
        self.calls.append(args)
        for key in self.keys(args):
            queue = self.script.get(key)
            if queue:
                nxt = queue.pop(0)
                return nxt if isinstance(nxt, GitResult) else GitResult(*nxt)
        if args == ["branch", "--show-current"]:
            return GitResult(True, self.head)
        return GitResult(True, "")

    def ran(self, *tokens) -> bool:
        """True when some call contains every token. Matching is token-exact,
        not substring: a stash label of 'runner-autonomy:checkout' must not
        register as having run `git checkout`."""
        return any(all(t in c for t in tokens) for c in self.calls)

    def index_of(self, *tokens) -> int:
        """Position of the first call containing every token (-1 if absent)."""
        for i, c in enumerate(self.calls):
            if all(t in c for t in tokens):
                return i
        return -1

    def count(self, *tokens) -> int:
        return sum(1 for c in self.calls if all(t in c for t in tokens))


def _ok(output=""):
    return GitResult(True, output)


def _fail(output=""):
    return GitResult(False, output)


# ==========================================================================
# 1. Conflict classification — the motivating case
# ==========================================================================

# The exact shape of the six conflicts the founder resolved by hand in
# tests/test_foreign_repo_workspace.py during M4b: one side wrapped the call
# across three lines, the other kept it on one. Identical semantics.
WRAPPED_CALL_CONFLICT = '''\
def test_ensure_workspace_clones():
<<<<<<< HEAD
    result = ensure_workspace("biz-abc", "acme/widgets", "tok", cfg, git_run=fake_git_run)
=======
    result = ensure_workspace(
        "biz-abc", "acme/widgets", "tok", cfg, git_run=fake_git_run
    )
>>>>>>> origin/main
    assert result["success"] is True
'''


def test_wrapped_call_across_lines_is_trivial():
    """The M4b case: a call wrapped across three lines vs kept on one."""
    _, hunks = parse_conflict_hunks(WRAPPED_CALL_CONFLICT)
    assert len(hunks) == 1
    verdict = classify_conflict(hunks[0].ours, hunks[0].theirs, path="tests/test_x.py")
    assert verdict["verdict"] == TRIVIAL, verdict


def test_wrapped_call_with_magic_trailing_comma_is_trivial():
    """Black-style wrapping adds a trailing comma — still identical semantics."""
    verdict = classify_conflict(
        '    result = f(a, b, c)',
        '    result = f(\n        a,\n        b,\n        c,\n    )',
        path="x.py",
    )
    assert verdict["verdict"] == TRIVIAL, verdict


def test_indentation_only_reflow_is_trivial_within_brackets():
    verdict = classify_conflict(
        "x = [1,   2,\n     3]",
        "x = [\n    1, 2, 3\n]",
        path="x.py",
    )
    assert verdict["verdict"] == TRIVIAL, verdict


def test_identical_sides_are_trivial():
    verdict = classify_conflict("a = 1", "a = 1", path="x.py")
    assert verdict["verdict"] == TRIVIAL


def test_resolution_keeps_surrounding_file_byte_for_byte():
    report = resolve_conflict_text(WRAPPED_CALL_CONFLICT, path="tests/test_x.py", prefer="ours")
    assert report.trivial, report.reason
    assert report.resolved_text == (
        'def test_ensure_workspace_clones():\n'
        '    result = ensure_workspace("biz-abc", "acme/widgets", "tok", cfg, git_run=fake_git_run)\n'
        '    assert result["success"] is True\n'
    )


def test_resolution_prefer_theirs_keeps_incoming_formatting():
    report = resolve_conflict_text(WRAPPED_CALL_CONFLICT, path="tests/test_x.py", prefer="theirs")
    assert report.trivial
    assert "ensure_workspace(\n" in report.resolved_text
    assert "<<<<<<<" not in report.resolved_text


# --------------------------------------------------------------------------
# 1b. False-positive traps — every one of these MUST be semantic
# --------------------------------------------------------------------------

def test_trap_indentation_change_is_semantic():
    """The dangerous one. Naive whitespace-stripping normalises both sides to
    'if x: do_a() do_b()' — but moving do_b() out of the if body changes what
    the program does. Bracket-aware line joining keeps them distinct."""
    ours = "if x:\n    do_a()\ndo_b()"
    theirs = "if x:\n    do_a()\n    do_b()"
    verdict = classify_conflict(ours, theirs, path="x.py")
    assert verdict["verdict"] == SEMANTIC, verdict


def test_trap_whitespace_inside_string_literal_is_semantic():
    """'hello  world' and 'hello world' are different strings."""
    verdict = classify_conflict('msg = "hello  world"', 'msg = "hello world"', path="x.py")
    assert verdict["verdict"] == SEMANTIC, verdict


def test_trap_word_boundary_whitespace_is_semantic():
    """`not x` (an expression) vs `notx` (a name) must not collapse together."""
    verdict = classify_conflict("if not x:\n    pass", "if notx:\n    pass", path="x.py")
    assert verdict["verdict"] == SEMANTIC, verdict


def test_trap_differing_comment_is_semantic():
    verdict = classify_conflict(
        "value = 1  # keep in sync with config",
        "value = 1  # arbitrary default",
        path="x.py",
    )
    assert verdict["verdict"] == SEMANTIC, verdict


def test_trap_multiline_string_literal_is_semantic():
    ours = 'DOC = """line one\nline two"""'
    theirs = 'DOC = """line one\n    line two"""'
    verdict = classify_conflict(ours, theirs, path="x.py")
    assert verdict["verdict"] == SEMANTIC, verdict


def test_trap_changed_argument_value_is_semantic():
    verdict = classify_conflict('f("a", timeout=30)', 'f(\n    "a",\n    timeout=60,\n)', path="x.py")
    assert verdict["verdict"] == SEMANTIC, verdict


def test_trap_added_statement_is_semantic():
    verdict = classify_conflict("a = 1", "a = 1\nb = 2", path="x.py")
    assert verdict["verdict"] == SEMANTIC, verdict


def test_trap_reordered_arguments_is_semantic():
    verdict = classify_conflict("f(a, b)", "f(\n    b,\n    a,\n)", path="x.py")
    assert verdict["verdict"] == SEMANTIC, verdict


@pytest.mark.parametrize("path", ["README.md", "package.json", "ci.yaml", "deploy.sh", "notes.txt"])
def test_trap_ineligible_file_types_are_semantic(path):
    """Formats where whitespace or a trailing comma IS content are never
    auto-resolved, however trivial the diff looks."""
    verdict = classify_conflict("a  b", "a b", path=path)
    assert verdict["verdict"] == SEMANTIC, verdict


def test_decrement_operator_is_not_treated_as_a_sql_comment():
    """`--` opens a comment in SQL but is a decrement in JS/C. Misreading it
    swallows the rest of the line — including brackets — and corrupts the
    bracket depth that decides how lines are joined."""
    verdict = classify_conflict("while (i--) { f(a, b); }", "while (i--) { f(a,   b); }", path="x.js")
    assert verdict["verdict"] == TRIVIAL, verdict
    # The same characters really are a comment in SQL, so the two sides differ
    # there (one comments out more text than the other).
    assert classify_conflict("a -- x", "a -- y", path="q.sql")["verdict"] == SEMANTIC


def test_hash_is_a_comment_in_python_but_not_in_typescript():
    assert classify_conflict("a = 1 # one", "a = 1 # two", path="x.py")["verdict"] == SEMANTIC
    # `#name` is a private field in TS — part of the code, not a comment.
    assert classify_conflict("this.#n = 1", "this.#n  =  1", path="x.ts")["verdict"] == TRIVIAL
    assert classify_conflict("this.#a = 1", "this.#b = 1", path="x.ts")["verdict"] == SEMANTIC


def test_auto_resolution_can_be_disabled_entirely(tmp_path):
    """GIT_AUTO_RESOLVE_TRIVIAL_CONFLICTS=false — every conflict waits for a human."""
    from types import SimpleNamespace

    cfg = SimpleNamespace(git_auto_resolve_trivial_conflicts=False)
    git = ScriptedGit({
        "rebase": [_fail("CONFLICT (content): Merge conflict in tools/x.py")],
        "diff": [_ok("tools/x.py")],
    })
    result = sync_with_base(
        str(tmp_path), cfg=cfg, git_run=git,
        read_file=lambda p: WRAPPED_CALL_CONFLICT,
        write_file=lambda p, t: None,
    )
    assert result["success"] is False
    assert git.ran("rebase", "--abort")
    assert not git.ran("add"), "nothing may be resolved when the flag is off"


def test_trailing_comma_not_dropped_for_sql():
    """A trailing comma before a closing paren is a syntax error in SQL, so it
    is never treated as a formatter artefact there."""
    verdict = classify_conflict("INSERT INTO t VALUES (1, 2)", "INSERT INTO t VALUES (1, 2,)", path="q.sql")
    assert verdict["verdict"] == SEMANTIC, verdict


def test_file_with_one_semantic_hunk_is_escalated_whole():
    """A half-resolved file is worse than an untouched one."""
    text = (
        "<<<<<<< HEAD\nf(a, b)\n=======\nf(\n    a, b\n)\n>>>>>>> main\n"
        "mid = 1\n"
        "<<<<<<< HEAD\ntimeout = 30\n=======\ntimeout = 60\n>>>>>>> main\n"
    )
    report = resolve_conflict_text(text, path="x.py")
    assert not report.trivial
    assert report.resolved_text is None
    assert "semantic" in report.reason
    assert [h["verdict"] for h in report.hunks] == [TRIVIAL, SEMANTIC]


# --------------------------------------------------------------------------
# 1c. Hunk parsing
# --------------------------------------------------------------------------

def test_parse_diff3_style_conflict_captures_base():
    text = (
        "before\n<<<<<<< HEAD\nours\n||||||| merged common ancestors\nbase\n"
        "=======\ntheirs\n>>>>>>> origin/main\nafter\n"
    )
    segments, hunks = parse_conflict_hunks(text)
    assert len(hunks) == 1
    assert hunks[0].ours == "ours"
    assert hunks[0].theirs == "theirs"
    assert hunks[0].base == "base"
    assert hunks[0].ours_label == "HEAD"
    assert hunks[0].theirs_label == "origin/main"
    assert segments[0] == "before"


def test_parse_unterminated_marker_is_kept_verbatim():
    """A truncated marker is not a conflict we understand — nothing is lost."""
    text = "a\n<<<<<<< HEAD\nb\n"
    segments, hunks = parse_conflict_hunks(text)
    assert hunks == []
    assert "\n".join(s for s in segments if isinstance(s, str)) == text


def test_file_with_no_conflict_markers_resolves_to_itself():
    report = resolve_conflict_text("a = 1\n", path="x.py")
    assert report.trivial
    assert report.resolved_text == "a = 1\n"


# ==========================================================================
# 2. Scope enforcement
# ==========================================================================

def test_path_in_scope_unrestricted_when_no_scope_declared():
    assert path_in_scope("anything/at/all.py", None) is True
    assert path_in_scope("anything/at/all.py", []) is True


def test_path_in_scope_respects_declared_scope():
    scope = ["runner/langgraph/tools", "runner/langgraph/tests"]
    assert path_in_scope("runner/langgraph/tools/git_autonomy.py", scope) is True
    assert path_in_scope("src/app/page.tsx", scope) is False


def test_scope_from_task_reads_acceptance_criteria():
    task = {"acceptance_criteria": {"allowed_scope": "runner/langgraph/tools, runner/langgraph/tests"}}
    assert scope_from_task(task) == ["runner/langgraph/tools", "runner/langgraph/tests"]
    assert scope_from_task({}) == []
    assert scope_from_task({"acceptance_criteria": "freeform text"}) == []


def test_out_of_scope_conflict_is_escalated_even_when_trivial(tmp_path):
    """CRITICAL SAFETY: never touch files outside the task's declared scope."""
    git = ScriptedGit({"diff": [_ok("docs/NOTES.py")]})
    written = {}
    result = auto_resolve_conflicts(
        str(tmp_path),
        allowed_paths=["runner/langgraph/tools"],
        git_run=git,
        read_file=lambda p: WRAPPED_CALL_CONFLICT,
        write_file=lambda p, t: written.setdefault(p, t),
    )
    assert result["resolved"] == []
    assert result["all_resolved"] is False
    assert "outside the task's declared scope" in result["escalated"][0]["reason"]
    assert written == {}, "an out-of-scope file must never be written"
    assert not git.ran("add"), "an out-of-scope file must never be staged"


def test_in_scope_trivial_conflict_is_resolved_and_staged(tmp_path):
    git = ScriptedGit({"diff": [_ok("tools/x.py")]})
    written = {}
    result = auto_resolve_conflicts(
        str(tmp_path),
        allowed_paths=["tools"],
        git_run=git,
        read_file=lambda p: WRAPPED_CALL_CONFLICT,
        write_file=lambda p, t: written.__setitem__(p, t),
    )
    assert result["resolved"] == ["tools/x.py"]
    assert result["all_resolved"] is True
    assert git.ran("add", "tools/x.py")
    assert "<<<<<<<" not in next(iter(written.values()))


# ==========================================================================
# 3. Worktree safety — never silently discard founder work
# ==========================================================================

def test_protect_uncommitted_work_noop_on_clean_tree():
    git = ScriptedGit({"status": [_ok("")]})
    guard = protect_uncommitted_work("/repo", git_run=git)
    assert guard.action == "none"
    assert not git.ran("stash")


def test_protect_uncommitted_work_stashes_including_untracked():
    git = ScriptedGit({"status": [_ok(" M docs/NOTES.md\n?? scratch.txt")]})
    guard = protect_uncommitted_work("/repo", label="create-branch:feature/x", git_run=git)
    assert guard.action == "stashed"
    assert guard.files == ["docs/NOTES.md", "scratch.txt"]
    assert git.ran("stash", "push", "--include-untracked")
    assert git.ran("runner-autonomy:create-branch:feature/x")


def test_worktree_files_handles_renames():
    git = ScriptedGit({"status": [_ok('R  old.py -> new.py')]})
    assert worktree_files("/repo", git_run=git) == ["new.py"]


def test_failed_stash_blocks_the_checkout_rather_than_risking_the_work():
    git = ScriptedGit({
        "status": [_ok(" M docs/NOTES.md")],
        "stash": [_fail("error: cannot stash")],
    })
    result = safe_checkout("/repo", "feature/x", git_run=git)
    assert result["success"] is False
    assert "unprotected local changes" in result["output"]
    assert not git.ran("checkout"), "must not check out over work it failed to protect"


def test_safe_checkout_stashes_before_checking_out():
    git = ScriptedGit({"status": [_ok(" M docs/NOTES.md")]})
    result = safe_checkout("/repo", "feature/x", create=True, git_run=git)
    assert result["success"] is True
    assert git.index_of("stash", "push") < git.index_of("checkout"), \
        "the stash must happen before the checkout"
    assert git.calls[git.index_of("checkout")] == ["checkout", "-b", "feature/x"]


def test_unpoppable_stash_is_kept_not_dropped():
    """The one outcome this module must never produce is lost work. A conflicting
    pop leaves the entry in the stash list and reports it."""
    git = ScriptedGit({"stash": [_fail("CONFLICT (content): Merge conflict in docs/NOTES.md")]})
    guard = WorkGuard(action="stashed", stash_message="runner-autonomy:sync", files=["docs/NOTES.md"])
    restored = restore_protected_work("/repo", guard, git_run=git)
    assert restored.restored is False
    assert restored.has_stash is True
    assert "CONFLICT" in restored.error
    assert not git.ran("stash", "drop")
    assert not git.ran("checkout", "--")


def test_restore_is_a_noop_when_nothing_was_stashed():
    git = ScriptedGit()
    guard = restore_protected_work("/repo", WorkGuard(action="none"), git_run=git)
    assert guard.restored is False
    assert git.calls == []


def test_no_destructive_commands_anywhere_in_the_sync_path(tmp_path):
    """Blanket guard: the whole divergence path must never reset, clean, or
    drop a stash — the operations that destroyed founder work in M4b."""
    git = ScriptedGit({
        "status": [_ok(" M docs/NOTES.md")],
        "rebase": [_fail("CONFLICT (content): Merge conflict in x.py")],
        "diff": [_ok("x.py")],
    })
    sync_with_base(
        str(tmp_path), git_run=git,
        read_file=lambda p: "<<<<<<< HEAD\ntimeout = 30\n=======\ntimeout = 60\n>>>>>>> main\n",
        write_file=lambda p, t: None,
    )
    flat = [" ".join(c) for c in git.calls]
    for forbidden in ("reset --hard", "clean -", "stash drop", "checkout -- .", "push --force "):
        assert not any(forbidden in c for c in flat), f"ran forbidden command: {forbidden} in {flat}"


# ==========================================================================
# 4. Divergence — rebase, already-upstream drops, conflict triage
# ==========================================================================

def test_rebase_clean_success():
    git = ScriptedGit({"rebase": [_ok("Successfully rebased and updated refs/heads/feat.")]})
    result = rebase_onto("/repo", "origin/main", git_run=git)
    assert result["success"] is True
    assert result["rebased"] is True
    assert not git.ran("rebase", "--abort")


def test_rebase_drops_commit_whose_contents_are_already_upstream():
    """git's own wording: 'dropping <sha> <subject> -- patch contents already
    upstream'. The apply backend stops there and needs an explicit --skip."""
    git = ScriptedGit({
        "rebase": [
            _fail("dropping abc123 change b -- patch contents already upstream"),
            _ok("Successfully rebased and updated refs/heads/feat."),
        ],
        "diff": [_ok("")],  # no unmerged paths
    })
    result = rebase_onto("/repo", "origin/main", git_run=git)
    assert result["success"] is True
    assert result["skipped_commits"] == 1
    assert git.ran("rebase", "--skip")
    assert not git.ran("rebase", "--abort")


def test_rebase_skips_on_apply_backend_no_changes_message():
    """The am/apply backend's phrasing of the same situation."""
    git = ScriptedGit({
        "rebase": [
            _fail(
                "No changes - did you forget to use 'git add'?\n"
                "If there is nothing left to stage, chances are that something else\n"
                "already introduced the same changes; you might want to skip this patch."
            ),
            _ok("Successfully rebased."),
        ],
        "diff": [_ok("")],
    })
    result = rebase_onto("/repo", "origin/main", git_run=git)
    assert result["success"] is True
    assert git.ran("rebase", "--skip")


def test_rebase_auto_resolves_trivial_conflict_and_continues():
    git = ScriptedGit({
        "rebase": [_fail("CONFLICT (content): Merge conflict in tools/x.py")],
        "diff": [_ok("tools/x.py"), _ok("")],
        "rebase --continue": [_ok("Successfully rebased and updated refs/heads/feat.")],
    })
    written = {}
    result = rebase_onto(
        "/repo", "origin/main", git_run=git,
        read_file=lambda p: WRAPPED_CALL_CONFLICT,
        write_file=lambda p, t: written.__setitem__(p, t),
    )
    assert result["success"] is True
    assert result["resolved_files"] == ["tools/x.py"]
    assert git.ran("rebase", "--continue")
    assert not git.ran("rebase", "--abort")
    assert "<<<<<<<" not in next(iter(written.values()))


def test_rebase_aborts_and_escalates_on_semantic_conflict():
    git = ScriptedGit({
        "rebase": [_fail("CONFLICT (content): Merge conflict in tools/x.py")],
        "diff": [_ok("tools/x.py")],
    })
    written = {}
    result = rebase_onto(
        "/repo", "origin/main", git_run=git,
        read_file=lambda p: "<<<<<<< HEAD\ntimeout = 30\n=======\ntimeout = 60\n>>>>>>> main\n",
        write_file=lambda p, t: written.__setitem__(p, t),
    )
    assert result["success"] is False
    assert result["reason"] == "conflicts_escalated"
    assert result["escalated"][0]["path"] == "tools/x.py"
    assert git.ran("rebase", "--abort"), "an escalated rebase must leave the branch untouched"
    assert not git.ran("rebase", "--continue")
    assert written == {}


def test_rebase_escalates_when_auto_resolution_disabled():
    git = ScriptedGit({
        "rebase": [_fail("CONFLICT")],
        "diff": [_ok("tools/x.py")],
    })
    result = rebase_onto("/repo", "origin/main", auto_resolve=False, git_run=git)
    assert result["success"] is False
    assert git.ran("rebase", "--abort")


def test_rebase_aborts_on_unrecognised_failure():
    git = ScriptedGit({"rebase": [_fail("fatal: invalid upstream 'origin/main'")], "diff": [_ok("")]})
    result = rebase_onto("/repo", "origin/main", git_run=git)
    assert result["success"] is False
    assert result["reason"] == "rebase_failed"
    assert git.ran("rebase", "--abort")


def test_rebase_gives_up_after_max_steps_without_looping_forever():
    git = ScriptedGit({
        "rebase": [_fail("dropping x -- patch contents already upstream")] * 50,
        "diff": [_ok("")] * 50,
    })
    result = rebase_onto("/repo", "origin/main", max_steps=3, git_run=git)
    assert result["success"] is False
    assert result["reason"] == "max_steps_exceeded"
    assert git.ran("rebase", "--abort")


def test_sync_with_base_stashes_fetches_rebases_and_restores():
    git = ScriptedGit({
        "status": [_ok(" M docs/NOTES.md")],
        "rebase": [_ok("Successfully rebased.")],
    })
    result = sync_with_base("/repo", base="main", git_run=git)
    assert result["success"] is True
    assert result["stash_stranded"] is False
    assert git.index_of("stash", "push") < git.index_of("fetch") < git.index_of("rebase")
    assert git.calls[-1] == ["stash", "pop"], "work must be restored last"


def test_sync_with_base_restores_work_when_fetch_fails():
    git = ScriptedGit({
        "status": [_ok(" M docs/NOTES.md")],
        "fetch": [_fail("fatal: could not read from remote")],
    })
    result = sync_with_base("/repo", git_run=git)
    assert result["success"] is False
    assert result["reason"] == "fetch_failed"
    assert git.ran("stash", "pop"), "a failed fetch must not strand the founder's work"
    assert not git.ran("rebase")


def test_sync_with_base_refuses_when_work_cannot_be_protected():
    git = ScriptedGit({
        "status": [_ok(" M docs/NOTES.md")],
        "stash": [_fail("error: cannot stash")],
    })
    result = sync_with_base("/repo", git_run=git)
    assert result["success"] is False
    assert result["reason"] == "unprotected_local_changes"
    assert not git.ran("fetch")
    assert not git.ran("rebase")


# ==========================================================================
# 5. Waking a PR whose checks were never scheduled
# ==========================================================================

def test_wake_refuses_protected_branch():
    git = ScriptedGit()
    result = wake_pr_checks("/repo", "main", git_run=git)
    assert result["success"] is False
    assert "protected branch" in result["reason"]
    assert git.calls == []


def test_wake_refuses_when_head_is_not_the_target_branch():
    """Regression. Every local rung acts on HEAD, so waking 'feature/t1' while
    HEAD sits on another branch would commit to the wrong branch — which is
    exactly what happened (three stray empty commits) before this guard existed."""
    git = ScriptedGit(head="feature/something-else")
    result = wake_pr_checks("/repo", "feature/t1", strategies=["empty_commit"], git_run=git)
    assert result["success"] is False
    assert "HEAD is on 'feature/something-else'" in result["reason"]
    assert not git.ran("commit", "--allow-empty")
    assert not git.ran("push")
    assert not git.ran("stash", "push"), "must refuse before disturbing the worktree at all"


def test_wake_update_branch_api_short_circuits_the_ladder():
    git = ScriptedGit()
    result = wake_pr_checks(
        "/repo", "feature/x", github_repo="o/r", pr_number=7,
        git_run=git, update_branch=lambda repo, pr, token: True,
    )
    assert result["success"] is True
    assert result["strategy"] == "update_branch"
    assert not git.ran("push"), "no local git needed when the API does it"


def test_wake_rebase_rung_is_inert_without_force_with_lease_opt_in():
    """AGENTS.md forbids force pushes; rebasing a pushed branch requires one, so
    the rung stays inert and the ladder falls through to a non-rewriting rung."""
    git = ScriptedGit({"merge": [_ok("Merge made by the 'ort' strategy.")]})
    result = wake_pr_checks(
        "/repo", "feature/x", github_repo="o/r", pr_number=7,
        allow_force_with_lease=False,
        git_run=git, update_branch=lambda repo, pr, token: False,
    )
    assert result["success"] is True
    assert result["strategy"] == "merge_base"
    assert not git.ran("rebase"), "must not rebase when it could not push the result"
    assert not any("--force" in " ".join(c) for c in git.calls)
    rebase_attempt = next(a for a in result["attempts"] if a["strategy"] == "rebase")
    assert "GIT_ALLOW_FORCE_WITH_LEASE" in rebase_attempt["reason"]


def test_wake_rebase_rung_uses_force_with_lease_when_opted_in():
    git = ScriptedGit({"rebase": [_ok("Successfully rebased.")]})
    result = wake_pr_checks(
        "/repo", "feature/x", github_repo="o/r", pr_number=7,
        allow_force_with_lease=True,
        git_run=git, update_branch=lambda repo, pr, token: False,
    )
    assert result["success"] is True
    assert result["strategy"] == "rebase"
    assert git.ran("push", "--force-with-lease", "origin", "feature/x")


def test_wake_never_escalates_a_refused_lease_to_a_real_force_push():
    """--force-with-lease refuses exactly when someone else pushed to the branch.
    That is the signal to back off, never to push harder."""
    git = ScriptedGit({
        "rebase": [_ok("Successfully rebased.")],
        "push": [_fail("! [rejected] stale info"), _ok("")],
        "merge": [_ok("Merge made by the 'ort' strategy.")],
    })
    result = wake_pr_checks(
        "/repo", "feature/x", github_repo="o/r", pr_number=7,
        allow_force_with_lease=True,
        git_run=git, update_branch=lambda repo, pr, token: False,
    )
    assert not any(
        "--force" in " ".join(c) and "--force-with-lease" not in " ".join(c)
        for c in git.calls
    ), "a refused lease must never become a bare --force"
    rebase_attempt = next(a for a in result["attempts"] if a["strategy"] == "rebase")
    assert "refused" in rebase_attempt["reason"]


def test_wake_merge_base_rung_merges_and_pushes():
    git = ScriptedGit({"merge": [_ok("Merge made by the 'ort' strategy.")]})
    result = wake_pr_checks(
        "/repo", "feature/x", strategies=["merge_base"], git_run=git,
    )
    assert result["success"] is True
    assert git.ran("merge", "--no-edit", "origin/main")
    assert git.ran("push", "origin", "feature/x")


def test_wake_merge_base_skips_when_branch_already_current():
    git = ScriptedGit({"merge": [_ok("Already up to date.")], "commit": [_ok("")]})
    result = wake_pr_checks(
        "/repo", "feature/x", strategies=["merge_base", "empty_commit"], git_run=git,
    )
    assert result["success"] is True
    assert result["strategy"] == "empty_commit"
    merge_attempt = next(a for a in result["attempts"] if a["strategy"] == "merge_base")
    assert "already contains latest base" in merge_attempt["reason"]


def test_wake_merge_base_escalates_semantic_conflict_and_aborts():
    git = ScriptedGit({
        "merge": [_fail("CONFLICT (content): Merge conflict in tools/x.py")],
        "diff": [_ok("tools/x.py")],
    })
    result = wake_pr_checks(
        "/repo", "feature/x", strategies=["merge_base"], git_run=git,
        read_file=lambda p: "<<<<<<< HEAD\ntimeout = 30\n=======\ntimeout = 60\n>>>>>>> main\n",
        write_file=lambda p, t: None,
    )
    assert result["success"] is False
    assert git.ran("merge", "--abort")
    assert not git.ran("push")


def test_wake_empty_commit_is_the_last_resort():
    git = ScriptedGit()
    result = wake_pr_checks("/repo", "feature/x", strategies=["empty_commit"], git_run=git)
    assert result["success"] is True
    assert git.ran("commit", "--allow-empty")
    assert git.ran("push", "origin", "feature/x")


def test_wake_reports_exhaustion_when_every_rung_fails():
    git = ScriptedGit({
        "push": [_fail("rejected"), _fail("rejected")],
        "merge": [_ok("Merge made")],
    })
    result = wake_pr_checks(
        "/repo", "feature/x", strategies=["merge_base", "empty_commit"], git_run=git,
    )
    assert result["success"] is False
    assert result["reason"] == "wake_strategies_exhausted"
    assert [a["strategy"] for a in result["attempts"]] == ["merge_base", "empty_commit"]


def test_wake_protects_and_restores_uncommitted_work():
    git = ScriptedGit({"status": [_ok(" M docs/NOTES.md")]})
    wake_pr_checks("/repo", "feature/x", strategies=["empty_commit"], git_run=git)
    assert git.ran("stash", "push", "--include-untracked")
    assert git.ran("stash", "pop")
    assert git.index_of("stash", "push") < git.index_of("commit", "--allow-empty")


def test_wake_restores_work_even_when_every_strategy_fails():
    git = ScriptedGit({"status": [_ok(" M docs/NOTES.md")], "push": [_fail("rejected")]})
    result = wake_pr_checks("/repo", "feature/x", strategies=["empty_commit"], git_run=git)
    assert result["success"] is False
    assert git.ran("stash", "pop"), "the finally-block must restore work on the failure path too"


# ==========================================================================
# 6. Real-git integration — proves the mocked sequences match reality
# ==========================================================================

def _git(repo, *args, check=True):
    return subprocess.run(
        ["git"] + list(args), cwd=repo, capture_output=True, text=True, check=check,
    )


@pytest.fixture
def real_repos(tmp_path):
    """An origin repo plus a clone with a feature branch, both fully local."""
    origin, work = tmp_path / "origin", tmp_path / "work"
    origin.mkdir()
    _git(origin, "-c", "init.defaultBranch=main", "init", "-q", ".")
    _git(origin, "config", "user.email", "t@example.com")
    _git(origin, "config", "user.name", "t")
    (origin / "tools").mkdir()
    (origin / "tools" / "x.py").write_text('a = 1\nresult = f("a", "b")\nz = 9\n')
    _git(origin, "add", "-A")
    _git(origin, "commit", "-qm", "base")

    _git(tmp_path, "clone", "-q", str(origin), str(work))
    _git(work, "config", "user.email", "t@example.com")
    _git(work, "config", "user.name", "t")
    return origin, work


def test_real_git_drops_local_commit_already_upstream(real_repos):
    """End-to-end on a real repo: the same change landed upstream independently,
    so the local commit's patch is already there and must be dropped cleanly."""
    origin, work = real_repos
    _git(work, "checkout", "-qb", "feature/dup")
    (work / "tools" / "x.py").write_text('a = 2\nresult = f("a", "b")\nz = 9\n')
    _git(work, "commit", "-qam", "bump a")

    (origin / "tools" / "x.py").write_text('a = 2\nresult = f("a", "b")\nz = 10\n')
    _git(origin, "commit", "-qam", "upstream bump a and z")

    result = sync_with_base(str(work), base="main")

    assert result["success"] is True, result
    assert (work / "tools" / "x.py").read_text() == 'a = 2\nresult = f("a", "b")\nz = 10\n'
    assert _git(work, "log", "--oneline").stdout.count("bump a") == 1


def test_real_git_auto_resolves_formatting_only_conflict(real_repos):
    """The M4b case on a real repo: the branch wrapped a call across lines while
    main reformatted the same line. Identical semantics, so the rebase completes
    without a human."""
    origin, work = real_repos
    _git(work, "checkout", "-qb", "feature/wrap")
    (work / "tools" / "x.py").write_text('a = 1\nresult = f(\n    "a",\n    "b",\n)\nz = 9\n')
    _git(work, "commit", "-qam", "wrap call")

    (origin / "tools" / "x.py").write_text('a = 1\nresult = f( "a",  "b" )\nz = 9\n')
    _git(origin, "commit", "-qam", "upstream reformat")

    result = sync_with_base(str(work), base="main", allowed_paths=["tools"])

    assert result["success"] is True, result
    text = (work / "tools" / "x.py").read_text()
    assert "<<<<<<<" not in text
    assert 'f(' in text and '"a"' in text and '"b"' in text
    assert _git(work, "status", "--porcelain").stdout.strip() == ""


def test_real_git_escalates_semantic_conflict_and_leaves_branch_intact(real_repos):
    origin, work = real_repos
    _git(work, "checkout", "-qb", "feature/sem")
    (work / "tools" / "x.py").write_text('a = 1\nresult = f("a", "CHANGED")\nz = 9\n')
    _git(work, "commit", "-qam", "branch change")
    head_before = _git(work, "rev-parse", "HEAD").stdout.strip()

    (origin / "tools" / "x.py").write_text('a = 1\nresult = f("a", "DIFFERENT")\nz = 9\n')
    _git(origin, "commit", "-qam", "upstream change")

    result = sync_with_base(str(work), base="main", allowed_paths=["tools"])

    assert result["success"] is False
    assert result["reason"] == "conflicts_escalated"
    assert _git(work, "rev-parse", "HEAD").stdout.strip() == head_before
    assert _git(work, "status", "--porcelain").stdout.strip() == ""
    assert "<<<<<<<" not in (work / "tools" / "x.py").read_text()


def test_real_git_preserves_uncommitted_work_across_a_sync(real_repos):
    """The M4b incident, reproduced on a real repo: uncommitted local doc edits
    must still be there after a routine branch/sync operation."""
    origin, work = real_repos
    _git(work, "checkout", "-qb", "feature/keep")
    (origin / "tools" / "x.py").write_text('a = 1\nresult = f("a", "b")\nz = 99\n')
    _git(origin, "commit", "-qam", "upstream moves on")

    (work / "NOTES.md").write_text("founder's uncommitted notes\n")
    (work / "tools" / "x.py").write_text('a = 1\nresult = f("a", "b")\nz = 9\nlocal_edit = True\n')

    result = sync_with_base(str(work), base="main")

    assert result["success"] is True, result
    assert (work / "NOTES.md").read_text() == "founder's uncommitted notes\n"
    assert "local_edit = True" in (work / "tools" / "x.py").read_text()
    assert "z = 99" in (work / "tools" / "x.py").read_text(), "upstream change should have landed too"


def test_real_git_create_branch_carries_uncommitted_work_over(real_repos):
    from tools.git_tools import create_branch

    _, work = real_repos
    (work / "NOTES.md").write_text("uncommitted\n")

    result = create_branch(str(work), "feature/carry")

    assert result["success"] is True, result
    assert _git(work, "branch", "--show-current").stdout.strip() == "feature/carry"
    assert (work / "NOTES.md").read_text() == "uncommitted\n"
    assert _git(work, "stash", "list").stdout.strip() == "", "nothing should be left stashed"


def test_real_git_conflict_markers_parse_as_written_by_git(real_repos):
    """Guards the parser against git's actual marker format rather than a
    hand-written approximation of it."""
    origin, work = real_repos
    _git(work, "checkout", "-qb", "feature/markers")
    (work / "tools" / "x.py").write_text('a = 1\nresult = OURS\nz = 9\n')
    _git(work, "commit", "-qam", "ours")
    (origin / "tools" / "x.py").write_text('a = 1\nresult = THEIRS\nz = 9\n')
    _git(origin, "commit", "-qam", "theirs")
    _git(work, "fetch", "-q", "origin")
    _git(work, "rebase", "origin/main", check=False)

    text = (work / "tools" / "x.py").read_text()
    _, hunks = parse_conflict_hunks(text)
    assert len(hunks) == 1
    assert {hunks[0].ours.strip(), hunks[0].theirs.strip()} == {"result = OURS", "result = THEIRS"}
    _git(work, "rebase", "--abort", check=False)


def test_env_flag_can_narrow_eligible_suffixes(monkeypatch):
    from config import RunnerConfig

    monkeypatch.setenv("GIT_TRIVIAL_CONFLICT_SUFFIXES", "ts,tsx")
    cfg = RunnerConfig()
    assert cfg.git_trivial_conflict_suffixes == [".ts", ".tsx"]
    assert classify_conflict("f(a, b)", "f(\n    a, b\n)", path="x.py", cfg=cfg)["verdict"] == SEMANTIC
    assert classify_conflict("f(a, b)", "f(\n    a, b\n)", path="x.ts", cfg=cfg)["verdict"] == TRIVIAL


def test_config_defaults_are_conservative():
    from config import RunnerConfig

    cfg = RunnerConfig()
    assert cfg.git_allow_force_with_lease is False, "force pushes must be opt-in (AGENTS.md)"
    assert cfg.git_prefer_rebase is True
    assert cfg.git_auto_resolve_trivial_conflicts is True
    assert cfg.pr_checks_wake_attempts >= 1
    assert cfg.pr_checks_wake_strategies[0] == "update_branch"
    assert "git_allow_force_with_lease" in cfg.report()


def test_new_env_vars_are_documented_in_the_readme():
    """CLAUDE.md's three-place rule: config.py, the README env table, a test."""
    readme = os.path.join(os.path.dirname(__file__), "..", "README.md")
    with open(readme, encoding="utf-8") as fh:
        text = fh.read()
    for var in (
        "PR_CHECKS_WAKE_ATTEMPTS",
        "PR_CHECKS_WAKE_STRATEGIES",
        "GIT_PREFER_REBASE",
        "GIT_AUTO_RESOLVE_TRIVIAL_CONFLICTS",
        "GIT_TRIVIAL_CONFLICT_SUFFIXES",
        "GIT_ALLOW_FORCE_WITH_LEASE",
    ):
        assert f"`{var}`" in text, f"{var} is missing from the README env table"


def test_work_loss_events_reach_a_human():
    """Stashed-but-unrestorable work is the only way founder edits can end up
    somewhere unexpected — it must never be a silent log line."""
    import config as config_module

    for event in ("git_work_restore_failed", "git_work_protect_failed", "git_conflict_escalated"):
        assert event in config_module._DEFAULT_SLACK_EVENTS, event


if __name__ == "__main__":
    raise SystemExit(pytest.main([os.path.abspath(__file__), "-q"]))
