"""Parent-child self-provisioning framework.

Implements the account/provisioning model from STRATEGY.md §3: bucks.ai owns
master vendor accounts once; every customer business is a scoped child resource
provisioned under them via API. The human creates ONE parent account per vendor,
once, ever. This module creates UNLIMITED scoped children under it via API,
forever, unattended.

SCOPE (M4c): GitHub repos/deploy-keys, Vercel projects/env-vars/git-links,
Supabase projects/api-keys. Stripe/AWS/Resend/Twilio/PostHog adapters are
consciously deferred to a later task — see seed_trimmed_sequence.py.

EXPLICITLY OUT OF SCOPE: autonomous signup for brand-new vendor accounts. ToS
acceptance is a binding legal act; provider terms prohibit automated signup;
agent-completed signup flows are a recognised fraud vector. See STRATEGY.md §6.3.

Each adapter degrades gracefully when its parent credential is absent — the
runner never halts; it logs and skips.

Secret hygiene: credential VALUES are never logged. Only names and resource IDs
appear in log payloads.
"""
from __future__ import annotations

import time
from typing import Optional

import requests

from tools.http_retry import retry_request
from tools.log_tools import log_event

_DEFAULT_TIMEOUT = 20
_GH_API = "https://api.github.com"
_VERCEL_API = "https://api.vercel.com"
_SUPABASE_API = "https://api.supabase.com"


# ---------------------------------------------------------------------------
# GitHub child provisioning
# ---------------------------------------------------------------------------

def _gh_headers(token: str) -> dict:
    return {
        "Authorization": f"Bearer {token}",
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
    }


def _gh_token() -> Optional[str]:
    from config import get_config
    return get_config().github_token


def create_github_repo(
    org: str,
    name: str,
    *,
    private: bool = True,
    description: str = "",
    token: Optional[str] = None,
) -> dict:
    """Create a repository under ``org`` using the parent GITHUB_TOKEN.

    Returns ``{"available": bool, "created": bool, "repo": dict|None,
    "reason": str|None}``. A 422 (already exists) is treated as success with
    ``created=False`` so the call is idempotent.
    """
    tok = token or _gh_token()
    if not tok:
        log_event("provisioning_skipped", {"adapter": "github", "reason": "no GITHUB_TOKEN"})
        return {"available": False, "reason": "no GITHUB_TOKEN"}
    if not org:
        return {"available": False, "reason": "no org"}

    url = f"{_GH_API}/orgs/{org}/repos"
    payload = {
        "name": name,
        "private": private,
        "description": description,
        "auto_init": True,
    }
    try:
        r = retry_request(
            requests.post, url,
            json=payload, headers=_gh_headers(tok),
            timeout=_DEFAULT_TIMEOUT,
        )
        if r.status_code == 422:
            return {"available": True, "created": False, "reason": "already_exists"}
        r.raise_for_status()
        repo = r.json()
        log_event("provisioning_created", {
            "adapter": "github", "resource": "repo",
            "org": org, "name": name,
        })
        return {"available": True, "created": True, "repo": repo}
    except Exception as e:
        log_event("error", {
            "tool": "provisioning_github", "action": "create_repo",
            "org": org, "name": name, "error": str(e),
        })
        return {"available": True, "created": False, "error": str(e)}


