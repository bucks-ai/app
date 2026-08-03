"""M4c: end-to-end git/PR autonomy — sync, rebase, conflict triage, check wake-up.

During M4b the founder personally drove every merge: ``gh pr create``, ``gh pr
checks``, ``gh pr merge``, plus three classes of manual intervention this module
exists to remove:

1. **"No checks reported."**  A PR sat with an empty ``check_runs`` list because
   Actions never scheduled a run against its head SHA.  The remedy the founder
   applied by hand was to put the branch back on top of latest ``main`` so a new
   head SHA is pushed and workflows re-trigger.  ``wake_pr_checks`` does that as
   an escalating ladder (see below).
2. **A diverged local ``main``.**  Resolved by hand-choosing rebase vs reset.
   ``sync_with_base`` always prefers ``pull --rebase`` and never resets, and it
   recognises the case where a local commit's content is *already upstream* so
   the commit can be dropped rather than fought with.
3. **Six identical-formatting merge conflicts** in
   ``tests/test_foreign_repo_workspace.py`` — one side wrapped a call across
   three lines, the other kept it on one; the code was character-for-character
   equivalent once the line wrapping was normalised.  ``classify_conflict``
   recognises exactly that class and nothing more.

CRITICAL SAFETY invariants (all unit-tested in ``tests/test_git_autonomy.py``):

  - **Never silently discard founder work.**  During M4b a routine branch
    operation reverted uncommitted local doc edits.  Every entry point here
    calls ``protect_uncommitted_work`` *before* any checkout/rebase/pull, which
    stashes (including untracked files) under a labelled message.  Nothing in
    this module ever runs ``git reset --hard``, ``git checkout -- .``, ``git
    clean``, or ``git stash drop``.  If a stash cannot be restored cleanly it is
    **left in the stash list** and reported loudly — recoverable by hand — never
    discarded to make the automation's life easier.
  - **Never touch files outside the task's declared scope.**  Conflict
    resolution accepts ``allowed_paths`` (the task's
    ``acceptance_criteria.allowed_scope``); a conflicted file outside that scope
    is escalated even when its conflict is textually trivial.
  - **Escalate anything semantic.**  ``classify_conflict`` returns ``trivial``
    only when both sides normalise to an identical token stream *and* identical
    per-logical-line indentation, with string/comment contents compared
    verbatim.  Everything it is not certain about — an unfamiliar file type, a
    multi-line string literal, a differing comment — is ``semantic`` and goes
    back to a human.
  - **No force pushes by default.**  ``AGENTS.md`` forbids ``git push --force``.
    The rebase rung of the wake ladder needs to rewrite an already-pushed
    branch, so it is inert unless ``GIT_ALLOW_FORCE_WITH_LEASE=true``, and even
    then it uses ``--force-with-lease`` (which refuses when origin moved since
    our fetch — i.e. when a human pushed to the branch).  The default ladder
    reaches the same end state without rewriting anything.

Every git invocation goes through an injectable ``git_run`` so the whole module
is unit-testable without a git binary or network (the convention established by
``tools/foreign_repo_workspace.py``).
"""
import os
import re
from dataclasses import dataclass, field
from typing import Callable, Optional

from tools.log_tools import log_event
from tools.shell_tools import run_command

# --------------------------------------------------------------------------
# Conflict classification verdicts
# --------------------------------------------------------------------------
TRIVIAL = "trivial"
SEMANTIC = "semantic"

# File suffixes whose formatting-vs-semantics analysis below is sound: brace or
# bracket delimited languages, plus Python (whose indentation is compared
# exactly). Deliberately excludes formats where whitespace or a trailing comma
# IS the content — .md (two-space line breaks, indented code blocks), .json
# (trailing comma is a syntax error), .yaml/.yml (indentation is structure),
# .sh (line joins need an explicit backslash), .txt, .env. Anything not listed
# is escalated rather than guessed at.
_DEFAULT_AUTO_RESOLVE_SUFFIXES = (
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs",
    ".css", ".scss", ".go", ".rs", ".java", ".kt", ".c", ".h", ".cpp", ".hpp",
    ".sql",
)

# Suffixes where a magic trailing comma before a closing bracket is a formatter
# artefact rather than content. Excluded for .json (syntax error) and .sql
# (syntax error) — both simply absent from this tuple.
_TRAILING_COMMA_OK_SUFFIXES = (
    ".py", ".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".go", ".rs",
)

_CONFLICT_START = re.compile(r"^<{7}(?: (?P<label>.*))?$")
_CONFLICT_BASE = re.compile(r"^\|{7}(?: (?P<label>.*))?$")
_CONFLICT_SEP = re.compile(r"^={7}$")
_CONFLICT_END = re.compile(r"^>{7}(?: (?P<label>.*))?$")

# Real strings emitted by git (verified against the git 2.53 binary's message
# catalogue) when a commit being replayed is already present upstream:
#   sequencer: "dropping %s %s -- patch contents already upstream"
#   rebase:    "warning: skipped previously applied commit %s"
#   am:        "No changes - did you forget to use 'git add'?" followed by
#              "already introduced the same changes; you might want to skip"
# The merge backend drops such a commit on its own; the apply/am backend stops
# and requires an explicit ``git rebase --skip``.
_ALREADY_UPSTREAM_MARKERS = (
    "patch contents already upstream",
    "skipped previously applied commit",
    "no changes -- patch already applied",
    "already introduced the same changes",
)

