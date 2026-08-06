"""Crash-safe WIP checkpointing — work in the working tree is work that can vanish (M4c.4).

THE INCIDENT: m4c-03 was implemented and then halted by a guard before the
commit step — three separate times. 1,552 lines of finished work
(``tools/state_self_healing.py``, its tests, and edits across 11 files) sat
uncommitted for days and were only recovered because the founder happened to
run ``git status`` and recognise them. Nothing in the runner noticed. Any of the
intervening ``git checkout`` operations could have destroyed the lot — and a
worker's routine branch operation did exactly that to founder doc edits during
M4b.

THE RULE: every exit path checkpoints first. Ctrl+C, SIGTERM from a watchdog, a
guard setting a stop reason, an unhandled exception — each one commits whatever
is dirty to the current task's branch under a clearly-marked WIP message and
pushes it if a remote exists, so recovery is one ``git checkout <sha>`` away.

Four entry points, one commit path:

  - ``install_checkpoint_handlers`` — SIGINT/SIGTERM handlers plus an atexit
    hook for the run-loop process (``main.py``).
  - ``checkpoint_wip`` — the commit path itself; also called directly by
    ``graph.decide_continue_or_stop`` the moment a guard sets a stop reason, so
    the work is safe before the loop unwinds rather than after.
  - ``detect_wip_checkpoint`` — on startup, find a WIP commit already on the
    task's branch.
  - ``format_wip_prompt_notice`` — tell the worker about it, so a resumed task
    continues the partial work instead of restarting it.

Safety, in order of how badly each would end:

  - **Never onto a protected branch.** A protected or detached HEAD redirects
    to ``wip/<task-id>``; the checkpoint is abandoned rather than committed to
    ``main`` if that redirect fails.
  - **Never outside the repo.** The add is ``git add -A -- .`` from the repo
    root, so the pathspec cannot reach above it.
  - **Never force-push.** A rejected push is reported, never forced.
  - **Never block the exit.** Every failure here is caught, logged loudly
    (``wip_checkpoint_failed`` reaches Slack), and returned as data. A failed
    checkpoint must not stop a clean shutdown — that would trade the work we
    could not save for the shutdown we could.

Every git call goes through an injectable ``git_run`` (``tools.git_autonomy``),
so the tests exercise all of this without touching a real repository.
"""
from __future__ import annotations

import atexit
import re
import signal
import sys
from dataclasses import dataclass
from datetime import datetime
from typing import Callable, Optional

from tools.git_autonomy import GitRun, default_git_run, worktree_files
from tools.log_tools import log_event

# Kept local rather than imported from git_tools: this module must stay usable
# from a signal handler, where importing a module that pulls in the whole graph
# is a way to fail at the worst possible moment.
PROTECTED_BRANCHES = frozenset({"main", "master", "dev", "develop", "production", "release"})

#: Every checkpoint commit subject starts with this, which is what makes them
#: findable on startup and unmistakable in ``git log``.
WIP_SUBJECT_PREFIX = "WIP checkpoint"

WIP_BRANCH_PREFIX = "wip/"

CHECKPOINT_EVENT = "wip_checkpointed"
CHECKPOINT_FAILED_EVENT = "wip_checkpoint_failed"
CHECKPOINT_SKIPPED_EVENT = "wip_checkpoint_skipped"
DETECTED_EVENT = "wip_checkpoint_detected"

#: ``git branch --show-current`` returns "" on a detached HEAD; ``git_tools``
#: returns "unknown" when the call fails outright. Neither is a branch we may
#: commit onto blind.
_UNRESOLVED_BRANCHES = frozenset({"", "unknown", "head"})

#: Paths listed in the log event and the commit body. The full count is always
#: reported; the list is capped so one enormous checkpoint cannot bloat every
#: consumer of the flight recorder.
MAX_LISTED_FILES = 40

_SLUG_RE = re.compile(r"[^A-Za-z0-9._-]+")

