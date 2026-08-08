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


def fetch_pull_main(repo_path: str, allowed_paths=None) -> dict:
    """Bring the current branch up to date with ``origin/main``.

    Prefers a rebase (``GIT_PREFER_REBASE``, on by default) via
    ``tools.git_autonomy.sync_with_base``, which also stashes uncommitted work
    first, drops local commits whose content is already upstream, and
    auto-resolves formatting-only conflicts. M4b needed the founder to
    hand-choose rebase vs reset on a diverged main and to recover from a stale
    origin/main no-op merge; the merge-based ``git pull`` below is kept only as
    an explicit opt-out (``GIT_PREFER_REBASE=false``).
    """
    log_event("git_sync", {"step": "fetch_pull_main"})
    from config import get_config
    from tools.git_autonomy import sync_with_base

    cfg = get_config()
    if getattr(cfg, "git_prefer_rebase", True):
        result = sync_with_base(repo_path, base="main", allowed_paths=allowed_paths, cfg=cfg)
        return {
            "fetch": result.get("reason") != "fetch_failed",
            "pull": result["success"],
            "rebased": result["success"],
            "reason": result.get("reason"),
            "skipped_commits": result.get("skipped_commits", 0),
            "escalated": result.get("escalated", []),
            "stash_stranded": result.get("stash_stranded", False),
            "output": result.get("output", ""),
        }

    fetch = _git(["fetch", "origin"], repo_path)
    pull = _git(["pull", "origin", "main", "--no-edit"], repo_path)
    return {"fetch": fetch.success, "pull": pull.success, "output": pull.output}


def create_branch(repo_path: str, branch: str) -> dict:
    """Check out ``branch`` (creating it if new), carrying uncommitted work across.

    M4c safety: the checkout is wrapped in stash/pop rather than run bare. A
    routine branch operation reverted the founder's uncommitted doc edits during
    M4b; here anything uncommitted is stashed under a labelled message first and
    popped back onto the target branch — so the worker's changes still reach the
    commit that follows, and a human's edits are never silently dropped.

    If the pop conflicts the work stays in the stash list and this returns
    failure: committing a half-restored tree would be worse than not committing.
    """
    from tools.git_autonomy import restore_protected_work, safe_checkout

    existing = _git(["branch", "--list", branch], repo_path)
    create = branch not in (existing.output or "")
    checkout = safe_checkout(repo_path, branch, create=create, label=f"create-branch:{branch}")
    guard = checkout["guard"]

    if not checkout["success"]:
        restore_protected_work(repo_path, guard)
        log_event("branch_created", {"branch": branch, "success": False, "output": checkout["output"][-500:]})
        return {"success": False, "output": checkout["output"]}

    restore_protected_work(repo_path, guard)
    if guard.has_stash:
        message = (
            f"branch '{branch}' checked out but stashed local work could not be "
            f"restored — it is preserved in the stash list as '{guard.stash_message}'"
        )
        log_event("branch_created", {"branch": branch, "success": False, "output": message})
        return {"success": False, "output": message, "stash_stranded": True}

    log_event("branch_created", {
        "branch": branch, "success": True, "preserved_files": len(guard.files),
    })
    return {"success": True, "output": checkout["output"]}


def run_check(repo_path: str) -> dict:
    log_event("check_started", {"repo_path": repo_path})
    # scripts/check.sh is a bucks-ai convention (see AGENTS.md); business/foreign
    # repos resolved via tools/foreign_repo_workspace.py have no such script and
    # never will, so a missing script is "no check configured" — not a failure.
    # Treating it as a failure sent every business mission into an unwinnable
    # auto-repair loop (the worker can't create a check that isn't part of its task).
    if not os.path.isfile(os.path.join(repo_path, "scripts", "check.sh")):
        log_event("check_skipped", {"repo_path": repo_path, "reason": "no scripts/check.sh"})
        return {"success": True, "output": "[check skipped: no scripts/check.sh in this repo]"}
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