_PROTECTED_BRANCHES = frozenset({"main", "master", "dev", "develop", "production", "release"})

GitRun = Callable[..., "GitResult"]


@dataclass
class GitResult:
    """Outcome of one git invocation — mirrors ``ToolResult`` but local to this
    module so an injected ``git_run`` never has to import runner state."""
    success: bool
    output: str = ""
    args: tuple = ()


def default_git_run(args: list[str], cwd: str, timeout: int = 120) -> GitResult:
    r = run_command(["git"] + list(args), cwd=cwd, timeout=timeout)
    return GitResult(success=r.success, output=(r.output or ""), args=tuple(args))


def _run(git_run: Optional[GitRun], args: list[str], cwd: str, timeout: int = 120) -> GitResult:
    return (git_run or default_git_run)(args, cwd, timeout)


# ==========================================================================
# Part 1 — conflict text analysis (pure functions, no git, no I/O)
# ==========================================================================

@dataclass
class ConflictHunk:
    """One ``<<<<<<< / ======= / >>>>>>>`` region of a conflicted file."""
    ours: str
    theirs: str
    base: Optional[str] = None
    start_line: int = 0
    end_line: int = 0
    ours_label: str = ""
    theirs_label: str = ""


@dataclass
class ConflictFileReport:
    path: str
    hunks: list = field(default_factory=list)     # list[dict] verdicts
    resolved_text: Optional[str] = None
    verdict: str = SEMANTIC
    reason: str = ""

    @property
    def trivial(self) -> bool:
        return self.verdict == TRIVIAL


def parse_conflict_hunks(text: str) -> tuple[list, list]:
    """Split ``text`` into (segments, hunks).

    ``segments`` is the file with each conflict replaced by a ``ConflictHunk``
    placeholder, so a resolved file can be reassembled without disturbing a
    single byte of the non-conflicted content. Handles diff3-style conflicts
    (the ``|||||||`` base section is captured and otherwise ignored).
    """
    segments: list = []
    hunks: list = []
    literal: list[str] = []

    lines = text.split("\n")
    i = 0
    while i < len(lines):
        start = _CONFLICT_START.match(lines[i])
        if not start:
            literal.append(lines[i])
            i += 1
            continue

        ours: list[str] = []
        base: Optional[list[str]] = None
        theirs: list[str] = []
        theirs_label = ""
        section = "ours"
        start_line = i
        i += 1
        closed = False
        while i < len(lines):
            line = lines[i]
            if _CONFLICT_BASE.match(line):
                section, base = "base", []
                i += 1
                continue
            if _CONFLICT_SEP.match(line):
                section = "theirs"
                i += 1
                continue
            end = _CONFLICT_END.match(line)
            if end:
                theirs_label = (end.group("label") or "").strip()
                closed = True
                i += 1
                break
            {"ours": ours, "base": base if base is not None else [], "theirs": theirs}[section].append(line)
            i += 1

        if not closed:
            # Truncated/unterminated marker — not a conflict we understand.
            # Emit it verbatim as literal text so nothing is lost.
            literal.extend(lines[start_line:i])
            continue

        if literal:
            segments.append("\n".join(literal))
            literal = []
        hunk = ConflictHunk(
            ours="\n".join(ours),
            theirs="\n".join(theirs),
            base="\n".join(base) if base is not None else None,
            start_line=start_line,
            end_line=i - 1,
            ours_label=(start.group("label") or "").strip(),
            theirs_label=theirs_label,
        )
        segments.append(hunk)
        hunks.append(hunk)

    if literal:
        segments.append("\n".join(literal))
    return segments, hunks


# Line-comment markers per language. These must be exact: treating `--` as a
# comment in JavaScript would swallow the rest of `i--, j)` — including the
# closing bracket — and corrupt the bracket-depth used for line joining, which
# is what decides whether two sides are compared as the same logical lines.
# Likewise `#` opens a comment in Python but is a private field in TS/JS.
_LINE_COMMENTS = {
    ".py": ("#",),
    ".sql": ("--",),
    ".css": (),
    ".scss": ("//",),
    ".rs": ("//",),
    ".go": ("//",),
}
_DEFAULT_LINE_COMMENTS = ("//",)
# With no path to go on, assume both so a comment is never mistaken for code.
_UNKNOWN_LINE_COMMENTS = ("#", "//", "--")


def _line_comments_for(suffix: str) -> tuple:
    if not suffix:
        return _UNKNOWN_LINE_COMMENTS
    return _LINE_COMMENTS.get(suffix, _DEFAULT_LINE_COMMENTS)


