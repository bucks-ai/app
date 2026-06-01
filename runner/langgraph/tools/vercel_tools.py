"""Vercel deployment tools — degrades gracefully when VERCEL_TOKEN is absent."""
import requests
from config import get_config
from tools.log_tools import log_event

_BASE = "https://api.vercel.com"


def _headers():
    cfg = get_config()
    return {"Authorization": f"Bearer {cfg.vercel_token}"}


def get_deployment_status(project_id: str = None) -> dict:
    cfg = get_config()
    if not cfg.has_vercel:
        log_event("vercel_degraded", {"reason": "no VERCEL_TOKEN"})
        return {"available": False, "reason": "no VERCEL_TOKEN"}
    try:
        url = f"{_BASE}/v6/deployments"
        params = {"projectId": project_id} if project_id else {}
        r = requests.get(url, headers=_headers(), params=params, timeout=15)
        r.raise_for_status()
        deployments = r.json().get("deployments", [])
        latest = deployments[0] if deployments else None
        return {"available": True, "latest": latest}
    except Exception as e:
        log_event("error", {"tool": "vercel", "action": "get_deployment_status", "error": str(e)})
        return {"available": False, "error": str(e)}


def trigger_deploy(project_name: str = None) -> dict:
    cfg = get_config()
    if not cfg.has_vercel:
        return {"success": False, "reason": "no VERCEL_TOKEN"}
    if not cfg.auto_deploy:
        return {"success": False, "reason": "AUTO_DEPLOY=false"}
    log_event("deploy_started", {"project_name": project_name})
    status = get_deployment_status()
    log_event("deploy_completed", {"status": status})
    return {"success": status.get("available", False), "status": status}