# Re-entrancy guard. A SIGTERM arriving while the atexit hook is mid-commit
# would otherwise start a second `git add`/`git commit` on the same tree.
_in_progress = False

_handlers_installed = False


# ---------------------------------------------------------------------------
# Pure helpers
# ---------------------------------------------------------------------------

def slugify_task_id(task_id: Optional[str]) -> str:
    """Return *task_id* reduced to something safe as a git ref component."""
    slug = _SLUG_RE.sub("-", str(task_id or "").strip()).strip("-./")
    return slug or "unknown-task"


def wip_branch_for(task_id: Optional[str]) -> str:
    return f"{WIP_BRANCH_PREFIX}{slugify_task_id(task_id)}"


def resolve_checkpoint_branch(current_branch: Optional[str], task_id: Optional[str]) -> dict:
    """Decide which branch this checkpoint may land on.

    Returns ``{"branch", "redirected", "reason", "current"}``. A protected
    branch or an unresolvable HEAD redirects to ``wip/<task-id>``: the whole
    point of the checkpoint is to not lose work, and committing overnight work
    onto ``main`` would be its own incident.
    """
    current = (current_branch or "").strip()
    lowered = current.lower()

    if lowered in _UNRESOLVED_BRANCHES:
        return {
            "branch": wip_branch_for(task_id),
            "redirected": True,
            "reason": "unresolved_branch",
            "current": current,
        }
    if lowered in PROTECTED_BRANCHES:
        return {
            "branch": wip_branch_for(task_id),
            "redirected": True,
            "reason": "protected_branch",
            "current": current,
        }
    return {"branch": current, "redirected": False, "reason": "", "current": current}


def format_checkpoint_message(
    *,
    task_id: Optional[str],
    stop_reason: Optional[str],
    trigger: str,
    branch: str,
    files: list,
    timestamp: Optional[str] = None,
) -> str:
    """Build the commit message. The subject alone has to be enough for a human
    scanning ``git log`` to know this is unfinished, automatic, and whose."""
    timestamp = timestamp or datetime.utcnow().isoformat()
    reason = stop_reason or trigger or "process_exit"
    subject = f"{WIP_SUBJECT_PREFIX} [{task_id or 'no-task'}]: {reason} @ {timestamp}"

    listed = files[:MAX_LISTED_FILES]
    body = [
        "",
        "Automatic checkpoint of an uncommitted working tree, written by the",
        "runner on its way out. This work is UNFINISHED and unreviewed — it has",
        "not passed scripts/check.sh and was never intended as a landed commit.",
        "",
        f"Task        : {task_id or 'none'}",
        f"Stop reason : {stop_reason or 'none (exited without one)'}",
        f"Trigger     : {trigger}",
        f"Branch      : {branch}",
        f"Files       : {len(files)}",
    ]
    body.extend(f"  - {path}" for path in listed)
    if len(files) > len(listed):
        body.append(f"  ... and {len(files) - len(listed)} more")
    body.extend([
        "",
        "To continue this work, check the branch out and build on it — do not",
        "restart the task from scratch.",
    ])
    return subject + "\n" + "\n".join(body) + "\n"


def format_wip_prompt_notice(detection: dict) -> str:
    """Render the block injected into a worker prompt when partial work exists.

    Silent when nothing was found, so callers can concatenate unconditionally.
    """
    if not (detection or {}).get("found"):
        return ""

    files = detection.get("files") or []
    listed = files[:MAX_LISTED_FILES]
    lines = [
        "PARTIAL WORK ALREADY EXISTS ON THIS BRANCH — CONTINUE IT, DO NOT RESTART.",
        "",
        f"A previous attempt at this task was interrupted before it could finish, and the",
        f"runner checkpointed its unfinished working tree to branch "
        f"'{detection.get('branch')}' as commit {detection.get('short_sha') or detection.get('sha')}",
        f"({detection.get('committed_at') or 'unknown time'}).",
        "",
        f"Commit subject: {detection.get('subject', '')}",
    ]
    if listed:
        lines.append(f"Files in that checkpoint ({len(files)}):")
        lines.extend(f"  - {path}" for path in listed)
        if len(files) > len(listed):
            lines.append(f"  ... and {len(files) - len(listed)} more")
    lines.extend([
        "",
        "That work is already in the branch's history — read it first (`git show "
        f"{detection.get('short_sha') or detection.get('sha')}`), verify what is done, and",
        "finish what remains. Re-implementing from scratch discards it and is the",
        "failure this checkpoint exists to prevent. The checkpoint was never checked",
        "or reviewed, so treat it as a draft to complete, not as verified work.",
        "",
    ])
    return "\n".join(lines) + "\n"