def add_github_deploy_key(
    repo_full_name: str,
    title: str,
    public_key: str,
    *,
    read_only: bool = True,
    token: Optional[str] = None,
) -> dict:
    """Add a deploy key to a GitHub repository.

    Returns ``{"available": bool, "created": bool, "key_id": int|None}``.
    ``public_key`` is the SSH public key (the value that lives in ~/.ssh/*.pub);
    it is sent to GitHub and is not a secret.
    """
    tok = token or _gh_token()
    if not tok:
        return {"available": False, "reason": "no GITHUB_TOKEN"}

    url = f"{_GH_API}/repos/{repo_full_name}/keys"
    payload = {"title": title, "key": public_key, "read_only": read_only}
    try:
        r = retry_request(
            requests.post, url,
            json=payload, headers=_gh_headers(tok),
            timeout=_DEFAULT_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        log_event("provisioning_created", {
            "adapter": "github", "resource": "deploy_key",
            "repo": repo_full_name, "title": title,
        })
        return {"available": True, "created": True, "key_id": data.get("id")}
    except Exception as e:
        log_event("error", {
            "tool": "provisioning_github", "action": "add_deploy_key",
            "repo": repo_full_name, "error": str(e),
        })
        return {"available": True, "created": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Vercel child provisioning
# ---------------------------------------------------------------------------

def _vercel_token() -> Optional[str]:
    from config import get_config
    return get_config().vercel_token


def _vercel_team_id() -> Optional[str]:
    from config import get_config
    return getattr(get_config(), "provisioning_vercel_team_id", None)


def _vercel_headers(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _vercel_params(team_id: Optional[str]) -> dict:
    tid = team_id or _vercel_team_id()
    return {"teamId": tid} if tid else {}


def create_vercel_project(
    name: str,
    *,
    framework: str = "nextjs",
    team_id: Optional[str] = None,
    token: Optional[str] = None,
) -> dict:
    """Create a Vercel project under the parent token's scope.

    Returns ``{"available": bool, "created": bool, "project": dict|None}``.
    A 409 (already exists) is treated as success with ``created=False``.
    """
    tok = token or _vercel_token()
    if not tok:
        log_event("provisioning_skipped", {"adapter": "vercel", "reason": "no VERCEL_TOKEN"})
        return {"available": False, "reason": "no VERCEL_TOKEN"}

    url = f"{_VERCEL_API}/v9/projects"
    payload = {"name": name, "framework": framework}
    try:
        r = retry_request(
            requests.post, url,
            json=payload, headers=_vercel_headers(tok),
            params=_vercel_params(team_id),
            timeout=_DEFAULT_TIMEOUT,
        )
        if r.status_code == 409:
            return {"available": True, "created": False, "reason": "already_exists"}
        r.raise_for_status()
        project = r.json()
        log_event("provisioning_created", {
            "adapter": "vercel", "resource": "project", "name": name,
        })
        return {"available": True, "created": True, "project": project}
    except Exception as e:
        log_event("error", {
            "tool": "provisioning_vercel", "action": "create_project",
            "name": name, "error": str(e),
        })
        return {"available": True, "created": False, "error": str(e)}


def set_vercel_env(
    project_id: str,
    key: str,
    value: str,
    *,
    env_targets: Optional[list] = None,
    team_id: Optional[str] = None,
    token: Optional[str] = None,
) -> dict:
    """Set an environment variable on a Vercel project.

    Returns ``{"available": bool, "created": bool}``.
    Secret hygiene: ``value`` is sent to Vercel but never appears in any log.
    """
    tok = token or _vercel_token()
    if not tok:
        return {"available": False, "reason": "no VERCEL_TOKEN"}

    url = f"{_VERCEL_API}/v9/projects/{project_id}/env"
    targets = env_targets or ["production", "preview", "development"]
    payload = {"key": key, "value": value, "type": "encrypted", "target": targets}
    try:
        r = retry_request(
            requests.post, url,
            json=payload, headers=_vercel_headers(tok),
            params=_vercel_params(team_id),
            timeout=_DEFAULT_TIMEOUT,
        )
        r.raise_for_status()
        log_event("provisioning_created", {
            "adapter": "vercel", "resource": "env_var",
            "key": key, "project_id": project_id,
        })
        return {"available": True, "created": True}
    except Exception as e:
        log_event("error", {
            "tool": "provisioning_vercel", "action": "set_env",
            "key": key, "project_id": project_id, "error": str(e),
        })
        return {"available": True, "created": False, "error": str(e)}


def link_vercel_git(
    project_id: str,
    repo_full_name: str,
    *,
    git_type: str = "github",
    production_branch: str = "main",
    team_id: Optional[str] = None,
    token: Optional[str] = None,
) -> dict:
    """Link a Vercel project to a GitHub repository for auto-deploys.

    Returns ``{"available": bool, "linked": bool}``.
    """
    tok = token or _vercel_token()
    if not tok:
        return {"available": False, "reason": "no VERCEL_TOKEN"}

    url = f"{_VERCEL_API}/v9/projects/{project_id}"
    parts = repo_full_name.split("/", 1)
    org = parts[0] if len(parts) == 2 else ""
    repo = parts[1] if len(parts) == 2 else repo_full_name
    payload = {
        "link": {
            "type": git_type,
            "repo": repo,
            "org": org,
            "productionBranch": production_branch,
        }
    }
    try:
        r = retry_request(
            requests.patch, url,
            json=payload, headers=_vercel_headers(tok),
            params=_vercel_params(team_id),
            timeout=_DEFAULT_TIMEOUT,
        )
        r.raise_for_status()
        log_event("provisioning_created", {
            "adapter": "vercel", "resource": "git_link",
            "project_id": project_id, "repo": repo_full_name,
        })
        return {"available": True, "linked": True}
    except Exception as e:
        log_event("error", {
            "tool": "provisioning_vercel", "action": "link_git",
            "project_id": project_id, "repo": repo_full_name, "error": str(e),
        })
        return {"available": True, "linked": False, "error": str(e)}


# ---------------------------------------------------------------------------
# Supabase child provisioning
# ---------------------------------------------------------------------------

def _supabase_management_key() -> Optional[str]:
    from config import get_config
    return getattr(get_config(), "supabase_management_api_key", None)


def _supabase_org_id() -> Optional[str]:
    from config import get_config
    return getattr(get_config(), "supabase_org_id", None)


def _supabase_headers(key: str) -> dict:
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def create_supabase_project(
    name: str,
    db_password: str,
    *,
    region: str = "us-east-1",
    org_id: Optional[str] = None,
    management_key: Optional[str] = None,
) -> dict:
    """Create a new Supabase project via the Management API.

    Returns ``{"available": bool, "created": bool, "project": dict|None}``.
    Secret hygiene: ``db_password`` is sent to Supabase but never logged.
    """
    key = management_key or _supabase_management_key()
    if not key:
        log_event("provisioning_skipped", {
            "adapter": "supabase", "reason": "no SUPABASE_MANAGEMENT_API_KEY",
        })
        return {"available": False, "reason": "no SUPABASE_MANAGEMENT_API_KEY"}

    target_org = org_id or _supabase_org_id()
    if not target_org:
        return {"available": False, "reason": "no SUPABASE_ORG_ID"}

    url = f"{_SUPABASE_API}/v1/projects"
    payload = {
        "name": name,
        "db_pass": db_password,
        "region": region,
        "organization_id": target_org,
    }
    try:
        r = retry_request(
            requests.post, url,
            json=payload, headers=_supabase_headers(key),
            timeout=60,
        )
        r.raise_for_status()
        project = r.json()
        log_event("provisioning_created", {
            "adapter": "supabase", "resource": "project",
            "name": name, "ref": project.get("id"),
        })
        return {"available": True, "created": True, "project": project}
    except Exception as e:
        log_event("error", {
            "tool": "provisioning_supabase", "action": "create_project",
            "name": name, "error": str(e),
        })
        return {"available": True, "created": False, "error": str(e)}


def get_supabase_api_keys(
    project_ref: str,
    *,
    management_key: Optional[str] = None,
) -> dict:
    """Retrieve API keys for a Supabase project via the Management API.

    Returns ``{"available": bool, "keys": list[dict]|None}``.
    The key values are returned to the caller for vaulting — they are never
    logged in this function (log_event only records the count).
    """
    key = management_key or _supabase_management_key()
    if not key:
        return {"available": False, "reason": "no SUPABASE_MANAGEMENT_API_KEY"}

    url = f"{_SUPABASE_API}/v1/projects/{project_ref}/api-keys"
    try:
        r = retry_request(
            requests.get, url,
            headers=_supabase_headers(key),
            timeout=_DEFAULT_TIMEOUT,
        )
        r.raise_for_status()
        keys = r.json()
        log_event("provisioning_read", {
            "adapter": "supabase", "resource": "api_keys",
            "project_ref": project_ref, "count": len(keys),
        })
        return {"available": True, "keys": keys}
    except Exception as e:
        log_event("error", {
            "tool": "provisioning_supabase", "action": "get_api_keys",
            "project_ref": project_ref, "error": str(e),
        })
        return {"available": True, "keys": None, "error": str(e)}


def wait_supabase_project_ready(
    project_ref: str,
    *,
    timeout_s: int = 300,
    poll_interval_s: int = 10,
    management_key: Optional[str] = None,
) -> dict:
    """Poll a Supabase project until status is ACTIVE_HEALTHY or timeout elapses.

    Returns ``{"available": bool, "ready": bool, "status": str}``.
    """
    key = management_key or _supabase_management_key()
    if not key:
        return {"available": False, "reason": "no SUPABASE_MANAGEMENT_API_KEY"}

    url = f"{_SUPABASE_API}/v1/projects/{project_ref}"
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        try:
            r = retry_request(
                requests.get, url,
                headers=_supabase_headers(key),
                timeout=_DEFAULT_TIMEOUT,
            )
            r.raise_for_status()
            data = r.json()
            status = data.get("status", "UNKNOWN")
            if status == "ACTIVE_HEALTHY":
                return {"available": True, "ready": True, "status": status}
            if status in ("INACTIVE", "REMOVED"):
                return {"available": True, "ready": False, "status": status}
        except Exception as e:
            log_event("error", {
                "tool": "provisioning_supabase", "action": "wait_ready",
                "project_ref": project_ref, "error": str(e),
            })
        time.sleep(poll_interval_s)

    return {"available": True, "ready": False, "status": "timeout"}
