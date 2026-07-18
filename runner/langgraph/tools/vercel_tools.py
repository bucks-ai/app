"""Vercel deployment tools — degrades gracefully when VERCEL_TOKEN is absent.

In addition to one-shot status reads, this module can *poll* a deployment until
it reaches a terminal state (READY / ERROR / CANCELED) or a timeout elapses, so
the runner can wait for an auto-deploy to actually finish instead of firing it
and immediately moving on.
"""
import os
import time

import requests

from config import get_config
from tools.http_retry import retry_request
from tools.log_tools import log_event

_BASE = "https://api.vercel.com"

# Normalized Vercel deployment readyState values.
_STATE_READY = "READY"
_STATES_FAILED = frozenset({"ERROR", "CANCELED", "DELETED"})
_STATES_IN_PROGRESS = frozenset({"QUEUED", "INITIALIZING", "BUILDING"})


def _headers(token: str = None):
    """Build the Vercel auth header. *token* overrides the configured
    ``VERCEL_TOKEN`` when set — used for business-mission deploys, which must
    authenticate with the business's own scoped token, never the bucks-ai
    token (see ``resolve_business_vercel_target``)."""
    cfg = get_config()
    return {"Authorization": f"Bearer {token or cfg.vercel_token}"}


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


def normalize_deployment_url(url: str) -> str:
    """Prefix a bare Vercel deployment hostname with ``https://``.

    Vercel's API returns ``url`` as a bare hostname (e.g. ``my-app.vercel.app``)
    with no scheme, which browser automation (Playwright) requires. Absolute
    URLs are passed through unchanged.
    """
    if not url:
        return None
    if url.startswith("http://") or url.startswith("https://"):
        return url
    return f"https://{url}"


def get_deployment_status(project_id: str = None, token: str = None) -> dict:
    cfg = get_config()
    if not (token or cfg.has_vercel):
        log_event("vercel_degraded", {"reason": "no VERCEL_TOKEN"})
        return {"available": False, "reason": "no VERCEL_TOKEN"}
    try:
        url = f"{_BASE}/v6/deployments"
        params = {"projectId": project_id} if project_id else {}
        r = retry_request(requests.get, url, headers=_headers(token), params=params, timeout=15)
        r.raise_for_status()
        deployments = r.json().get("deployments", [])
        latest = deployments[0] if deployments else None
        return {"available": True, "latest": latest}
    except Exception as e:
        log_event("error", {"tool": "vercel", "action": "get_deployment_status", "error": str(e)})
        return {"available": False, "error": str(e)}


def get_deployment_by_id(deployment_id: str, token: str = None) -> dict:
    """Fetch a single deployment by its id/uid (read-only)."""
    cfg = get_config()
    if not (token or cfg.has_vercel):
        log_event("vercel_degraded", {"reason": "no VERCEL_TOKEN"})
        return {"available": False, "reason": "no VERCEL_TOKEN"}
    if not deployment_id:
        return {"available": False, "error": "no deployment_id"}
    try:
        url = f"{_BASE}/v13/deployments/{deployment_id}"
        r = retry_request(requests.get, url, headers=_headers(token), timeout=15)
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
    token: str = None,
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
    if not (token or cfg.has_vercel):
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
            fetch = lambda: get_deployment_by_id(deployment_id, token=token)
        else:
            fetch = lambda: get_deployment_status(project_id, token=token)

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


