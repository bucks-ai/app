"""GitHub API helpers — degrades gracefully when GITHUB_TOKEN is absent."""
import time
from typing import Optional

import requests

from config import get_config
from tools.http_retry import retry_request
from tools.log_tools import log_event

_gh = None
_API_BASE = "https://api.github.com"


def _client():
    global _gh
    cfg = get_config()
    if not cfg.has_github:
        return None
    if _gh is None:
        from github import Github
        _gh = Github(cfg.github_token)
    return _gh


def list_open_issues(repo: str) -> list[dict]:
    gh = _client()
    if not gh:
        log_event("github_degraded", {"reason": "no GITHUB_TOKEN", "action": "list_open_issues"})
        return []
    try:
        issues = gh.get_repo(repo).get_issues(state="open")
        return [
            {
                "number": i.number,
                "title": i.title,
                "body": i.body or "",
                "url": i.html_url,
                "labels": [l.name for l in i.labels],
                "assignees": [a.login for a in i.assignees],
                "created_at": i.created_at.isoformat() if i.created_at else None,
                "updated_at": i.updated_at.isoformat() if i.updated_at else None,
            }
            for i in issues
            if not getattr(i, "pull_request", None)
        ]
    except Exception as e:
        log_event("error", {"tool": "github", "action": "list_open_issues", "error": str(e)})
        return []


def create_issue(repo: str, title: str, body: str, labels: list[str] = None) -> Optional[dict]:
    gh = _client()
    if not gh:
        log_event("github_degraded", {"reason": "no GITHUB_TOKEN", "action": "create_issue"})
        return None
    try:
        r = gh.get_repo(repo)
        label_objs = [r.get_label(l) for l in (labels or [])] if labels else []
        issue = r.create_issue(title=title, body=body, labels=label_objs)
        return {"number": issue.number, "url": issue.html_url}
    except Exception as e:
        log_event("error", {"tool": "github", "action": "create_issue", "error": str(e)})
        return None


def comment_issue(repo: str, issue_number: int, body: str) -> bool:
    gh = _client()
    if not gh:
        return False
    try:
        gh.get_repo(repo).get_issue(issue_number).create_comment(body)
        return True
    except Exception as e:
        log_event("error", {"tool": "github", "action": "comment_issue", "error": str(e)})
        return False


def close_issue(repo: str, issue_number: int) -> bool:
    gh = _client()
    if not gh:
        return False
    try:
        gh.get_repo(repo).get_issue(issue_number).edit(state="closed")
        return True
    except Exception as e:
        log_event("error", {"tool": "github", "action": "close_issue", "error": str(e)})
        return False


def _slug(value: str) -> str:
    chars = []
    previous_dash = False
    for ch in value.lower():
        if ch.isalnum():
            chars.append(ch)
            previous_dash = False
        elif not previous_dash:
            chars.append("-")
            previous_dash = True
    return "".join(chars).strip("-") or "task"


def _task_type_from_labels(labels: list[str]) -> str:
    normalized = [label.lower() for label in labels]
    for label in normalized:
        if label.startswith("type:"):
            value = label.split(":", 1)[1].strip()
            if value:
                return value
    for candidate in ("ui", "frontend", "polish", "design", "backend"):
        if candidate in normalized:
            return candidate
    return "general"


def _preferred_worker_from_labels(labels: list[str]) -> Optional[str]:
    normalized = [label.lower() for label in labels]
    for label in normalized:
        if label.startswith("worker:"):
            value = label.split(":", 1)[1].strip()
            if value in ("claude", "codex"):
                return value
    if any(label in normalized for label in ("ui", "frontend", "polish", "design")):
        return "codex"
    return None


def create_or_update_task_from_issue(issue: dict) -> dict:
    from tools.task_tools import upsert_task
    labels = issue.get("labels") or []
    issue_number = issue.get("number")
    task_id = f"gh-issue-{issue_number or _slug(issue.get('title', 'issue'))}"
    task = {
        "id": task_id,
        "title": issue.get("title", "GitHub Issue"),
        "description": issue.get("body") or "",
        "type": _task_type_from_labels(labels),
        "status": "queued",
        "branch": f"feature/{task_id}",
        "source": "github_issue",
        "issue_number": issue_number,
        "issue_url": issue.get("url"),
        "issue_labels": labels,
    }
    preferred_worker = _preferred_worker_from_labels(labels)
    if preferred_worker:
        task["preferred_worker"] = preferred_worker
    return upsert_task(task)


