"""Environment ownership tooling — M4c.

Implements the proactive infrastructure checks the runner performs AS PART OF
finishing each task, not only when a human triggers them:

  check_sentry_after_deploy        — look for new Sentry errors since a given
                                     timestamp; logs results, never halts loop.
  should_deploy_for_sha_mismatch   — pure decision: given a startup-preflight
                                     production_sha check result, should the
                                     runner trigger a deploy right now?
  trigger_deploy_for_sha_mismatch  — trigger the deploy when the SHA is stale.
  check_posthog_analytics_health   — probe that PostHog is recording events;
                                     logs results, never halts the loop.
  verify_push_destination          — re-assert origin remote after push to
                                     confirm business commits landed in the
                                     right repo.

All functions degrade gracefully on infra/credential failure (fail-open): they
log a ``*_degraded`` or ``*_failed`` event and return a structured error result
so callers can log and continue rather than halt the loop.
"""
from __future__ import annotations

from typing import Optional

from tools.log_tools import log_event


# ---------------------------------------------------------------------------
# Sentry post-deploy check
# ---------------------------------------------------------------------------

def check_sentry_after_deploy(since_iso: Optional[str] = None) -> dict:
    """Fetch Sentry issues first seen since *since_iso* and log a summary.

    FAIL-OPEN: if Sentry is not configured or the request fails, logs a
    ``sentry_post_deploy_degraded`` event and returns
    ``{"available": False, ...}`` — the loop always continues.

    Returns::

        {"available": True,  "total": int, "by_level": dict, "issues": list}
        {"available": False, "reason": str}
    """
    try:
        from tools.sentry_tools import list_new_issues, summarize_issues, format_issue_summary
        from config import get_config
        cfg = get_config()
        if not cfg.has_sentry:
            log_event("sentry_post_deploy_degraded", {
                "reason": "no Sentry credentials",
                "since_iso": since_iso,
            })
            return {"available": False, "reason": "no_sentry_config"}

        issues = list_new_issues(since_iso or "")
        summary = summarize_issues(issues)
        text = format_issue_summary(summary)
        log_event("sentry_post_deploy_checked", {
            "since_iso": since_iso,
            "total": summary["total"],
            "by_level": summary["by_level"],
            "total_events": summary["total_events"],
            "summary": text,
        })
        return {
            "available": True,
            "total": summary["total"],
            "by_level": summary["by_level"],
            "issues": summary["top_issues"],
            "text": text,
        }
    except Exception as e:
        log_event("sentry_post_deploy_degraded", {"reason": str(e), "since_iso": since_iso})
        return {"available": False, "reason": str(e)}


# ---------------------------------------------------------------------------
# Production SHA mismatch → trigger deploy
# ---------------------------------------------------------------------------

def should_deploy_for_sha_mismatch(sha_check: dict, auto_deploy: bool) -> bool:
    """Pure decision: should the runner trigger a deploy to fix a SHA mismatch?

    Returns True only when the production_sha preflight check explicitly FAILED
    (status == 'fail') and auto_deploy is on. WARN (could not determine) → no
    deploy (transient — may resolve without a push). PASS or SKIP → no action.
    """
    if not auto_deploy:
        return False
    return (sha_check or {}).get("status") == "fail"


def trigger_deploy_for_sha_mismatch(cfg, sha_check: dict) -> dict:
    """Trigger a Vercel deploy when production is serving a stale commit.

    FAIL-OPEN: if the deploy trigger raises or returns an error, logs
    ``sha_mismatch_deploy_failed`` and returns a failure result — the loop
    always continues. The next successful push will fix production anyway.

    Returns the trigger_deploy result dict or ``{"success": False, "reason": …}``
    when skipped (SHA current, auto_deploy off, or token missing).
    """
    if not should_deploy_for_sha_mismatch(sha_check, cfg.auto_deploy):
        return {"success": False, "reason": "sha_current_or_deploy_disabled"}
    if not cfg.has_vercel:
        log_event("sha_mismatch_deploy_failed", {"reason": "no VERCEL_TOKEN"})
        return {"success": False, "reason": "no_vercel_token"}

    origin_sha = (sha_check.get("data") or {}).get("origin_sha", "?")
    deployed_sha = (sha_check.get("data") or {}).get("deployed_sha", "?")
    log_event("sha_mismatch_deploy_triggered", {
        "origin_sha": origin_sha,
        "deployed_sha": deployed_sha,
        "project_id": cfg.vercel_project_id,
        "reason": "production is serving a stale commit; triggering auto-deploy",
    })
    try:
        from tools.vercel_tools import trigger_deploy
        result = trigger_deploy(project_id=cfg.vercel_project_id, poll=True)
        event = "sha_mismatch_deploy_completed" if result.get("success") else "sha_mismatch_deploy_failed"
        log_event(event, {
            "origin_sha": origin_sha,
            "deployed_sha": deployed_sha,
            "deploy_success": result.get("success"),
        })
        return result
    except Exception as e:
        log_event("sha_mismatch_deploy_failed", {"error": str(e)})
        return {"success": False, "reason": str(e)}