def _scan(text: str, line_comments: tuple = _UNKNOWN_LINE_COMMENTS):
    """Tokenise ``text`` into ``(kind, chunk)`` pairs where kind is ``"code"``,
    ``"literal"`` (string/char literal) or ``"comment"``.

    Literals and comments are kept verbatim and atomic so whitespace *inside*
    them is never normalised away — ``"hello  world"`` and ``"hello world"``
    must never be judged equivalent, and neither must two different comments.
    Returns ``(tokens, spans_newline)``; ``spans_newline`` is True when a
    literal ran across a line break (a multi-line string), which makes
    line-oriented normalisation unsafe and forces a ``semantic`` verdict.
    """
    tokens: list[tuple[str, str]] = []
    spans_newline = False
    code: list[str] = []
    i, n = 0, len(text)

    def flush_code():
        if code:
            tokens.append(("code", "".join(code)))
            code.clear()

    while i < n:
        ch = text[i]
        # Line comments
        if any(text.startswith(marker, i) for marker in line_comments):
            flush_code()
            end = text.find("\n", i)
            end = n if end == -1 else end
            tokens.append(("comment", text[i:end]))
            i = end
            continue
        # Block comments
        if text.startswith("/*", i):
            flush_code()
            end = text.find("*/", i + 2)
            end = n if end == -1 else end + 2
            chunk = text[i:end]
            spans_newline = spans_newline or "\n" in chunk
            tokens.append(("comment", chunk))
            i = end
            continue
        # String / char literals, triple-quoted first
        if ch in "\"'`":
            flush_code()
            quote = text[i:i + 3] if text[i:i + 3] in ('"""', "'''") else ch
            j = i + len(quote)
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text.startswith(quote, j):
                    j += len(quote)
                    break
                j += 1
            else:
                j = n
            chunk = text[i:j]
            spans_newline = spans_newline or "\n" in chunk
            tokens.append(("literal", chunk))
            i = j
            continue
        code.append(ch)
        i += 1

    flush_code()
    return tokens, spans_newline


_WORD_RE = re.compile(r"\w")


def _squash_code_whitespace(code: str) -> str:
    """Drop whitespace from a code segment, keeping a single space only where it
    separates two word characters.

    Preserving that one case is what keeps ``not x`` distinct from ``notx`` —
    stripping whitespace outright would let two genuinely different expressions
    normalise to the same string.
    """
    out: list[str] = []
    i, n = 0, len(code)
    while i < n:
        if code[i].isspace():
            j = i
            while j < n and code[j].isspace():
                j += 1
            prev = out[-1] if out else ""
            nxt = code[j] if j < n else ""
            if prev and nxt and _WORD_RE.match(prev) and _WORD_RE.match(nxt):
                out.append(" ")
            i = j
            continue
        out.append(code[i])
        i += 1
    return "".join(out)


def _bracket_depth_delta(tokens) -> int:
    depth = 0
    for kind, chunk in tokens:
        if kind != "code":
            continue
        for ch in chunk:
            if ch in "([{":
                depth += 1
            elif ch in ")]}":
                depth -= 1
    return depth


def _normalize_side(text: str, line_comments: tuple = _UNKNOWN_LINE_COMMENTS) -> Optional[list[tuple[str, str]]]:
    """Reduce one side of a conflict to ``[(indent, normalized_code)]`` logical
    lines, or ``None`` when the text cannot be normalised safely.

    Physical lines are joined only where the join happens *inside an open
    bracket* — mirroring Python's implicit line joining. That is precisely the
    "call wrapped across three lines" case, and it is what keeps this analysis
    safe for indentation-significant languages: a de-indented statement at
    bracket depth 0 stays its own logical line and its indentation is compared
    exactly, so moving ``do_b()`` in or out of an ``if`` body is never mistaken
    for a reformat.
    """
    if "\n" in text and _scan(text, line_comments)[1]:
        return None  # multi-line literal/comment — line-oriented analysis unsafe

    logical: list[tuple[str, str]] = []
    pending: list[str] = []
    indent = ""
    depth = 0
    for raw in text.split("\n"):
        stripped = raw.strip()
        if not stripped and depth <= 0:
            continue  # blank line between statements carries no meaning here
        if not pending:
            indent = raw[:len(raw) - len(raw.lstrip())]
        pending.append(stripped)
        depth += _bracket_depth_delta(_scan(stripped, line_comments)[0])
        if depth <= 0:
            joined = " ".join(p for p in pending if p)
            logical.append((indent, _normalize_tokens(joined, line_comments)))
            pending, depth = [], 0
    if pending:
        logical.append((indent, _normalize_tokens(" ".join(p for p in pending if p), line_comments)))
    return logical


def _normalize_tokens(line: str, line_comments: tuple = _UNKNOWN_LINE_COMMENTS) -> str:
    tokens, _ = _scan(line, line_comments)
    return "".join(
        _squash_code_whitespace(chunk) if kind == "code" else chunk
        for kind, chunk in tokens
    )


_TRAILING_COMMA_RE = re.compile(r",(?=[)\]}])")


def _drop_trailing_commas(normalized: str) -> str:
    return _TRAILING_COMMA_RE.sub("", normalized)


def auto_resolve_suffixes(cfg=None) -> tuple:
    """Suffixes eligible for auto-resolution (``GIT_TRIVIAL_CONFLICT_SUFFIXES``)."""
    configured = getattr(cfg, "git_trivial_conflict_suffixes", None) if cfg else None
    return tuple(configured) if configured else _DEFAULT_AUTO_RESOLVE_SUFFIXES


def auto_resolve_enabled(cfg=None) -> bool:
    """``GIT_AUTO_RESOLVE_TRIVIAL_CONFLICTS`` — off means every conflict, however
    trivial, waits for a human."""
    return bool(getattr(cfg, "git_auto_resolve_trivial_conflicts", True)) if cfg else True


