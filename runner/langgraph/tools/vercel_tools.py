"""Vercel deployment tools — degrades gracefully when VERCEL_TOKEN is absent.

In addition to one-shot status reads, this module can *poll* a deployment until
it reaches a terminal state (READY / ERROR / CANCELED) or a timeout elapses, so
the runner can wait for an auto-deploy to actually finish instead of firing it
and immediately moving on.
"""
import time
from typing import Optional

import requests

from config import get_config
from tools.http_retry import retry_request
from tools.log_tools import log_event

_BASE = "https://api.vercel.com"

# Normalized Vercel deployment readyState values.
_STATE_READY = "READY"
_STATES_FAILED = frozenset({"ERROR", "CANCELED", "DELETED"})
_STATES_IN_PROGRESS = frozenset({"QUEUED", "INITIALIZING", "BUILDING"})


def _headers():
    cfg = get_config()
    return {"Authorization": f"Bearer {cfg.vercel_token}"}


def normalize_ready_state(deployment: dict) -> str:
    """Return an uppercase readyState for a deployment, or 'UNKNOWN'.

    Vercel exposes the state as ``readyState`` on most endpoints and ``state`` on
    others; accept either so callers don't have to care which API version produced
    the record.
    """
    if not deployment:
        return "UNKNOWN"
    state = deployment.get("readyState") or deployment.get("state") or ""
    return str(state).upper() or "UNKNOWN"


def is_terminal_state(state: str) -> bool:
    """True when a deployment will not change state any further."""
    s = (state or "").upper()
    return s == _STATE_READY or s in _STATES_FAILED


def get_deployment_status(project_id: str = None) -> dict:
    cfg = get_config()
    if not cfg.has_vercel:
        log_event("vercel_degraded", {"reason": "no VERCEL_TOKEN"})
        return {"available": False, "reason": "no VERCEL_TOKEN"}
    try:
        url = f"{_BASE}/v6/deployments"
        params = {"projectId": project_id} if project_id else {}
        r = retry_request(requests.get, url, headers=_headers(), params=params, timeout=15)
        r.raise_for_status()
        deployments = r.json().get("deployments", [])
        latest = deployments[0] if deployments else None
        return {"available": True, "latest": latest}
    except Exception as e:
        log_event("error", {"tool": "vercel", "action": "get_deployment_status", "error": str(e)})
        return {"available": False, "error": str(e)}


def get_deployment_by_id(deployment_id: str) -> dict:
    """Fetch a single deployment by its id/uid (read-only)."""
    cfg = get_config()
    if not cfg.has_vercel:
        log_event("vercel_degraded", {"reason": "no VERCEL_TOKEN"})
        return {"available": False, "reason": "no VERCEL_TOKEN"}
    if not deployment_id:
        return {"available": False, "error": "no deployment_id"}
    try:
        url = f"{_BASE}/v13/deployments/{deployment_id}"
        r = retry_request(requests.get, url, headers=_headers(), timeout=15)
        r.raise_for_status()
        return {"available": True, "deployment": r.json()}
    except Exception as e:
        log_event("error", {"tool": "vercel", "action": "get_deployment_by_id", "error": str(e)})
        return {"available": False, "error": str(e)}


