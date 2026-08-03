"""Resolve the base URL post-deploy browser harnesses (E2E, UI flow) should target.

Pure/side-effect-free so the resolution priority — ``E2E_BASE_URL`` always wins
over the Vercel-reported deploy URL — is unit-testable without a real deployment.
"""
from typing import Optional


def resolve_target_url(
    e2e_base_url: Optional[str],
    deploy_result: Optional[dict],
) -> tuple[Optional[str], Optional[str]]:
    """Return ``(url, source)`` for post-deploy browser validation.

    ``e2e_base_url`` (``E2E_BASE_URL``) always wins when set. Otherwise falls
    back to the URL Vercel reported for the deployment on
    ``deploy_result["url"]`` (``deployment_url`` kept as a legacy fallback
    key). Returns ``(None, None)`` when neither source has a URL.
    """
    if e2e_base_url:
        return e2e_base_url, "env_override"
    deploy = deploy_result or {}
    url = deploy.get("url") or deploy.get("deployment_url")
    if url:
        return url, "deploy_result"
    return None, None