def fast_forward_main(repo_path: str, merge_sha: str = "") -> dict:
    """Checkout main and fast-forward it to the merge commit on origin/main.

    Must be called BEFORE branch cleanup after a successful merge, so that
    the merge commit is in the local graph before we verify it is reachable
    and before we delete the only local ref that held it.

    Logs ``main_fast_forwarded`` with before/after SHAs.  If the checkout or
    pull fails, returns ``success=False`` and the caller must abort cleanup —
    never delete the feature branch when the local state has not been confirmed
    safe (M4c.4).
    """
    r_before = _git(["rev-parse", "main"], repo_path)
    before_sha = r_before.output.strip() if r_before.success else ""

    checkout = _git(["checkout", "main"], repo_path)
    if not checkout.success:
        log_event("error", {
            "step": "fast_forward_main",
            "merge_sha": merge_sha[:12] if merge_sha else "",
            "reason": "could not checkout main",
            "output": (checkout.output or "")[-400:],
        })
        return {"success": False, "reason": "checkout_failed", "output": checkout.output}

    pull = _git(["pull", "--ff-only", "origin", "main"], repo_path)
    if not pull.success:
        log_event("error", {
            "step": "fast_forward_main",
            "merge_sha": merge_sha[:12] if merge_sha else "",
            "reason": "ff-only pull failed — local main diverged or fetch failed",
            "output": (pull.output or "")[-400:],
        })
        return {"success": False, "reason": "ff_only_failed", "output": pull.output}

    r_after = _git(["rev-parse", "main"], repo_path)
    after_sha = r_after.output.strip() if r_after.success else ""
    log_event("main_fast_forwarded", {
        "before": before_sha,
        "after": after_sha,
        "merge_sha": merge_sha[:12] if merge_sha else "",
    })
    return {"success": True, "before": before_sha, "after": after_sha, "output": pull.output}


def cleanup_feature_branch(repo_path: str, branch: str, force: bool = False, merge_sha: str = "") -> dict:
    """Delete a feature branch locally and on origin.

    ``merge_sha`` is the commit the caller knows landed on main (e.g. the SHA
    returned by the GitHub merge API).  When provided, the branch is not
    deleted unless ``git merge-base --is-ancestor <merge_sha> main`` passes —
    i.e. the merge commit is provably in the local graph.  If it is not yet
    reachable the cleanup is skipped entirely and the branch is left intact:
    an undeleted branch is a trivial cleanup task; a deleted one with work
    that never reached local main can be data loss (M4c.4).

    ``force=True`` retries a failed ``-d`` with ``-D``, but **only** when
    ``merge_sha`` is confirmed reachable from main.  When the merge commit is
    NOT reachable, ``-D`` is never issued regardless of ``force``.  If no
    ``merge_sha`` is given, ``force`` falls back to the old squash-merge
    behaviour (M0.9 finding, 2026-07-06).
    """
    if branch.lower() in _PROTECTED_BRANCHES:
        result = {
            "success": False,
            "local_deleted": False,
            "remote_deleted": False,
            "output": f"Refusing to clean up protected branch '{branch}'.",
        }
        log_event("branch_cleanup_completed", {"branch": branch, **result})
        return result

    # ── Safety gate: only delete when the merge commit is on local main ──────
    if merge_sha:
        ancestor = _git(["merge-base", "--is-ancestor", merge_sha, "main"], repo_path)
        if not ancestor.success:
            result = {
                "success": False,
                "local_deleted": False,
                "remote_deleted": False,
                "output": (
                    f"cleanup skipped: merge commit {merge_sha[:12]} is not reachable "
                    "from local main — branch left intact to prevent data loss"
                ),
            }
            log_event("branch_cleanup_skipped", {
                "branch": branch,
                "merge_sha": merge_sha[:12],
                "reason": (
                    "merge commit not reachable from local main; skipping cleanup "
                    "to avoid deleting the only local ref holding the merged state"
                ),
            })
            return result

    current = current_branch(repo_path)
    if current == branch:
        # M4c safety: never checkout over uncommitted work. Anything dirty is
        # stashed under a labelled message and popped back onto main.
        from tools.git_autonomy import restore_protected_work, safe_checkout

        checkout = safe_checkout(repo_path, "main", label=f"cleanup:{branch}")
        restore_protected_work(repo_path, checkout["guard"])
        if not checkout["success"]:
            result = {
                "success": False,
                "local_deleted": False,
                "remote_deleted": False,
                "output": checkout["output"],
            }
            log_event("branch_cleanup_completed", {"branch": branch, **result})
            return result

    local = _git(["branch", "-d", branch], repo_path)
    if not local.success and force and "not fully merged" in (local.output or ""):
        # Use -D only when the merge commit is confirmed reachable (ancestor
        # check above passed), OR when no merge_sha was given and the caller
        # confirms via the GitHub API that the work landed.
        if not merge_sha or _git(["merge-base", "--is-ancestor", merge_sha, "main"], repo_path).success:
            log_event("branch_cleanup_forced", {
                "branch": branch,
                "reason": "squash/API merge not detectable locally; -d refused, retrying -D",
            })
            local = _git(["branch", "-D", branch], repo_path)
        else:
            log_event("error", {
                "branch": branch,
                "reason": (
                    "-d refused and merge commit not reachable from local main; "
                    "refusing -D to avoid data loss"
                ),
            })
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