def trigger_deploy(
    project_name: str = None,
    project_id: str = None,
    poll: bool = True,
    token: str = None,
) -> dict:
    """Trigger (and optionally poll) a Vercel deploy.

    *token* overrides the configured ``VERCEL_TOKEN`` — business missions pass
    the scoped token resolved by ``resolve_business_vercel_target`` here so the
    deploy authenticates against the business's own Vercel account, never the
    bucks-ai one.
    """
    cfg = get_config()
    if not (token or cfg.has_vercel):
        return {"success": False, "reason": "no VERCEL_TOKEN"}
    if not cfg.auto_deploy:
        return {"success": False, "reason": "AUTO_DEPLOY=false"}
    log_event("deploy_started", {"project_name": project_name, "project_id": project_id})
    status = get_deployment_status(project_id, token=token)
    latest = status.get("latest") or {}
    result = {"success": status.get("available", False), "status": status}
    result["url"] = normalize_deployment_url(latest.get("url"))

    # Auto-deploy polling: wait for the latest deployment to finish building so the
    # runner reports a real ready/failed verdict instead of an in-progress snapshot.
    if poll and cfg.auto_deploy_poll and status.get("available"):
        deployment_id = latest.get("uid") or latest.get("id")
        verdict = poll_deployment_until_terminal(
            deployment_id=deployment_id,
            project_id=project_id,
            token=token,
        )
        result["poll"] = verdict
        # The polled deployment record is the freshest source of the final URL
        # (production aliasing can differ from the pre-build snapshot).
        polled_url = normalize_deployment_url((verdict.get("deployment") or {}).get("url"))
        if polled_url:
            result["url"] = polled_url
        if verdict.get("available"):
            # A reachable-but-not-ready deployment (failed/canceled/timed out) is a
            # deploy failure as far as the runner is concerned.
            result["success"] = bool(verdict.get("ready"))

    log_event("deploy_completed", {"status": status, "poll": result.get("poll"), "url": result.get("url")})
    return result


# ---------------------------------------------------------------------------
# M4b: business-mission deploy targeting
#
# A business mission's deploy must target that business's OWN Vercel project
# using a token scoped to it — never the bucks-ai project/token this runner
# otherwise deploys with. The business's target lives on
# ``businesses.sandbox_config`` (JSONB; see
# supabase/migrations/0004_businesses_sandbox_config.sql,
# 0005_business_sandbox_config_vercel_target.sql) under the keys
# ``vercel_project_id`` / ``vercel_token_secret_name`` — the latter names an
# environment variable, never a token value (external containment convention;
# mirrors ``tools/foreign_repo_workspace.py::resolve_scoped_github_token``).
# ---------------------------------------------------------------------------

def resolve_scoped_vercel_token(secret_name: str) -> dict:
    """Read a Vercel token from the environment by *secret_name*.

    Returns ``{"success": True, "token": ..., "secret_name": ...}`` or
    ``{"success": False, "error": "missing_secret"/"no_secret_name", "secret_name": ...}``.
    Callers must only ever surface ``secret_name`` in logs — never ``token``.
    """
    secret_name = (secret_name or "").strip()
    if not secret_name:
        return {"success": False, "error": "no_secret_name"}
    token = os.environ.get(secret_name)
    if not token:
        return {"success": False, "error": "missing_secret", "secret_name": secret_name}
    return {"success": True, "token": token, "secret_name": secret_name}


def resolve_business_vercel_target(sandbox_config: dict) -> dict:
    """Resolve a business mission's Vercel deploy target from its
    ``sandbox_config`` dict (as fetched onto a ``businesses`` row).

    Returns one of:
      {"success": True, "project_id": ..., "token": ..., "secret_name": ...}
      {"success": False, "reason": "partial_sandbox_config"}
      {"success": False, "reason": "missing_secret", "secret_name": ...}

    CRITICAL SAFETY: this function never returns a bucks-ai fallback target.
    When ``vercel_project_id`` or ``vercel_token_secret_name`` is missing —
    a "partial" sandbox_config — the caller must skip the deploy for that
    business entirely rather than substituting the runner's own
    ``VERCEL_PROJECT_ID``/``VERCEL_TOKEN``.
    """
    sandbox_config = sandbox_config or {}
    project_id = (sandbox_config.get("vercel_project_id") or "").strip()
    secret_name = (sandbox_config.get("vercel_token_secret_name") or "").strip()
    if not project_id or not secret_name:
        return {"success": False, "reason": "partial_sandbox_config"}

    token_result = resolve_scoped_vercel_token(secret_name)
    if not token_result["success"]:
        return {"success": False, "reason": "missing_secret", "secret_name": secret_name}

    return {
        "success": True,
        "project_id": project_id,
        "token": token_result["token"],
        "secret_name": secret_name,
    }
