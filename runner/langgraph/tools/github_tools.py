"""GitHub API helpers — degrades gracefully when GITHUB_TOKEN is absent."""
from typing import Optional
from config import get_config
from tools.log_tools import log_event

_gh = None


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