def classify_conflict(ours: str, theirs: str, *, path: str = "", cfg=None) -> dict:
    """Classify one conflict hunk as ``trivial`` (whitespace/formatting only,
    identical semantics) or ``semantic`` (anything else).

    Returns ``{"verdict", "reason"}``. The bar for ``trivial`` is deliberately
    high — every uncertainty resolves to ``semantic``.
    """
    suffix = os.path.splitext(path or "")[1].lower()
    if path and suffix not in auto_resolve_suffixes(cfg):
        return {
            "verdict": SEMANTIC,
            "reason": f"file type '{suffix or path}' not eligible for auto-resolution",
        }

    if ours == theirs:
        return {"verdict": TRIVIAL, "reason": "sides are identical"}

    line_comments = _line_comments_for(suffix)
    left = _normalize_side(ours, line_comments)
    right = _normalize_side(theirs, line_comments)
    if left is None or right is None:
        return {"verdict": SEMANTIC, "reason": "multi-line string/comment — cannot normalise safely"}

    if left == right:
        return {"verdict": TRIVIAL, "reason": "identical after whitespace/line-wrap normalisation"}

    if len(left) != len(right):
        return {"verdict": SEMANTIC, "reason": f"different statement count ({len(left)} vs {len(right)})"}

    if [ind for ind, _ in left] != [ind for ind, _ in right]:
        return {"verdict": SEMANTIC, "reason": "indentation differs between sides"}

    if suffix in _TRAILING_COMMA_OK_SUFFIXES:
        if [(i, _drop_trailing_commas(c)) for i, c in left] == \
           [(i, _drop_trailing_commas(c)) for i, c in right]:
            return {
                "verdict": TRIVIAL,
                "reason": "identical after normalisation ignoring magic trailing comma",
            }

    return {"verdict": SEMANTIC, "reason": "code differs beyond formatting"}


def resolve_conflict_text(text: str, *, path: str = "", prefer: str = "ours", cfg=None) -> ConflictFileReport:
    """Attempt to resolve every conflict in one file's ``text``.

    ``prefer`` picks which side to keep for a trivial hunk — the two are
    semantically identical by construction, so this only decides formatting.
    Callers pass the side that corresponds to upstream for their operation
    (during a rebase HEAD/"ours" *is* upstream; during a merge of main into a
    branch, "theirs" is main), so the result converges on the base branch's
    formatting rather than re-introducing the branch's.

    A file resolves only when **every** hunk in it is trivial: a half-resolved
    file is worse than an untouched one.
    """
    segments, hunks = parse_conflict_hunks(text)
    report = ConflictFileReport(path=path)

    if not hunks:
        report.verdict = TRIVIAL
        report.reason = "no conflict markers"
        report.resolved_text = text
        return report

    for hunk in hunks:
        decision = classify_conflict(hunk.ours, hunk.theirs, path=path, cfg=cfg)
        report.hunks.append({
            "start_line": hunk.start_line,
            "end_line": hunk.end_line,
            **decision,
        })

    semantic = [h for h in report.hunks if h["verdict"] == SEMANTIC]
    if semantic:
        report.verdict = SEMANTIC
        report.reason = (
            f"{len(semantic)}/{len(report.hunks)} hunk(s) are semantic: "
            f"{semantic[0]['reason']} (line {semantic[0]['start_line'] + 1})"
        )
        return report

    rebuilt = []
    for seg in segments:
        if isinstance(seg, ConflictHunk):
            rebuilt.append(seg.ours if prefer == "ours" else seg.theirs)
        else:
            rebuilt.append(seg)
    report.verdict = TRIVIAL
    report.reason = f"all {len(report.hunks)} hunk(s) whitespace/formatting only"
    report.resolved_text = "\n".join(rebuilt)
    return report


# ==========================================================================
# Part 2 — scope enforcement
# ==========================================================================

def normalize_scope(allowed_scope) -> list[str]:
    """Coerce a task's ``acceptance_criteria.allowed_scope`` (list or
    comma-separated string) into a list of lowercase path fragments."""
    if not allowed_scope:
        return []
    if isinstance(allowed_scope, (list, tuple, set)):
        parts = [str(p).strip().lower() for p in allowed_scope]
    else:
        parts = [p.strip().lower() for p in str(allowed_scope).split(",")]
    return [p for p in parts if p]


def path_in_scope(path: str, allowed_paths) -> bool:
    """True when ``path`` falls inside the declared scope.

    An empty scope means "unrestricted" — the pre-existing behaviour for tasks
    that never declared one (matching ``independent_code_review``).
    """
    scope = normalize_scope(allowed_paths)
    if not scope:
        return True
    candidate = (path or "").strip().lower().lstrip("./")
    return any(candidate.startswith(s) or s in candidate for s in scope)


def scope_from_task(task: Optional[dict]) -> list[str]:
    ac = (task or {}).get("acceptance_criteria")
    if not isinstance(ac, dict):
        return []
    return normalize_scope(ac.get("allowed_scope"))


# ==========================================================================
# Part 3 — worktree safety: commit-or-stash before any checkout
# ==========================================================================

@dataclass
class WorkGuard:
    """Record of uncommitted work set aside before a branch operation."""
    action: str = "none"          # "none" | "stashed"
    stash_message: str = ""
    files: list = field(default_factory=list)
    restored: bool = False
    error: str = ""

    @property
    def has_stash(self) -> bool:
        return self.action == "stashed" and not self.restored


