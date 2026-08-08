"""Repo-health preflight and check-failure classifier (M4c.4).

Provides two services:

1. ``run_repo_health_check`` — run ``scripts/check.sh`` once against the
   starting-state repo before any task is dispatched (halting check in the
   startup preflight). A broken repo caught here stops the loop with
   ``repo_unhealthy`` and zero worker budget is spent on work that will
   never pass verification.

2. ``classify_check_failure`` — when a worker's check fails mid-task,
   determine whether the failure is PRE-EXISTING (environmental) or was
   INTRODUCED by the task. Stashes uncommitted changes, re-runs check.sh
   on the clean state (the "base check"), and pops the stash. If the base
   check also fails, the failure predates this task; if it passes, the task
   broke it. This classification controls whether failure counters are
   charged to the task.

3. ``get_dirty_paths`` — return uncommitted paths from ``git status --short``
   for use in the completion-evidence gate's human-readable block.
"""
from __future__ import annotations

import os
import subprocess
from typing import Callable, Optional

_CHECK_SCRIPT = "scripts/check.sh"
_MAX_EXCERPT = 500


def run_repo_health_check(
    repo_path: str,
    timeout: int = 120,
    run_fn: Optional[Callable] = None,
) -> dict:
    """Run scripts/check.sh and return a health verdict.

    Returns::

        {
          "healthy":         bool,
          "timed_out":       bool,
          "exit_code":       int | None,
          "failed_command":  str,
          "output_excerpt":  str,
        }

    ``failed_command`` is the script path when the check fails; empty on
    success.  ``output_excerpt`` is capped at 500 chars (trailing portion).
    When ``scripts/check.sh`` does not exist (foreign / business repo), the
    check is treated as healthy — same policy as ``git_tools.run_check``.
    """
    if not os.path.isfile(os.path.join(repo_path, _CHECK_SCRIPT)):
        return {
            "healthy": True,
            "timed_out": False,
            "exit_code": None,
            "failed_command": "",
            "output_excerpt": "[no scripts/check.sh — repo health check skipped]",
        }

    if run_fn is None:
        run_fn = subprocess.run

    try:
        result = run_fn(
            ["bash", _CHECK_SCRIPT],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        output = ((result.stdout or "") + (result.stderr or "")).strip()
        exit_code = result.returncode
        return {
            "healthy": exit_code == 0,
            "timed_out": False,
            "exit_code": exit_code,
            "failed_command": _CHECK_SCRIPT if exit_code != 0 else "",
            "output_excerpt": output[-_MAX_EXCERPT:] if output else "",
        }
    except subprocess.TimeoutExpired:
        return {
            "healthy": False,
            "timed_out": True,
            "exit_code": None,
            "failed_command": _CHECK_SCRIPT,
            "output_excerpt": f"[timed out after {timeout}s — check.sh did not complete]",
        }
    except Exception as exc:
        return {
            "healthy": False,
            "timed_out": False,
            "exit_code": None,
            "failed_command": _CHECK_SCRIPT,
            "output_excerpt": f"[error running check.sh: {type(exc).__name__}: {exc}]",
        }


def classify_check_failure(
    repo_path: str,
    timeout: int = 120,
    git_fn: Optional[Callable] = None,
    run_fn: Optional[Callable] = None,
) -> dict:
    """Determine if a check.sh failure is environmental or task-caused.

    Stashes uncommitted changes (including untracked files), re-runs
    check.sh on the clean state (the "base check"), and pops the stash.

    - If the base check also fails → **environmental**: the breakage
      predates this task; no failure counter should be charged to it.
    - If the base check passes → **task failure**: the task introduced the
      breakage; existing failure handling applies unchanged.
    - If the base check cannot be determined (error / timeout) →
      conservatively NOT classified as environmental.

    Returns::

        {
          "environmental":        bool,
          "base_passed":          bool | None,
          "had_stash":            bool,
          "base_output_excerpt":  str,
        }
    """
    if not os.path.isfile(os.path.join(repo_path, _CHECK_SCRIPT)):
        return {
            "environmental": False,
            "base_passed": None,
            "had_stash": False,
            "base_output_excerpt": "[no scripts/check.sh]",
        }

    if git_fn is None:
        git_fn = subprocess.run
    if run_fn is None:
        run_fn = subprocess.run

    # Stash uncommitted changes (including new untracked files added by the worker).
    had_stash = False
    try:
        stash_result = git_fn(
            ["git", "stash", "--include-untracked", "--message", "runner_env_check"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=30,
        )
        had_stash = (
            stash_result.returncode == 0
            and "No local changes to save" not in (stash_result.stdout or "")
        )
    except Exception:
        pass  # stash failure → assume nothing was stashed; proceed anyway

    base_passed: Optional[bool] = None
    base_output = ""

    try:
        check_result = run_fn(
            ["bash", _CHECK_SCRIPT],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
        base_passed = check_result.returncode == 0
        base_output = ((check_result.stdout or "") + (check_result.stderr or "")).strip()
    except subprocess.TimeoutExpired:
        base_output = f"[base check timed out after {timeout}s]"
    except Exception as exc:
        base_output = f"[base check error: {type(exc).__name__}: {exc}]"
    finally:
        if had_stash:
            try:
                git_fn(
                    ["git", "stash", "pop"],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
            except Exception:
                pass  # stash pop failure must not re-raise; the work is restored best-effort

    environmental = base_passed is False  # only confirmed-fail on clean state qualifies

    return {
        "environmental": environmental,
        "base_passed": base_passed,
        "had_stash": had_stash,
        "base_output_excerpt": base_output[-_MAX_EXCERPT:] if base_output else "",
    }


def get_dirty_paths(
    repo_path: str,
    git_fn: Optional[Callable] = None,
) -> list:
    """Return uncommitted paths from ``git status --short``.

    Used by the completion-evidence gate to name work that exists in the
    tree but could not be committed because the base repo's check.sh failed.
    Returns an empty list when the tree is clean or git is unavailable.
    """
    if git_fn is None:
        git_fn = subprocess.run

    try:
        result = git_fn(
            ["git", "status", "--short"],
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=15,
        )
        if result.returncode != 0:
            return []
        paths = []
        for line in (result.stdout or "").splitlines():
            stripped = line.strip()
            if stripped:
                # git status --short format: "XY path" — strip the status prefix
                paths.append(stripped[3:] if len(stripped) > 3 else stripped)
        return [p for p in paths if p]
    except Exception:
        return []


def format_repo_unhealthy_report(check_result: dict) -> str:
    """Format the human-readable ``repo_unhealthy`` stop report.

    Includes the failed command, exit code, an excerpt of its output, and
    a one-sentence diagnosis so the founder knows immediately what is wrong
    and that no task can complete until it is fixed.
    """
    lines = ["REPO HEALTH PREFLIGHT: FAILED"]
    lines.append("")

    cmd = check_result.get("failed_command") or _CHECK_SCRIPT
    if check_result.get("timed_out"):
        lines.append(f"  Command:   {cmd}")
        lines.append("  Exit code: (timed out — no exit code)")
    else:
        lines.append(f"  Command:   {cmd}")
        lines.append(f"  Exit code: {check_result.get('exit_code')}")

    excerpt = (check_result.get("output_excerpt") or "").strip()
    if excerpt:
        lines.append("")
        lines.append(f"  Output (last {_MAX_EXCERPT} chars):")
        for line in excerpt.splitlines():
            lines.append(f"    {line}")

    lines.append("")
    lines.append(
        "This is a PRE-EXISTING repo problem, not a task failure. "
        "No task can complete until scripts/check.sh passes on the base repo."
    )
    return "\n".join(lines) + "\n"