# ---------------------------------------------------------------------------
# Git plumbing
# ---------------------------------------------------------------------------

def _run(git_run: Optional[GitRun], args: list, cwd: str, timeout: int = 120):
    return (git_run or default_git_run)(args, cwd, timeout)


def _current_branch(repo_path: str, git_run: Optional[GitRun]) -> str:
    r = _run(git_run, ["branch", "--show-current"], repo_path, 30)
    return (r.output or "").strip() if r.success else ""


def _branch_exists(repo_path: str, branch: str, git_run: Optional[GitRun]) -> bool:
    r = _run(git_run, ["rev-parse", "--verify", f"refs/heads/{branch}"], repo_path, 30)
    return bool(r.success)


def _has_origin(repo_path: str, git_run: Optional[GitRun]) -> bool:
    r = _run(git_run, ["remote", "get-url", "origin"], repo_path, 30)
    return bool(r.success and (r.output or "").strip())


def _blank_result(**overrides) -> dict:
    result = {
        "checkpointed": False,
        "reason": "",
        "branch": "",
        "redirected": False,
        "sha": "",
        "short_sha": "",
        "files": [],
        "file_count": 0,
        "pushed": False,
        "push_error": "",
        "error": "",
        "trigger": "",
        "task_id": None,
        "stop_reason": None,
        "committed_at": "",
    }
    result.update(overrides)
    return result


def checkpoint_wip(
    repo_path: str,
    *,
    task_id: Optional[str] = None,
    stop_reason: Optional[str] = None,
    trigger: str = "unknown",
    push: bool = True,
    git_run: Optional[GitRun] = None,
    now: Optional[Callable[[], datetime]] = None,
) -> dict:
    """Commit whatever is dirty in *repo_path* under a marked WIP message.

    Returns the outcome as a dict (see ``_blank_result`` for the shape) and
    **never raises**: this runs on the way out of the process, and an exception
    here would replace "we could not save the work" with "we could not shut
    down either".

    A clean tree is a no-op — the common case on a healthy stop, and the reason
    this is safe to call from several exit paths at once.
    """
    global _in_progress

    base = _blank_result(trigger=trigger, task_id=task_id, stop_reason=stop_reason)

    if _in_progress:
        # Another exit path is already committing this tree.
        return _blank_result(**{**base, "reason": "already_in_progress"})

    _in_progress = True
    try:
        return _checkpoint_wip(
            repo_path,
            base=base,
            task_id=task_id,
            stop_reason=stop_reason,
            trigger=trigger,
            push=push,
            git_run=git_run,
            now=now,
        )
    except Exception as e:  # pragma: no cover - defensive; the point is to never raise
        result = _blank_result(**{**base, "reason": "exception", "error": f"{type(e).__name__}: {e}"})
        _log_failure(repo_path, result)
        return result
    finally:
        _in_progress = False