def worktree_files(repo_path: str, *, git_run: Optional[GitRun] = None) -> list[str]:
    """Paths with uncommitted changes, including untracked files."""
    r = _run(git_run, ["status", "--porcelain"], repo_path)
    if not r.success:
        return []
    paths = []
    for line in (r.output or "").splitlines():
        if len(line) > 3:
            entry = line[3:].strip()
            # Renames are reported as "old -> new"; the new path is what exists.
            paths.append(entry.split(" -> ")[-1].strip().strip('"'))
    return [p for p in paths if p]


def protect_uncommitted_work(
    repo_path: str, *, label: str = "runner", git_run: Optional[GitRun] = None,
) -> WorkGuard:
    """Stash any uncommitted work (including untracked files) before a branch
    operation touches the worktree.

    This is the direct fix for the M4b incident where a routine branch
    operation reverted uncommitted local doc edits. The stash is *labelled* so
    a human can find it, and it is never dropped by this module.
    """
    files = worktree_files(repo_path, git_run=git_run)
    if not files:
        return WorkGuard(action="none")

    message = f"runner-autonomy:{label}"
    r = _run(git_run, ["stash", "push", "--include-untracked", "-m", message], repo_path)
    if not r.success:
        log_event("git_work_protect_failed", {
            "repo_path": repo_path, "label": label,
            "files": files[:20], "output": (r.output or "")[-500:],
        })
        return WorkGuard(action="none", files=files, error=r.output or "stash failed")

    log_event("git_work_stashed", {
        "repo_path": repo_path, "label": label, "message": message, "files": files[:20],
    })
    return WorkGuard(action="stashed", stash_message=message, files=files)


def restore_protected_work(
    repo_path: str, guard: WorkGuard, *, git_run: Optional[GitRun] = None,
) -> WorkGuard:
    """Restore work set aside by ``protect_uncommitted_work``.

    On a conflicting pop the stash entry is **kept** (``git stash pop`` leaves
    it in place when it fails) and the failure is logged loudly. Losing the
    founder's edits is the one outcome this module must never produce, so an
    un-poppable stash is a reported problem, not a cleanup target.
    """
    if guard.action != "stashed" or guard.restored:
        return guard

    r = _run(git_run, ["stash", "pop"], repo_path)
    if r.success:
        guard.restored = True
        log_event("git_work_restored", {"repo_path": repo_path, "message": guard.stash_message})
        return guard

    guard.error = r.output or "stash pop failed"
    log_event("git_work_restore_failed", {
        "repo_path": repo_path,
        "message": guard.stash_message,
        "files": guard.files[:20],
        "output": guard.error[-500:],
        "recovery": f"work is preserved in the stash list as '{guard.stash_message}' — `git stash list` then `git stash pop`",
    })
    return guard


def safe_checkout(
    repo_path: str, branch: str, *, create: bool = False,
    label: str = "checkout", git_run: Optional[GitRun] = None,
) -> dict:
    """Check out ``branch`` after setting aside any uncommitted work.

    Returns ``{"success", "guard", "output"}``. The guard is returned rather
    than auto-popped: the caller decides when the worktree is back on the right
    branch for the stash to be restored onto.
    """
    guard = protect_uncommitted_work(repo_path, label=label, git_run=git_run)
    if guard.error:
        return {
            "success": False, "guard": guard,
            "output": f"refusing to checkout with unprotected local changes: {guard.error}",
        }

    args = ["checkout", "-b", branch] if create else ["checkout", branch]
    r = _run(git_run, args, repo_path)
    return {"success": r.success, "guard": guard, "output": r.output}


# ==========================================================================
# Part 4 — divergence handling: rebase, already-upstream drops, conflict triage
# ==========================================================================

def _is_already_upstream(output: str) -> bool:
    lowered = (output or "").lower()
    return any(marker in lowered for marker in _ALREADY_UPSTREAM_MARKERS)


def unmerged_paths(repo_path: str, *, git_run: Optional[GitRun] = None) -> list[str]:
    r = _run(git_run, ["diff", "--name-only", "--diff-filter=U"], repo_path)
    if not r.success:
        return []
    return [line.strip() for line in (r.output or "").splitlines() if line.strip()]


