"""Dispatch preflight checks — M4c.

Two independent guards that both exist because of the same M4b failure: the
runner dispatched a business task in a way that gave the worker no reliable
signal about *which repo it was standing in*, and the worker (correctly)
refused to act on an irreversible deploy it could not verify.

1. ``verify_origin_remote`` — before any business work begins, assert the
   workspace's ``origin`` actually points at the business's repo. A workspace
   that silently resolved to the wrong repo is the one failure mode where the
   worker cannot protect itself: every subsequent commit/push/deploy would go
   somewhere the founder did not authorise.

2. ``evaluate_loop_start`` — refuse to start the loop from a non-main branch or
   a dirty working tree. Observed 2026-08-02: the loop was started from
   ``fix/sandbox-config-edit`` with uncommitted changes, so workers inherited a
   tree that did not match ``main`` and could not tell intended state from
   in-flight edits.

Token safety: a business workspace's origin URL embeds a scoped GitHub token
(``https://x-access-token:<token>@github.com/owner/name.git`` — see
``foreign_repo_workspace.ensure_workspace``). Nothing in this module returns,
logs, or raises a raw remote URL; only the parsed ``owner/name`` ever escapes.
"""
import subprocess
from typing import Callable, Optional

# A loop may only start from one of these. "main" is the runner's own default
# branch; the rest are accepted only when explicitly configured by the caller.
DEFAULT_ALLOWED_START_BRANCHES = ("main",)


def parse_repo_full_name(remote_url: str) -> str:
    """Extract ``owner/name`` (lowercased) from a git remote URL.

    Handles the three forms the runner produces or encounters::

        https://x-access-token:TOKEN@github.com/owner/name.git
        https://github.com/owner/name
        git@github.com:owner/name.git

    Returns ``""`` when *remote_url* cannot be parsed. Credentials in the
    userinfo portion are discarded here and never returned — this function is
    the only place a credentialed URL is touched.
    """
    url = (remote_url or "").strip()
    if not url:
        return ""

    # Drop scheme and any userinfo (user:token@host) before splitting on host.
    if "://" in url:
        url = url.split("://", 1)[1]
    if "@" in url:
        url = url.rsplit("@", 1)[1]

    # scp-style (git@github.com:owner/name) uses ':' where https uses '/'.
    if ":" in url:
        host, _, rest = url.partition(":")
        path = rest
    elif "/" in url:
        _, _, path = url.partition("/")
    else:
        return ""

    path = path.strip("/")
    if path.endswith(".git"):
        path = path[: -len(".git")]

    parts = [p for p in path.split("/") if p]
    if len(parts) < 2:
        return ""
    # Take the last two segments so a self-hosted path prefix cannot break it.
    return "/".join(parts[-2:]).lower()


def _git_remote_url(repo_path: str, timeout: int = 30) -> dict:
    """Return ``{"success": bool, "url": str, "error": str}`` for origin.

    Deliberately does not use ``tools.shell_tools.run_command``: that helper
    logs raw command output on failure, and git echoes the credentialed clone
    URL in several of its error messages.
    """
    try:
        result = subprocess.run(
            ["git", "remote", "get-url", "origin"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return {"success": False, "url": "", "error": "timeout"}
    except Exception as e:  # missing git binary, bad cwd, ...
        return {"success": False, "url": "", "error": type(e).__name__}

    if result.returncode != 0:
        # stderr may name the repo path but never the token (git only echoes
        # the URL for *network* errors, not for `remote get-url`). Still, keep
        # the error opaque rather than forwarding git's text verbatim.
        return {"success": False, "url": "", "error": "no_origin_remote"}
    return {"success": True, "url": (result.stdout or "").strip(), "error": ""}


def verify_origin_remote(
    repo_path: str,
    expected_repo_full_name: str,
    git_remote_url: Optional[Callable[[str], dict]] = None,
) -> dict:
    """Assert *repo_path*'s ``origin`` resolves to *expected_repo_full_name*.

    Returns ``{"ok": bool, "reason": str, "expected": str, "actual": str}``.
    ``actual`` is always a parsed ``owner/name`` (or ``""``) — never a URL, so
    it is safe to log and to surface in outbox text.

    ``git_remote_url`` is injectable (``fn(repo_path) -> {"success", "url", ...}``)
    so tests can exercise this without a real repo or network.
    """
    expected = (expected_repo_full_name or "").strip().strip("/").lower()
    if not expected:
        return {"ok": False, "reason": "no_expected_repo", "expected": "", "actual": ""}

    fetch = (git_remote_url or _git_remote_url)(repo_path)
    if not fetch["success"]:
        return {
            "ok": False,
            "reason": fetch.get("error") or "remote_unavailable",
            "expected": expected,
            "actual": "",
        }

    actual = parse_repo_full_name(fetch["url"])
    if not actual:
        return {"ok": False, "reason": "unparseable_remote", "expected": expected, "actual": ""}
    if actual != expected:
        return {"ok": False, "reason": "remote_mismatch", "expected": expected, "actual": actual}
    return {"ok": True, "reason": "", "expected": expected, "actual": actual}


def check_loop_start_preconditions(
    branch: str,
    dirty: bool,
    allowed_branches: tuple = DEFAULT_ALLOWED_START_BRANCHES,
) -> dict:
    """Pure decision: may the loop start from this branch / tree state?

    Returns ``{"ok": bool, "reason": str, "branch": str, "dirty": bool,
    "message": str}``. Branch is checked before dirtiness so the operator gets
    the more fundamental problem first.
    """
    branch = (branch or "").strip()
    allowed = tuple(allowed_branches or DEFAULT_ALLOWED_START_BRANCHES)

    if branch not in allowed:
        return {
            "ok": False,
            "reason": "non_main_branch",
            "branch": branch,
            "dirty": dirty,
            "message": (
                f"refusing to start: on branch '{branch or 'unknown'}', "
                f"expected one of {', '.join(allowed)}. Workers inherit this "
                f"tree and cannot distinguish intended state from in-flight work."
            ),
        }

    if dirty:
        return {
            "ok": False,
            "reason": "dirty_working_tree",
            "branch": branch,
            "dirty": True,
            "message": (
                "refusing to start: uncommitted changes in the working tree. "
                "Commit or stash them so workers start from a known-good state."
            ),
        }

    return {"ok": True, "reason": "", "branch": branch, "dirty": False, "message": ""}


def evaluate_loop_start(
    repo_path: str,
    allowed_branches: tuple = DEFAULT_ALLOWED_START_BRANCHES,
    branch_fn: Optional[Callable[[str], str]] = None,
    status_fn: Optional[Callable[[str], dict]] = None,
) -> dict:
    """Gather live git state for *repo_path* and apply
    ``check_loop_start_preconditions``.

    ``branch_fn`` / ``status_fn`` default to ``tools.git_tools`` helpers and are
    injectable for tests.
    """
    if branch_fn is None or status_fn is None:
        from tools.git_tools import current_branch, get_git_status
        branch_fn = branch_fn or current_branch
        status_fn = status_fn or get_git_status

    branch = branch_fn(repo_path)
    status = status_fn(repo_path)

    # `git status --short --branch` always emits a leading "## <branch>" line;
    # any further line means a modified/untracked/staged path.
    lines = [ln for ln in (status.get("output") or "").splitlines() if ln.strip()]
    dirty = any(not ln.startswith("##") for ln in lines)

    return check_loop_start_preconditions(branch, dirty, allowed_branches)