def _checkpoint_wip(
    repo_path: str,
    *,
    base: dict,
    task_id: Optional[str],
    stop_reason: Optional[str],
    trigger: str,
    push: bool,
    git_run: Optional[GitRun],
    now: Optional[Callable[[], datetime]],
) -> dict:
    if not repo_path:
        result = _blank_result(**{**base, "reason": "no_repo_path", "error": "no repo_path given"})
        _log_failure(repo_path, result)
        return result

    files = worktree_files(repo_path, git_run=git_run)
    if not files:
        log_event(CHECKPOINT_SKIPPED_EVENT, {
            "reason": "clean_tree",
            "trigger": trigger,
            "task_id": task_id,
            "stop_reason": stop_reason,
            "repo_path": repo_path,
        }, task_id=task_id)
        return _blank_result(**{**base, "reason": "clean_tree"})

    base = {**base, "files": files[:MAX_LISTED_FILES], "file_count": len(files)}

    resolved = resolve_checkpoint_branch(_current_branch(repo_path, git_run), task_id)
    branch = resolved["branch"]
    base = {**base, "branch": branch, "redirected": resolved["redirected"]}

    if resolved["redirected"]:
        create = not _branch_exists(repo_path, branch, git_run)
        args = ["checkout", "-b", branch] if create else ["checkout", branch]
        checkout = _run(git_run, args, repo_path)
        if not checkout.success:
            # Falling back to the current branch would mean committing to a
            # protected branch, which is the one thing this must not do.
            result = _blank_result(**{
                **base,
                "reason": "redirect_failed",
                "error": (
                    f"cannot move off protected/unresolved branch "
                    f"'{resolved['current'] or 'detached HEAD'}' onto {branch}: "
                    f"{(checkout.output or '')[-300:]}"
                ),
            })
            _log_failure(repo_path, result)
            return result

    # `-- .` anchors the pathspec at the repo root: git cannot be talked into
    # staging anything above it.
    add = _run(git_run, ["add", "-A", "--", "."], repo_path)
    if not add.success:
        result = _blank_result(**{
            **base, "reason": "add_failed", "error": (add.output or "")[-300:],
        })
        _log_failure(repo_path, result)
        return result

    timestamp = (now() if now else datetime.utcnow()).isoformat()
    message = format_checkpoint_message(
        task_id=task_id,
        stop_reason=stop_reason,
        trigger=trigger,
        branch=branch,
        files=files,
        timestamp=timestamp,
    )

    # No --no-verify: hooks exist for a reason (AGENTS.md), and a hook that
    # refuses the commit is reported like any other failure rather than
    # bypassed.
    commit = _run(git_run, ["commit", "-m", message], repo_path)
    if not commit.success:
        output = (commit.output or "").lower()
        if "nothing to commit" in output or "nothing added to commit" in output:
            # Everything dirty was ignored (e.g. only .runtime/ changed).
            log_event(CHECKPOINT_SKIPPED_EVENT, {
                "reason": "nothing_to_commit",
                "trigger": trigger,
                "task_id": task_id,
                "stop_reason": stop_reason,
                "repo_path": repo_path,
            }, task_id=task_id)
            return _blank_result(**{**base, "reason": "nothing_to_commit"})
        result = _blank_result(**{
            **base, "reason": "commit_failed", "error": (commit.output or "")[-300:],
        })
        _log_failure(repo_path, result)
        return result

    rev = _run(git_run, ["rev-parse", "HEAD"], repo_path, 30)
    sha = (rev.output or "").strip() if rev.success else ""

    result = _blank_result(**{
        **base,
        "checkpointed": True,
        "reason": "committed",
        "sha": sha,
        "short_sha": sha[:12],
        "committed_at": timestamp,
    })

    if push and _has_origin(repo_path, git_run):
        # Plain push, never --force / --force-with-lease: a rejected push means
        # the remote has something this checkpoint does not, and overwriting it
        # would destroy work in exactly the way this module exists to prevent.
        pushed = _run(git_run, ["push", "-u", "origin", branch], repo_path)
        result["pushed"] = bool(pushed.success)
        if not pushed.success:
            result["push_error"] = (pushed.output or "")[-300:]

    log_event(CHECKPOINT_EVENT, {
        "sha": result["sha"],
        "short_sha": result["short_sha"],
        "branch": branch,
        "redirected": result["redirected"],
        "files": result["files"],
        "file_count": result["file_count"],
        "pushed": result["pushed"],
        "push_error": result["push_error"],
        "trigger": trigger,
        "stop_reason": stop_reason,
        "task_id": task_id,
        "repo_path": repo_path,
        "recover_with": f"git -C {repo_path} checkout {result['short_sha'] or branch}",
    }, task_id=task_id)
    return result