def auto_resolve_conflicts(
    repo_path: str, *,
    paths=None,
    allowed_paths=None,
    prefer: str = "ours",
    cfg=None,
    git_run: Optional[GitRun] = None,
    read_file: Optional[Callable[[str], str]] = None,
    write_file: Optional[Callable[[str, str], None]] = None,
) -> dict:
    """Resolve every conflicted file whose conflicts are purely formatting.

    ``paths`` is the conflicted file list; when omitted it is queried. Callers
    already holding the list (``rebase_onto``) pass it so the resolution acts on
    exactly the set of files they inspected.

    Returns ``{"resolved": [...], "escalated": [{path, reason}], "all_resolved":
    bool}``. Escalates — never guesses — when a conflicted file is outside
    ``allowed_paths``, is an ineligible file type, or contains any hunk whose
    two sides are not provably equivalent.
    """
    paths = list(paths) if paths is not None else unmerged_paths(repo_path, git_run=git_run)
    resolved: list[str] = []
    escalated: list[dict] = []

    _read = read_file or (lambda p: open(p, "r", encoding="utf-8").read())
    _write = write_file or (lambda p, t: open(p, "w", encoding="utf-8").write(t))

    for rel in paths:
        if not path_in_scope(rel, allowed_paths):
            escalated.append({
                "path": rel,
                "reason": "conflicted file is outside the task's declared scope",
            })
            continue

        full = os.path.join(repo_path, rel)
        try:
            text = _read(full)
        except Exception as e:
            escalated.append({"path": rel, "reason": f"unreadable: {e}"})
            continue

        report = resolve_conflict_text(text, path=rel, prefer=prefer, cfg=cfg)
        if not report.trivial or report.resolved_text is None:
            escalated.append({"path": rel, "reason": report.reason, "hunks": report.hunks})
            continue

        try:
            _write(full, report.resolved_text)
        except Exception as e:
            escalated.append({"path": rel, "reason": f"unwritable: {e}"})
            continue

        add = _run(git_run, ["add", "--", rel], repo_path)
        if not add.success:
            escalated.append({"path": rel, "reason": f"git add failed: {add.output[:200]}"})
            continue

        resolved.append(rel)
        log_event("git_conflict_auto_resolved", {
            "path": rel, "hunks": len(report.hunks), "reason": report.reason, "prefer": prefer,
        })

    if escalated:
        log_event("git_conflict_escalated", {
            "repo_path": repo_path,
            "escalated": [{"path": e["path"], "reason": e["reason"]} for e in escalated],
            "auto_resolved": resolved,
            "note": "semantic or out-of-scope conflict — left for a human",
        })

    return {
        "resolved": resolved,
        "escalated": escalated,
        "all_resolved": bool(paths) and not escalated,
        "conflicted": paths,
    }


def _abort_rebase(repo_path: str, git_run: Optional[GitRun]) -> None:
    _run(git_run, ["rebase", "--abort"], repo_path)


def rebase_onto(
    repo_path: str, upstream: str, *,
    allowed_paths=None,
    auto_resolve: bool = True,
    max_steps: int = 25,
    cfg=None,
    git_run: Optional[GitRun] = None,
    **resolve_kwargs,
) -> dict:
    """Rebase the current branch onto ``upstream``, driving it to completion.

    Handles the three states that stopped M4b's rebases dead:

    * **conflict** — trivial hunks are resolved and staged, then
      ``git rebase --continue``; a semantic or out-of-scope conflict aborts the
      whole rebase (leaving the branch exactly as it was) and escalates.
    * **already upstream** — the commit's content is present on ``upstream``
      already, so it is dropped with ``git rebase --skip`` rather than fought
      with. (The merge backend drops these itself; the apply backend stops with
      "No changes - did you forget to use 'git add'?" and needs the skip.)
    * **anything else** — abort and report, never leave a half-rebased branch.

    During a rebase HEAD is *upstream*, so trivial hunks keep the "ours" side —
    i.e. the base branch's formatting wins.
    """
    result = {
        "success": False, "rebased": False, "skipped_commits": 0,
        "resolved_files": [], "escalated": [], "steps": 0, "output": "",
    }
    outputs: list[str] = []

    r = _run(git_run, ["rebase", upstream], repo_path, timeout=300)
    outputs.append(r.output or "")

    for step in range(max_steps):
        result["steps"] = step + 1
        if r.success:
            result["success"] = True
            result["rebased"] = True
            break

        conflicts = unmerged_paths(repo_path, git_run=git_run)
        if conflicts:
            if not auto_resolve:
                _abort_rebase(repo_path, git_run)
                result["escalated"] = [{"path": p, "reason": "auto-resolution disabled"} for p in conflicts]
                result["reason"] = "conflicts_escalated"
                break
            resolution = auto_resolve_conflicts(
                repo_path, paths=conflicts, allowed_paths=allowed_paths, prefer="ours",
                cfg=cfg, git_run=git_run, **resolve_kwargs,
            )
            result["resolved_files"].extend(resolution["resolved"])
            if not resolution["all_resolved"]:
                _abort_rebase(repo_path, git_run)
                result["escalated"] = resolution["escalated"]
                result["reason"] = "conflicts_escalated"
                break
            r = _run(git_run, ["-c", "core.editor=true", "rebase", "--continue"], repo_path, timeout=300)
            outputs.append(r.output or "")
            continue

        if _is_already_upstream(r.output or ""):
            result["skipped_commits"] += 1
            log_event("git_rebase_skipped_upstream_commit", {
                "repo_path": repo_path, "upstream": upstream,
                "detail": "patch contents already upstream — commit dropped",
            })
            r = _run(git_run, ["rebase", "--skip"], repo_path, timeout=300)
            outputs.append(r.output or "")
            continue

        _abort_rebase(repo_path, git_run)
        result["reason"] = "rebase_failed"
        break
    else:
        _abort_rebase(repo_path, git_run)
        result["reason"] = "max_steps_exceeded"

    # A clean rebase whose commits were all already upstream still counts as
    # success — the branch is now exactly upstream, which is the goal.
    if result["success"] and _is_already_upstream("\n".join(outputs)) and not result["skipped_commits"]:
        result["skipped_commits"] = "\n".join(outputs).lower().count("skipped previously applied commit")

    result["output"] = "\n".join(o for o in outputs if o)[-4000:]
    log_event("git_rebase_completed" if result["success"] else "git_rebase_failed", {
        "repo_path": repo_path, "upstream": upstream,
        "success": result["success"], "steps": result["steps"],
        "skipped_commits": result["skipped_commits"],
        "resolved_files": result["resolved_files"],
        "escalated": [e["path"] for e in result["escalated"]],
        "reason": result.get("reason"),
    })
    return result


