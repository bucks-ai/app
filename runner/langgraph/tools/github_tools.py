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
        return [{"number": i.number, "title": i.title, "labels": [l.name for l in i.labels]} for i in issues]
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


def create_or_update_task_from_issue(issue: dict) -> dict:
    from tools.task_tools import add_task
    task = {
        "id": f"gh-issue-{issue.get('number', 'unknown')}",
        "title": issue.get("title", "GitHub Issue"),
        "type": "general",
        "status": "queued",
        "source": "github_issue",
        "issue_number": issue.get("number"),
    }
    add_task(task)
    return task