def _log_failure(repo_path: str, result: dict) -> None:
    """Loud, never fatal. This event is in the default Slack fan-out because a
    checkpoint that did not happen is the exact condition nobody noticed for
    days during the m4c-03 incident."""
    log_event(CHECKPOINT_FAILED_EVENT, {
        "reason": result.get("reason"),
        "error": result.get("error"),
        "branch": result.get("branch"),
        "files": result.get("files"),
        "file_count": result.get("file_count"),
        "trigger": result.get("trigger"),
        "stop_reason": result.get("stop_reason"),
        "task_id": result.get("task_id"),
        "repo_path": repo_path,
        "message": (
            f"WIP checkpoint FAILED ({result.get('reason')}) — "
            f"{result.get('file_count', 0)} uncommitted file(s) are still only in the "
            f"working tree at {repo_path}. Commit them by hand before any branch "
            f"operation touches that repo."
        ),
    }, task_id=result.get("task_id"))


# ---------------------------------------------------------------------------
# Startup detection
# ---------------------------------------------------------------------------

_LOG_SEPARATOR = "\x1f"


def detect_wip_checkpoint(
    repo_path: str,
    branch: Optional[str],
    *,
    git_run: Optional[GitRun] = None,
    limit: int = 20,
) -> dict:
    """Find the most recent WIP checkpoint commit on *branch*.

    Returns ``{"found", "branch", "sha", "short_sha", "subject",
    "committed_at", "files", "commits_since"}``. ``commits_since`` is how many
    commits sit on top of the checkpoint — 0 means it is the branch tip and
    nothing has been built on it yet.

    Never raises: a missing branch, a repo without history, or a git failure
    all read as "no checkpoint found", because this only ever adds context to a
    prompt and must not be able to stop a task from being dispatched.
    """
    empty = {
        "found": False, "branch": branch or "", "sha": "", "short_sha": "",
        "subject": "", "committed_at": "", "files": [], "commits_since": 0,
    }
    if not repo_path or not branch:
        return empty

    try:
        log = _run(
            git_run,
            ["log", branch, f"-n{limit}", f"--format=%H{_LOG_SEPARATOR}%s{_LOG_SEPARATOR}%cI"],
            repo_path,
            60,
        )
        if not log.success:
            return empty

        for index, line in enumerate((log.output or "").splitlines()):
            parts = line.split(_LOG_SEPARATOR)
            if len(parts) < 2:
                continue
            sha, subject = parts[0].strip(), parts[1].strip()
            if not subject.startswith(WIP_SUBJECT_PREFIX):
                continue
            committed_at = parts[2].strip() if len(parts) > 2 else ""
            files = _commit_files(repo_path, sha, git_run)
            return {
                "found": True,
                "branch": branch,
                "sha": sha,
                "short_sha": sha[:12],
                "subject": subject,
                "committed_at": committed_at,
                "files": files,
                "commits_since": index,
            }
    except Exception:
        return empty
    return empty


def _commit_files(repo_path: str, sha: str, git_run: Optional[GitRun]) -> list:
    r = _run(git_run, ["show", "--name-only", "--format=", sha], repo_path, 60)
    if not r.success:
        return []
    return [line.strip() for line in (r.output or "").splitlines() if line.strip()]


# ---------------------------------------------------------------------------
# Exit-path handlers
# ---------------------------------------------------------------------------