def sync_with_base(
    repo_path: str, *,
    base: str = "main",
    remote: str = "origin",
    allowed_paths=None,
    label: str = "sync",
    cfg=None,
    git_run: Optional[GitRun] = None,
    **resolve_kwargs,
) -> dict:
    """Bring the current branch up to date with ``remote/base``, rebase-first.

    Replaces the merge-based ``git pull origin main --no-edit``: a diverged
    local ``main`` used to need the founder to hand-choose rebase vs reset.
    Here rebase is always the choice, local commits already present upstream
    are dropped cleanly, and **nothing is ever reset or discarded** — on an
    unresolvable divergence the rebase aborts and the branch is left untouched
    for a human.

    Any uncommitted work is stashed first and restored afterwards.
    """
    guard = protect_uncommitted_work(repo_path, label=label, git_run=git_run)
    if guard.error:
        return {
            "success": False, "reason": "unprotected_local_changes",
            "guard": guard, "output": guard.error,
        }

    fetch = _run(git_run, ["fetch", remote], repo_path, timeout=300)
    if not fetch.success:
        restore_protected_work(repo_path, guard, git_run=git_run)
        return {"success": False, "reason": "fetch_failed", "guard": guard, "output": fetch.output}

    rebase = rebase_onto(
        repo_path, f"{remote}/{base}",
        allowed_paths=allowed_paths, auto_resolve=auto_resolve_enabled(cfg),
        cfg=cfg, git_run=git_run, **resolve_kwargs,
    )
    restore_protected_work(repo_path, guard, git_run=git_run)

    return {
        "success": rebase["success"],
        "reason": rebase.get("reason"),
        "skipped_commits": rebase["skipped_commits"],
        "resolved_files": rebase["resolved_files"],
        "escalated": rebase["escalated"],
        "guard": guard,
        "stash_stranded": guard.has_stash,
        "output": rebase["output"],
    }


# ==========================================================================
# Part 5 — waking a PR whose checks were never scheduled
# ==========================================================================

# Ordered ladder, cheapest and least invasive first. ``rebase`` is inert unless
# GIT_ALLOW_FORCE_WITH_LEASE is on (see the module docstring): rebasing an
# already-pushed branch rewrites it, and AGENTS.md forbids force pushes. The
# other two rungs reach the same end state — a fresh head SHA on top of latest
# main — without rewriting anything, which is also exactly what GitHub's own
# "Update branch" button does.
DEFAULT_WAKE_STRATEGIES = ("update_branch", "rebase", "merge_base", "empty_commit")


def _branch_needs_force_push(repo_path: str, branch: str, remote: str, git_run) -> bool:
    """True when ``remote/branch`` is not an ancestor of the local branch — i.e.
    a push would be rejected as non-fast-forward."""
    r = _run(git_run, ["merge-base", "--is-ancestor", f"{remote}/{branch}", branch], repo_path)
    return not r.success


def wake_pr_checks(
    repo_path: str,
    branch: str, *,
    base: str = "main",
    remote: str = "origin",
    github_repo: Optional[str] = None,
    pr_number: Optional[int] = None,
    token: Optional[str] = None,
    allowed_paths=None,
    strategies=None,
    allow_force_with_lease: bool = False,
    cfg=None,
    git_run: Optional[GitRun] = None,
    update_branch: Optional[Callable[..., bool]] = None,
    **resolve_kwargs,
) -> dict:
    """Push a fresh head SHA so GitHub Actions schedules check runs for a PR
    that reported none.

    Tries each strategy in order until one reports it moved the branch:

    ``update_branch``  GitHub's update-branch API (no local git, no rewrite).
    ``rebase``         rebase onto ``remote/base`` + ``--force-with-lease``
                       push; skipped unless ``allow_force_with_lease``.
                       ``--force-with-lease`` refuses if origin moved since our
                       fetch, so a human's push to the branch is never clobbered.
    ``merge_base``     merge ``remote/base`` into the branch and push normally —
                       same end state as a rebase, no history rewritten.
    ``empty_commit``   last resort: an empty commit purely to change the head SHA.

    Refuses outright on a protected branch.
    """
    if branch.lower() in _PROTECTED_BRANCHES:
        return {"success": False, "reason": f"refusing to wake checks on protected branch '{branch}'", "attempts": []}

    # Every local rung (rebase, merge, empty commit) acts on whatever HEAD is,
    # so a mismatch would rewrite an unrelated branch. Found the hard way: with
    # this guard absent, a test run drove the ladder against the wrong checkout
    # and put three empty commits on it. Verify, never assume.
    head = _run(git_run, ["branch", "--show-current"], repo_path).output.strip()
    if head != branch:
        log_event("pr_checks_wake_wrong_branch", {
            "repo_path": repo_path, "expected": branch, "head": head,
        })
        return {
            "success": False,
            "reason": f"refusing to wake checks: HEAD is on '{head}', not '{branch}'",
            "attempts": [],
        }

    ladder = tuple(strategies or DEFAULT_WAKE_STRATEGIES)
    attempts: list[dict] = []

    guard = protect_uncommitted_work(repo_path, label=f"wake-checks:{branch}", git_run=git_run)
    if guard.error:
        return {
            "success": False, "reason": "unprotected_local_changes",
            "attempts": attempts, "guard": guard,
        }

    try:
        for strategy in ladder:
            outcome = _run_wake_strategy(
                strategy, repo_path, branch,
                base=base, remote=remote, github_repo=github_repo, pr_number=pr_number,
                token=token, allowed_paths=allowed_paths,
                allow_force_with_lease=allow_force_with_lease,
                cfg=cfg, git_run=git_run, update_branch=update_branch, **resolve_kwargs
            )
            attempts.append(outcome)
            log_event("pr_checks_wake_attempt", {
                "repo": github_repo, "pr_number": pr_number, "branch": branch, **outcome,
            })
            if outcome.get("success"):
                return {"success": True, "strategy": strategy, "attempts": attempts, "guard": guard}
    finally:
        restore_protected_work(repo_path, guard, git_run=git_run)

    log_event("pr_checks_wake_exhausted", {
        "repo": github_repo, "pr_number": pr_number, "branch": branch,
        "strategies": list(ladder),
        "attempts": [{"strategy": a["strategy"], "reason": a.get("reason")} for a in attempts],
    })
    return {"success": False, "reason": "wake_strategies_exhausted", "attempts": attempts, "guard": guard}