# ---------------------------------------------------------------------------
# PostHog analytics health probe
# ---------------------------------------------------------------------------

def check_posthog_analytics_health(event_names: list[str], days: int = 7) -> dict:
    """Verify that PostHog is recording the given *event_names*.

    FAIL-OPEN: if PostHog is unconfigured or any query fails, logs a
    ``posthog_analytics_degraded`` event and returns
    ``{"available": False, ...}`` — the loop always continues.

    Returns::

        {"available": True,  "events": [{"event": str, "days": int, "count": int}, …]}
        {"available": False, "reason": str}
    """
    try:
        from tools.posthog_tools import query_event_count
        from config import get_config
        cfg = get_config()
        if not cfg.has_posthog:
            log_event("posthog_analytics_degraded", {
                "reason": "no POSTHOG_PERSONAL_API_KEY/POSTHOG_PROJECT_ID",
            })
            return {"available": False, "reason": "no_posthog_config"}

        results = []
        for event in (event_names or []):
            r = query_event_count(event, days=days)
            results.append(r)

        available_results = [r for r in results if r.get("available")]
        log_event("posthog_analytics_health_checked", {
            "event_count": len(event_names or []),
            "available_count": len(available_results),
            "events": [
                {"event": r.get("event"), "days": r.get("days"), "count": r.get("count")}
                for r in available_results
            ],
        })
        return {"available": True, "events": results}
    except Exception as e:
        log_event("posthog_analytics_degraded", {"reason": str(e)})
        return {"available": False, "reason": str(e)}


# ---------------------------------------------------------------------------
# Push-destination verification
# ---------------------------------------------------------------------------

def verify_push_destination(repo_path: str, expected_repo_full_name: str) -> dict:
    """Assert *repo_path*'s ``origin`` still resolves to *expected_repo_full_name*
    after a push, confirming the commit landed in the right repo.

    HARD-FAIL on mismatch (returns ``{"ok": False}``): callers must treat this
    as a security boundary — a commit that went to the wrong repo cannot be
    walked back by the runner alone.

    FAIL-OPEN on infra errors (remote unreachable, git subprocess error):
    returns ``{"ok": True, "degraded": True}`` so the loop continues when a
    transient git issue prevents verification. Logged loudly as
    ``push_destination_verify_degraded``.
    """
    if not repo_path or not expected_repo_full_name:
        log_event("push_destination_verify_skipped", {
            "reason": "missing repo_path or expected_repo_full_name",
        })
        return {"ok": True, "degraded": True, "reason": "missing_args"}

    try:
        from tools.dispatch_preflight import verify_origin_remote
        result = verify_origin_remote(repo_path, expected_repo_full_name)
        if result["ok"]:
            log_event("push_destination_verified", {
                "repo": result["actual"],
                "expected": result["expected"],
            })
        else:
            log_event("push_destination_mismatch", {
                "expected": result["expected"],
                "actual": result["actual"],
                "reason": result["reason"],
                "repo_path": repo_path,
            })
        return result
    except Exception as e:
        log_event("push_destination_verify_degraded", {
            "error": str(e),
            "repo_path": repo_path,
            "expected": expected_repo_full_name,
        })
        # Transient error — degrade to pass so the loop continues.
        return {"ok": True, "degraded": True, "reason": str(e)}