def poll_deployment_until_terminal(
    deployment_id: str = None,
    project_id: str = None,
    timeout: float = None,
    interval: float = None,
    fetch=None,
    sleep=time.sleep,
    now=time.monotonic,
) -> dict:
    """Poll a deployment until it reaches a terminal state or ``timeout`` elapses.

    Resolves the deployment by ``deployment_id`` when given, otherwise tracks the
    latest deployment for ``project_id``. ``timeout`` and ``interval`` default to
    the configured ``VERCEL_POLL_TIMEOUT`` / ``VERCEL_POLL_INTERVAL`` (seconds).

    ``fetch``/``sleep``/``now`` are injectable so the loop can be unit-tested
    without the network or real time; production callers leave them at the
    defaults.

    Returns a verdict dict::

        {
          "available": bool,   # False only when Vercel can't be reached at all
          "ready":     bool,   # terminal state was READY
          "terminal":  bool,   # reached a terminal state before timing out
          "timed_out": bool,   # gave up because timeout elapsed
          "state":     str,    # last observed normalized state
          "deployment": dict,  # last observed deployment record
          "polls":     int,    # number of status reads performed
          "elapsed":   float,  # seconds spent polling
        }
    """
    cfg = get_config()
    if not cfg.has_vercel:
        log_event("vercel_degraded", {"reason": "no VERCEL_TOKEN", "action": "poll"})
        return {
            "available": False,
            "reason": "no VERCEL_TOKEN",
            "ready": False,
            "terminal": False,
            "timed_out": False,
            "polls": 0,
        }

    timeout = cfg.vercel_poll_timeout if timeout is None else timeout
    interval = cfg.vercel_poll_interval if interval is None else interval
    if interval <= 0:
        interval = 1.0

    if fetch is None:
        if deployment_id:
            fetch = lambda: get_deployment_by_id(deployment_id)
        else:
            fetch = lambda: get_deployment_status(project_id)

    start = now()
    polls = 0
    last_state = "UNKNOWN"
    last_deployment = None
    log_event("deploy_poll_started", {
        "deployment_id": deployment_id,
        "project_id": project_id,
        "timeout": timeout,
        "interval": interval,
    })

    while True:
        res = fetch() or {}
        polls += 1
        if not res.get("available"):
            reason = res.get("error") or res.get("reason") or "unavailable"
            log_event("deploy_poll_unavailable", {"polls": polls, "reason": reason})
            return {
                "available": False,
                "error": reason,
                "ready": False,
                "terminal": False,
                "timed_out": False,
                "state": last_state,
                "deployment": last_deployment,
                "polls": polls,
                "elapsed": round(now() - start, 2),
            }

        deployment = res.get("deployment") or res.get("latest")
        last_deployment = deployment
        last_state = normalize_ready_state(deployment)
        elapsed = round(now() - start, 2)
        log_event("deploy_poll_tick", {"poll": polls, "state": last_state, "elapsed": elapsed})

        if is_terminal_state(last_state):
            ready = last_state == _STATE_READY
            log_event(
                "deploy_poll_ready" if ready else "deploy_poll_failed",
                {"state": last_state, "polls": polls, "elapsed": elapsed},
            )
            return {
                "available": True,
                "ready": ready,
                "terminal": True,
                "timed_out": False,
                "state": last_state,
                "deployment": deployment,
                "polls": polls,
                "elapsed": elapsed,
            }

        # Not terminal yet — only sleep for another round if there is time left.
        if (now() - start) + interval >= timeout:
            log_event("deploy_poll_timeout", {
                "state": last_state,
                "polls": polls,
                "elapsed": round(now() - start, 2),
                "timeout": timeout,
            })
            return {
                "available": True,
                "ready": False,
                "terminal": False,
                "timed_out": True,
                "state": last_state,
                "deployment": deployment,
                "polls": polls,
                "elapsed": round(now() - start, 2),
            }

        sleep(interval)


def trigger_deploy(project_name: str = None, project_id: str = None, poll: bool = True) -> dict:
    cfg = get_config()
    if not cfg.has_vercel:
        return {"success": False, "reason": "no VERCEL_TOKEN"}
    if not cfg.auto_deploy:
        return {"success": False, "reason": "AUTO_DEPLOY=false"}
    log_event("deploy_started", {"project_name": project_name})
    status = get_deployment_status(project_id)
    result = {"success": status.get("available", False), "status": status}

    # Auto-deploy polling: wait for the latest deployment to finish building so the
    # runner reports a real ready/failed verdict instead of an in-progress snapshot.
    if poll and cfg.auto_deploy_poll and status.get("available"):
        latest = status.get("latest") or {}
        deployment_id = latest.get("uid") or latest.get("id")
        verdict = poll_deployment_until_terminal(
            deployment_id=deployment_id,
            project_id=project_id,
        )
        result["poll"] = verdict
        if verdict.get("available"):
            # A reachable-but-not-ready deployment (failed/canceled/timed out) is a
            # deploy failure as far as the runner is concerned.
            result["success"] = bool(verdict.get("ready"))

    log_event("deploy_completed", {"status": status, "poll": result.get("poll")})
    return result


def extract_deploy_url(deploy_result: dict) -> Optional[str]:
    """Pull the deployed URL out of a ``trigger_deploy()`` result, if present.

    Vercel deployment objects expose a bare hostname (no scheme) in ``url``, not
    a top-level ``url``/``deployment_url`` key on the ``trigger_deploy`` result —
    so callers reading ``deploy_result.get("url")`` directly always get ``None``.
    Prefers the polled deployment (most current, post-build) over the initial
    status snapshot, and falls back to top-level convenience keys for callers
    (tests, other deploy providers) that construct a ``deploy_result`` by hand.
    """
    if not deploy_result:
        return None
    poll = deploy_result.get("poll") or {}
    deployment = poll.get("deployment") or (deploy_result.get("status") or {}).get("latest") or {}
    host = deployment.get("url") or deploy_result.get("url") or deploy_result.get("deployment_url")
    if not host:
        return None
    host = str(host)
    if host.startswith("http://") or host.startswith("https://"):
        return host
    return f"https://{host}"