def _run_wake_strategy(
    strategy: str, repo_path: str, branch: str, *,
    base: str, remote: str, github_repo, pr_number, token, allowed_paths,
    allow_force_with_lease: bool, cfg, git_run, update_branch, **resolve_kwargs
) -> dict:
    out = {"strategy": strategy, "success": False}

    if strategy == "update_branch":
        if not (github_repo and pr_number):
            return {**out, "reason": "no repo/pr_number for update-branch API"}
        updater = update_branch
        if updater is None:
            from tools.github_tools import _update_pr_branch as updater  # noqa: N813
        ok = bool(updater(github_repo, pr_number, token))
        return {**out, "success": ok, "reason": None if ok else "update-branch API declined (branch not behind)"}

    if strategy == "rebase":
        if not allow_force_with_lease:
            return {**out, "reason": "rebase rung disabled: GIT_ALLOW_FORCE_WITH_LEASE is off"}
        fetch = _run(git_run, ["fetch", remote], repo_path, timeout=300)
        if not fetch.success:
            return {**out, "reason": f"fetch failed: {fetch.output[:200]}"}
        rebase = rebase_onto(
            repo_path, f"{remote}/{base}", allowed_paths=allowed_paths,
            auto_resolve=auto_resolve_enabled(cfg), cfg=cfg, git_run=git_run,
            **resolve_kwargs,
        )
        if not rebase["success"]:
            return {**out, "reason": f"rebase not completed: {rebase.get('reason')}",
                    "escalated": [e["path"] for e in rebase["escalated"]]}
        push = _run(git_run, ["push", "--force-with-lease", remote, branch], repo_path, timeout=300)
        if not push.success:
            # --force-with-lease refused: origin moved since our fetch, which
            # means someone else pushed. Never escalate to a real force push.
            return {**out, "reason": f"force-with-lease push refused (origin moved): {push.output[:200]}"}
        return {**out, "success": True}

    if strategy == "merge_base":
        fetch = _run(git_run, ["fetch", remote], repo_path, timeout=300)
        if not fetch.success:
            return {**out, "reason": f"fetch failed: {fetch.output[:200]}"}
        merge = _run(
            git_run,
            ["-c", "core.editor=true", "merge", "--no-edit", f"{remote}/{base}"],
            repo_path, timeout=300,
        )
        if not merge.success:
            if not auto_resolve_enabled(cfg):
                _run(git_run, ["merge", "--abort"], repo_path)
                return {**out, "reason": "merge conflicted and auto-resolution is disabled"}
            resolution = auto_resolve_conflicts(
                repo_path, allowed_paths=allowed_paths, prefer="theirs",
                cfg=cfg, git_run=git_run, **resolve_kwargs,
            )
            if not resolution["all_resolved"]:
                _run(git_run, ["merge", "--abort"], repo_path)
                return {**out, "reason": "merge conflicts require a human",
                        "escalated": [e["path"] for e in resolution["escalated"]]}
            commit = _run(git_run, ["-c", "core.editor=true", "commit", "--no-edit"], repo_path)
            if not commit.success:
                _run(git_run, ["merge", "--abort"], repo_path)
                return {**out, "reason": f"merge commit failed: {commit.output[:200]}"}
        if "already up to date" in (merge.output or "").lower():
            return {**out, "reason": "branch already contains latest base — nothing to push"}
        if _branch_needs_force_push(repo_path, branch, remote, git_run):
            return {**out, "reason": "push would not fast-forward; refusing to force"}
        push = _run(git_run, ["push", remote, branch], repo_path, timeout=300)
        return {**out, "success": push.success,
                "reason": None if push.success else f"push failed: {push.output[:200]}"}

    if strategy == "empty_commit":
        commit = _run(
            git_run,
            ["commit", "--allow-empty", "-m", f"chore: re-trigger checks for {branch}"],
            repo_path,
        )
        if not commit.success:
            return {**out, "reason": f"empty commit failed: {commit.output[:200]}"}
        push = _run(git_run, ["push", remote, branch], repo_path, timeout=300)
        return {**out, "success": push.success,
                "reason": None if push.success else f"push failed: {push.output[:200]}"}

    return {**out, "reason": f"unknown wake strategy '{strategy}'"}