def sync_open_issues_to_tasks(repo: Optional[str] = None) -> dict:
    cfg = get_config()
    target_repo = repo or cfg.github_repo
    if not target_repo:
        log_event("github_degraded", {
            "reason": "no GITHUB_REPO",
            "action": "sync_open_issues_to_tasks",
        })
        return {"available": False, "repo": None, "synced": 0, "tasks": []}

    issues = list_open_issues(target_repo)
    tasks = [create_or_update_task_from_issue(issue) for issue in issues]
    log_event("github_issue_sync", {
        "repo": target_repo,
        "issues": len(issues),
        "synced": len(tasks),
    })
    return {"available": True, "repo": target_repo, "synced": len(tasks), "tasks": tasks}


def update_issue_for_task_result(
    repo: str,
    task: dict,
    digest: str,
    *,
    success: bool,
    deploy_verdict: Optional[str] = None,
) -> dict:
    issue_number = task.get("issue_number")
    if not issue_number:
        return {"updated": False, "reason": "task has no linked issue"}

    status = "completed" if success else "failed"
    body = f"Runner {status} task: {task.get('title')}\n\nSummary:\n{digest[:500]}"
    if deploy_verdict:
        body += f"\n\nDeploy: {deploy_verdict}"

    commented = comment_issue(repo, issue_number, body)
    closed = False
    if success and commented:
        closed = close_issue(repo, issue_number)

    return {
        "updated": commented,
        "closed": closed,
        "issue_number": issue_number,
        "status": status,
    }