@dataclass
class CheckpointContext:
    """What the exit paths need to know about the run they are interrupting.

    Supplied by a callable rather than captured once, because the task and
    branch change under the loop's feet and a signal can arrive at any point.
    """
    repo_path: str
    task_id: Optional[str] = None
    stop_reason: Optional[str] = None

    @classmethod
    def from_any(cls, value) -> "CheckpointContext":
        if isinstance(value, cls):
            return value
        data = value or {}
        return cls(
            repo_path=data.get("repo_path") or "",
            task_id=data.get("task_id"),
            stop_reason=data.get("stop_reason"),
        )


def install_checkpoint_handlers(
    context_fn: Callable[[], object],
    *,
    checkpoint: Callable[..., dict] = checkpoint_wip,
    push: bool = True,
    signal_module=signal,
    atexit_register: Callable = atexit.register,
    exit_fn: Callable[[int], None] = sys.exit,
    force: bool = False,
) -> dict:
    """Install SIGINT/SIGTERM handlers and an atexit hook that checkpoint first.

    ``context_fn`` is called at exit time and returns a ``CheckpointContext``
    (or a plain dict with the same keys) describing the task in flight.

    The handlers preserve the exit they intercepted: SIGINT still raises
    ``KeyboardInterrupt`` so ``cmd_run_loop``'s existing handling is unchanged,
    and SIGTERM still exits ``128 + signum``, which lets the atexit hook run.
    The atexit hook covers what no signal does — an unhandled exception, a
    guard-driven ``sys.exit``, or a normal return — and is a no-op when an
    earlier path already committed the tree.

    SIGKILL cannot be caught; nothing here can save work from one.

    Returns ``{"signals": [...], "atexit": bool, "already_installed": bool}``.
    ``signal_module``/``atexit_register``/``exit_fn`` are injectable so the
    tests can fire the handlers without touching the pytest process.
    """
    global _handlers_installed

    if _handlers_installed and not force:
        return {"signals": [], "atexit": False, "already_installed": True}

    def _run_checkpoint(trigger: str, stop_reason: Optional[str] = None) -> dict:
        try:
            ctx = CheckpointContext.from_any(context_fn())
        except Exception as e:  # a broken context provider must not block exit
            log_event(CHECKPOINT_FAILED_EVENT, {
                "reason": "context_unavailable",
                "error": f"{type(e).__name__}: {e}",
                "trigger": trigger,
                "message": (
                    "WIP checkpoint could not run: the runner could not determine "
                    "which task/repo it was working on. Check `git status` by hand."
                ),
            })
            return _blank_result(reason="context_unavailable", trigger=trigger)
        return checkpoint(
            ctx.repo_path,
            task_id=ctx.task_id,
            stop_reason=stop_reason or ctx.stop_reason,
            trigger=trigger,
            push=push,
        )

    installed: list = []

    def _make_signal_handler(name: str):
        def _handler(signum, frame):  # noqa: ARG001 - signal API
            _run_checkpoint(f"signal:{name}", stop_reason=name.lower())
            if name == "SIGINT":
                raise KeyboardInterrupt
            exit_fn(128 + int(signum))
        return _handler

    for name in ("SIGINT", "SIGTERM"):
        signum = getattr(signal_module, name, None)
        if signum is None:
            continue
        try:
            signal_module.signal(signum, _make_signal_handler(name))
            installed.append(name)
        except (ValueError, OSError, RuntimeError) as e:
            # signal.signal only works in the main thread of the main
            # interpreter; a runner embedded elsewhere still gets the atexit
            # hook rather than nothing.
            log_event(CHECKPOINT_SKIPPED_EVENT, {
                "reason": "signal_unavailable",
                "signal": name,
                "error": f"{type(e).__name__}: {e}",
            })

    atexit_register(lambda: _run_checkpoint("atexit"))
    _handlers_installed = True

    log_event("wip_checkpoint_handlers_installed", {
        "signals": installed,
        "atexit": True,
        "push": push,
    })
    return {"signals": installed, "atexit": True, "already_installed": False}


def reset_handlers_for_tests() -> None:
    """Clear the install-once latch (tests only)."""
    global _handlers_installed, _in_progress
    _handlers_installed = False
    _in_progress = False
