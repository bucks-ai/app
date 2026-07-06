"""Shell-based Git helpers."""
import os
from tools.shell_tools import run_command
from tools.log_tools import log_event

_PROTECTED_BRANCHES = {"main", "master", "dev", "develop", "production", "release"}


def _git(args: list[str], cwd: str, timeout: int = 60):
    return run_command(["git"] + args, cwd=cwd, timeout=timeout)


def get_git_status(repo_path: str) -> dict:
    r = _git(["status", "--short", "--branch"], repo_path)
    return {"output": r.output, "success": r.success}


def current_branch(repo_path: str) -> str:
    r = _git(["branch", "--show-current"], repo_path)
    return r.output.strip() if r.success else "unknown"


def latest_commit(repo_path: str) -> str:
    r = _git(["log", "--oneline", "-1"], repo_path)
    return r.output.strip() if r.success else ""


def current_commit_sha(repo_path: str) -> str:
    """Return the full SHA of HEAD — used as the `ref` for the GitHub checks API
    (unlike ``latest_commit``, which returns a `<short-sha> <message>` line meant
    for display/logging, not for use as a git ref)."""
    r = _git(["rev-parse", "HEAD"], repo_path)
    return r.output.strip() if r.success else ""


def fetch_pull_main(repo_path: str) -> dict:
    log_event("git_sync", {"step": "fetch_pull_main"})
    fetch = _git(["fetch", "origin"], repo_path)
    pull = _git(["pull", "origin", "main", "--no-edit"], repo_path)
    return {"fetch": fetch.success, "pull": pull.success, "output": pull.output}


def create_branch(repo_path: str, branch: str) -> dict:
    existing = _git(["branch", "--list", branch], repo_path)
    if branch in (existing.output or ""):
        r = _git(["checkout", branch], repo_path)
    else:
        r = _git(["checkout", "-b", branch], repo_path)
    log_event("branch_created", {"branch": branch, "success": r.success})
    return {"success": r.success, "output": r.output}


def run_check(repo_path: str) -> dict:
    log_event("check_started", {"repo_path": repo_path})
    r = run_command(["bash", "scripts/check.sh"], cwd=repo_path, timeout=300)
    event_type = "check_passed" if r.success else "check_failed"
    log_event(event_type, {"output": r.output[-1000:] if r.output else ""})
    return {"success": r.success, "output": r.output}


def commit_all(repo_path: str, message: str) -> dict:
    add = _git(["add", "-A"], repo_path)
    commit = _git(["commit", "-m", message], repo_path)
    # `git commit` exits non-zero when the tree is already clean. That happens when
    # the worker committed its own changes (the task prompt asks workers to commit) —
    # not a failure, and the existing HEAD is still deployable. Treat that case as a
    # landed commit so push/merge/deploy proceed instead of being skipped.
    nothing_to_commit = (
        not commit.success and "nothing to commit" in (commit.output or "").lower()
    )
    committed = commit.success or nothing_to_commit
    sha = latest_commit(repo_path) if committed else ""
    log_event("commit_created", {
        "message": message,
        "sha": sha,
        "success": commit.success,
        "nothing_to_commit": nothing_to_commit,
    })
    return {
        "success": commit.success,
        "committed": committed,
        "nothing_to_commit": nothing_to_commit,
        "sha": sha,
        "output": commit.output,
    }


def push_branch(repo_path: str, branch: str) -> dict:
    r = _git(["push", "-u", "origin", branch], repo_path, timeout=120)
    log_event("push_completed", {"branch": branch, "success": r.success, "output": r.output[-500:]})
    return {"success": r.success, "output": r.output}


def merge_feature_branch(repo_path: str, branch: str) -> dict:
    log_event("merge_started", {"branch": branch})
    script = os.path.join(repo_path, "scripts", "merge-feature.sh")
    r = run_command(["bash", script, branch], cwd=repo_path, timeout=300)
    log_event("merge_completed", {"branch": branch, "success": r.success, "output": r.output[-500:]})
    return {"success": r.success, "output": r.output}


def cleanup_feature_branch(repo_path: str, branch: str) -> dict:
    if branch.lower() in _PROTECTED_BRANCHES:
        result = {
            "success": False,
            "local_deleted": False,
            "remote_deleted": False,
            "output": f"Refusing to clean up protected branch '{branch}'.",
        }
        log_event("branch_cleanup_completed", {"branch": branch, **result})
        return result

    current = current_branch(repo_path)
    checkout = None
    if current == branch:
        checkout = _git(["checkout", "main"], repo_path)
        if not checkout.success:
            result = {
                "success": False,
                "local_deleted": False,
                "remote_deleted": False,
                "output": checkout.output,
            }
            log_event("branch_cleanup_completed", {"branch": branch, **result})
            return result

    local = _git(["branch", "-d", branch], repo_path)
    remote = _git(["push", "origin", "--delete", branch], repo_path, timeout=120)
    result = {
        "success": local.success and remote.success,
        "local_deleted": local.success,
        "remote_deleted": remote.success,
        "output": "\n".join(part for part in [local.output, remote.output] if part),
    }
    log_event("branch_cleanup_completed", {"branch": branch, **result})
    return result


def push_deploy_if_available(repo_path: str) -> dict:
    r = _git(["remote", "-v"], repo_path)
    if "vercel" in (r.output or "").lower() or "deploy" in (r.output or "").lower():
        push = _git(["push", "deploy", "main"], repo_path, timeout=120)
        return {"attempted": True, "success": push.success, "output": push.output}
    return {"attempted": False, "reason": "no deploy remote configured"}