def _rest_headers(token: Optional[str] = None) -> dict:
    cfg = get_config()
    return {
        "Authorization": f"Bearer {token or cfg.github_token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _error_body(exc: Exception) -> Optional[str]:
    """Best-effort extraction of GitHub's JSON/text error body from a raised
    HTTPError, so protection-rejection reasons (405/409) are visible in logs."""
    resp = getattr(exc, "response", None)
    if resp is None:
        return None
    try:
        return resp.text[:2000]
    except Exception:
        return None


def _status_code(exc: Exception) -> Optional[int]:
    resp = getattr(exc, "response", None)
    return getattr(resp, "status_code", None) if resp is not None else None


def create_pull_request(
    repo: str, branch: str, title: str, body: str, base: str = "main",
    token: Optional[str] = None,
) -> dict:
    """Create a PR for ``branch`` -> ``base``.

    Idempotent: if an open PR already exists for ``branch``, that PR is
    returned instead of creating a duplicate (``created: False``).

    ``token`` overrides the runner's own ``GITHUB_TOKEN`` — used by M4b
    business missions to authenticate with a scoped token for the sandboxed
    repo instead of the runner's own credentials.
    """
    cfg = get_config()
    effective_token = token or cfg.github_token
    if not effective_token:
        log_event("github_degraded", {"reason": "no GITHUB_TOKEN", "action": "create_pull_request"})
        return {"success": False, "reason": "no GITHUB_TOKEN"}

    owner = repo.split("/", 1)[0]
    try:
        existing = retry_request(
            requests.get,
            f"{_API_BASE}/repos/{repo}/pulls",
            headers=_rest_headers(effective_token),
            params={"head": f"{owner}:{branch}", "base": base, "state": "open"},
            timeout=15,
        )
        existing.raise_for_status()
        found = existing.json()
        if found:
            pr = found[0]
            log_event("pr_already_exists", {
                "repo": repo, "branch": branch,
                "number": pr.get("number"), "url": pr.get("html_url"),
            })
            return {
                "success": True, "created": False,
                "number": pr.get("number"), "url": pr.get("html_url"),
            }

        r = retry_request(
            requests.post,
            f"{_API_BASE}/repos/{repo}/pulls",
            headers=_rest_headers(effective_token),
            json={"title": title, "body": body, "head": branch, "base": base},
            timeout=15,
        )
        r.raise_for_status()
        pr = r.json()
        log_event("pr_created", {
            "repo": repo, "branch": branch,
            "number": pr.get("number"), "url": pr.get("html_url"),
        })
        return {
            "success": True, "created": True,
            "number": pr.get("number"), "url": pr.get("html_url"),
        }
    except Exception as e:
        status = _status_code(e)
        body = _error_body(e)
        # GitHub rejects PR creation with 422 "No commits between <base> and <branch>"
        # when the feature branch has no commits ahead of base (e.g. the worker made
        # no net changes). That is not a merge failure — there is simply nothing to
        # merge, since the branch already matches base. Treat it as a no-op success
        # instead of failing the task.
        no_diff = status == 422 and body and "no commits between" in body.lower()
        if no_diff:
            log_event("pr_create_no_diff", {"repo": repo, "branch": branch, "base": base})
            return {"success": True, "created": False, "no_diff": True, "number": None, "url": None}
        log_event("error", {
            "tool": "github", "action": "create_pull_request",
            "error": str(e), "body": body,
        })
        return {"success": False, "error": str(e), "error_body": body}


def _fetch_pr_details(repo: str, pr_number: int, token: Optional[str] = None) -> Optional[dict]:
    """Best-effort fetch of a PR's current mergeable state. Returns ``None``
    (rather than raising) on any error so a transient failure here degrades to
    "keep polling", not a crash of the whole check-poll loop."""
    try:
        r = retry_request(
            requests.get,
            f"{_API_BASE}/repos/{repo}/pulls/{pr_number}",
            headers=_rest_headers(token),
            timeout=15,
        )
        r.raise_for_status()
        return r.json()
    except Exception as e:
        log_event("error", {"tool": "github", "action": "poll_pr_checks_fetch_pr", "error": str(e)})
        return None


def _update_pr_branch(repo: str, pr_number: int, token: Optional[str] = None) -> bool:
    """Refresh a PR's merge ref via the update-branch API to re-trigger
    workflows. Best-effort: returns False (does not raise) on failure."""
    try:
        r = retry_request(
            requests.put,
            f"{_API_BASE}/repos/{repo}/pulls/{pr_number}/update-branch",
            headers=_rest_headers(token),
            timeout=15,
        )
        r.raise_for_status()
        return True
    except Exception as e:
        log_event("error", {"tool": "github", "action": "poll_pr_checks_update_branch", "error": str(e)})
        return False


def poll_pr_checks(
    repo: str,
    sha: str,
    timeout_s: float = None,
    interval_s: float = None,
    sleep=time.sleep,
    now=time.monotonic,
    pr_number: Optional[int] = None,
    empty_grace_s: float = None,
    token: Optional[str] = None,
) -> dict:
    """Poll the check-runs API for ``sha`` until every run completes or the
    timeout elapses.

    ``success`` is True only when every check run reached status "completed"
    with conclusion "success" or "skipped". Distinguishes a real check
    failure (``timed_out: False``) from giving up before checks finished
    (``timed_out: True``) so the caller can log the right event.

    A dropped GitHub Actions webhook can leave a commit with an empty
    ``check_runs`` list forever — that used to burn the full ``timeout``
    every time, indistinguishable from a slow-but-real check run. Once
    ``check_runs`` has been empty for ``empty_grace_s`` seconds (``pr_number``
    permitting), the PR's mergeable state is queried once; if it is
    conflicting (``dirty``) or ``behind``, the branch is refreshed once via
    the update-branch API to re-trigger workflows and polling continues. If
    ``check_runs`` is still empty after a further ``empty_grace_s`` seconds,
    polling fails fast with ``reason: "pr_checks_no_runs"`` — a distinct,
    actionable reason rather than the generic timeout.
    """
    cfg = get_config()
    effective_token = token or cfg.github_token
    if not effective_token:
        log_event("github_degraded", {"reason": "no GITHUB_TOKEN", "action": "poll_pr_checks"})
        return {"success": False, "timed_out": False, "reason": "no GITHUB_TOKEN", "runs": [], "polls": 0}

    timeout = cfg.pr_checks_timeout_s if timeout_s is None else timeout_s
    interval = cfg.pr_checks_poll_interval_s if interval_s is None else interval_s
    if interval <= 0:
        interval = 1.0
    grace = cfg.pr_checks_empty_grace_s if empty_grace_s is None else empty_grace_s
    if grace <= 0:
        grace = 1.0

    start = now()
    polls = 0
    branch_update_attempted = False
    log_event("pr_checks_poll_started", {"repo": repo, "sha": sha, "timeout": timeout, "interval": interval})

    while True:
        polls += 1
        try:
            r = retry_request(
                requests.get,
                f"{_API_BASE}/repos/{repo}/commits/{sha}/check-runs",
                headers=_rest_headers(effective_token),
                timeout=15,
            )
            r.raise_for_status()
            runs = r.json().get("check_runs", [])
        except Exception as e:
            log_event("error", {"tool": "github", "action": "poll_pr_checks", "error": str(e)})
            return {
                "success": False, "timed_out": False, "error": str(e),
                "runs": [], "polls": polls, "elapsed": round(now() - start, 2),
            }

        elapsed = round(now() - start, 2)
        # An empty check_runs list means Actions hasn't registered a run yet —
        # treat that as "not complete", not a vacuous success.
        all_complete = bool(runs) and all(run.get("status") == "completed" for run in runs)
        log_event("pr_checks_poll_tick", {
            "sha": sha, "poll": polls, "elapsed": elapsed,
            "total": len(runs),
            "completed": sum(1 for run in runs if run.get("status") == "completed"),
        })

        if all_complete:
            ok = all(run.get("conclusion") in ("success", "skipped") for run in runs)
            log_event("pr_checks_completed" if ok else "pr_checks_failed", {
                "sha": sha, "polls": polls, "elapsed": elapsed,
                "conclusions": {run.get("name"): run.get("conclusion") for run in runs},
            })
            return {"success": ok, "timed_out": False, "runs": runs, "polls": polls, "elapsed": elapsed}

        if not runs:
            if not branch_update_attempted and elapsed >= grace and pr_number is not None:
                branch_update_attempted = True
                pr_details = _fetch_pr_details(repo, pr_number, effective_token)
                mergeable_state = (pr_details or {}).get("mergeable_state")
                if mergeable_state in ("dirty", "behind"):
                    if _update_pr_branch(repo, pr_number, effective_token):
                        log_event("pr_branch_updated", {
                            "repo": repo, "pr_number": pr_number,
                            "mergeable_state": mergeable_state, "elapsed": elapsed,
                        })

            if elapsed >= grace * 2:
                log_event("pr_checks_no_runs", {
                    "repo": repo, "sha": sha, "pr_number": pr_number,
                    "polls": polls, "elapsed": elapsed,
                })
                return {
                    "success": False, "timed_out": False, "reason": "pr_checks_no_runs",
                    "runs": runs, "polls": polls, "elapsed": elapsed,
                }

        if (now() - start) + interval >= timeout:
            log_event("pr_checks_timeout", {
                "sha": sha, "polls": polls, "elapsed": elapsed, "timeout": timeout,
            })
            return {"success": False, "timed_out": True, "runs": runs, "polls": polls, "elapsed": elapsed}

        sleep(interval)


def merge_pull_request(
    repo: str, pr_number: int, method: str = "merge", token: Optional[str] = None,
) -> dict:
    """Merge a pull request via the REST API.

    On rejection (405 — not mergeable / branch protection unmet, 409 — head
    branch changed since checks ran) GitHub's error body is surfaced verbatim
    in ``error_body`` so the reason is visible in logs rather than swallowed.
    """
    cfg = get_config()
    effective_token = token or cfg.github_token
    if not effective_token:
        log_event("github_degraded", {"reason": "no GITHUB_TOKEN", "action": "merge_pull_request"})
        return {"success": False, "reason": "no GITHUB_TOKEN"}

    try:
        r = retry_request(
            requests.put,
            f"{_API_BASE}/repos/{repo}/pulls/{pr_number}/merge",
            headers=_rest_headers(effective_token),
            json={"merge_method": method},
            timeout=30,
        )
        r.raise_for_status()
        result = r.json()
        log_event("pr_merged", {"repo": repo, "number": pr_number, "sha": result.get("sha")})
        return {"success": bool(result.get("merged")), "sha": result.get("sha"), "message": result.get("message")}
    except Exception as e:
        log_event("error", {
            "tool": "github", "action": "merge_pull_request",
            "error": str(e), "status_code": _status_code(e), "body": _error_body(e),
        })
        return {
            "success": False, "error": str(e),
            "status_code": _status_code(e), "error_body": _error_body(e),
        }
