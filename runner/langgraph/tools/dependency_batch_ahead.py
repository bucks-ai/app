"""Dependency batch-ahead — ONE consolidated credential request at startup.

Scans the entire approved task queue, extracts every external dependency the
roadmap will need, and fires a single consolidated request the first time each
session. Goal: one 30-minute founder session for the whole roadmap instead of
N ambushes over weeks (M4c phone-push doctrine).

The dependency list is GENEROUS, not minimal. Per STRATEGY.md §6.3: never cut
corners to avoid asking — tool acquisition is pre-approved by the founder.

Phone push (ntfy.sh) fires once with the count. Slack gets the full list via
the ``dependency_batch_request`` event. The loop never halts — this is a report
not a gate.

Idempotency: the outbox file is written once. Subsequent startups see it and
skip. After the founder provisions everything they create
inbox/dependency_batch_provided.txt to signal completion.
"""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from tools.log_tools import log_event
from tools.resource_gate import available_credential_names

_ENV_NAME_RE = re.compile(r"[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)+")

_RUNTIME_DIR = Path(__file__).parent.parent / ".runtime"
_OUTBOX_DIR = Path(__file__).parent.parent / "outbox"
_INBOX_DIR = Path(__file__).parent.parent / "inbox"

# Every credential the roadmap will ever need, with a human-readable purpose
# so the founder knows exactly what to provision and where.
# Organised by vendor — keep this list generous.
_ROADMAP_DEPS: dict[str, str] = {
    # AI workers — the runner cannot run at all without these
    "ANTHROPIC_API_KEY": (
        "Anthropic API key — Claude workers (signup: console.anthropic.com; "
        "free tier insufficient — use Pay-as-you-go; paste into .env as ANTHROPIC_API_KEY)"
    ),
    "OPENAI_API_KEY": (
        "OpenAI API key — ChatGPT planner + Codex workers (signup: platform.openai.com; "
        "paste into .env as OPENAI_API_KEY)"
    ),
    # GitHub — parent org under which child repos are provisioned
    "GITHUB_TOKEN": (
        "GitHub personal access token — parent credential for repo creation, deploy keys, PRs "
        "(github.com → Settings → Developer settings → Personal access tokens → Fine-grained; "
        "scopes: repo, admin:org read; paste into .env as GITHUB_TOKEN)"
    ),
    "PROVISIONING_GITHUB_ORG": (
        "GitHub org name — the org under which child business repos are created "
        "(e.g. bucks-ai-apps; create at github.com/organizations/new if needed; "
        "paste into .env as PROVISIONING_GITHUB_ORG)"
    ),
    # Vercel — hosting for main app and child business deployments
    "VERCEL_TOKEN": (
        "Vercel API token — deploy main app and provision child projects "
        "(vercel.com → Settings → Tokens → Create; paste into .env as VERCEL_TOKEN)"
    ),
    "VERCEL_PROJECT_ID": (
        "Vercel project ID for the bucks.ai main app "
        "(vercel.com → your project → Settings → General → Project ID; "
        "paste into .env as VERCEL_PROJECT_ID)"
    ),
    "PROVISIONING_VERCEL_TEAM_ID": (
        "Vercel team ID — required when projects are created under a team "
        "(vercel.com → your team → Settings → General → Team ID; "
        "paste into .env as PROVISIONING_VERCEL_TEAM_ID; optional if using personal account)"
    ),
    # Supabase — main database + child project provisioning
    "SUPABASE_URL": (
        "Supabase URL for the bucks.ai main project "
        "(app.supabase.com → your project → Settings → API → Project URL; "
        "paste into .env as SUPABASE_URL)"
    ),
    "SUPABASE_SERVICE_ROLE_KEY": (
        "Supabase service-role key — bypasses RLS for runner SQL operations "
        "(app.supabase.com → your project → Settings → API → service_role key; "
        "paste into .env as SUPABASE_SERVICE_ROLE_KEY)"
    ),
    "SUPABASE_MANAGEMENT_API_KEY": (
        "Supabase Management API key — creates child projects via API "
        "(app.supabase.com → Account → Access Tokens → Generate new token; "
        "paste into .env as SUPABASE_MANAGEMENT_API_KEY)"
    ),
    "SUPABASE_ORG_ID": (
        "Supabase org ID — required for child project creation "
        "(app.supabase.com → your org → Settings → General → Organisation ID; "
        "paste into .env as SUPABASE_ORG_ID)"
    ),
    # Notifications
    "SLACK_WEBHOOK_URL": (
        "Slack incoming webhook URL — runner activity log "
        "(api.slack.com → Your Apps → Incoming Webhooks → Add New Webhook; "
        "paste into .env as SLACK_WEBHOOK_URL)"
    ),
    "NTFY_TOPIC": (
        "ntfy.sh topic name — phone push for credential requests only "
        "(ntfy.sh → no signup needed; pick any unique topic name e.g. bucks-ai-RANDOMSUFFIX; "
        "install ntfy app on phone, subscribe to the same topic; "
        "paste the topic name into .env as NTFY_TOPIC)"
    ),
    # Observability
    "SENTRY_AUTH_TOKEN": (
        "Sentry auth token — post-deploy error monitoring "
        "(sentry.io → Settings → Developer Settings → Auth Tokens; "
        "paste into .env as SENTRY_AUTH_TOKEN)"
    ),
    # Outreach / transactional email (needed for M5 business builds)
    "RESEND_API_KEY": (
        "Resend API key — transactional email for customer businesses "
        "(resend.com → API Keys → Create API Key; "
        "paste into .env as RESEND_API_KEY)"
    ),
    # Payments (needed for M5 Stripe Connect flows)
    "STRIPE_SECRET_KEY": (
        "Stripe secret key — Connect sub-accounts for customer payment flows "
        "(dashboard.stripe.com → Developers → API Keys → Restricted key; "
        "scopes: read/write on Connect; paste into .env as STRIPE_SECRET_KEY)"
    ),
    # Twilio — voice/SMS for customer businesses
    "TWILIO_ACCOUNT_SID": (
        "Twilio master account SID — parent credential for creating subaccounts "
        "(console.twilio.com → Account → General Settings → Account SID; "
        "paste into .env as TWILIO_ACCOUNT_SID)"
    ),
    "TWILIO_AUTH_TOKEN": (
        "Twilio master auth token — paired with TWILIO_ACCOUNT_SID "
        "(console.twilio.com → Account → General Settings → Auth Token; "
        "paste into .env as TWILIO_AUTH_TOKEN)"
    ),
    # PostHog — analytics child project provisioning (Type B: org → projects API)
    "POSTHOG_ORG_ID": (
        "PostHog organisation slug — required for child project creation via API "
        "(posthog.com → your org → Settings → General → Organisation ID/slug; "
        "paste into .env as POSTHOG_ORG_ID)"
    ),
}


def _load_queued_tasks() -> list[dict]:
    """Load tasks in queued or blocked state from the runtime queue."""
    p = _RUNTIME_DIR / "tasks.local.json"
    if not p.exists():
        return []
    try:
        tasks = json.loads(p.read_text())
        return [
            t for t in tasks
            if isinstance(t, dict) and t.get("status") in ("queued", "blocked")
        ]
    except Exception:
        return []


def _format_batch_request(missing: list[dict], inbox_filename: str) -> str:
    """Human-readable outbox file — no secret values."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    lines = [
        "# Roadmap Dependency Batch — Consolidated Credential Request",
        f"# Generated: {now}",
        "",
        "The runner scanned the entire approved roadmap and found the following",
        "credentials not yet provisioned. Provision them ALL in one session (~30 min).",
        "",
        "When done, create this file to unblock the runner:",
        "",
        f"    touch inbox/{inbox_filename}",
        "",
        "This request will NOT repeat once the inbox file exists.",
        "",
        "─" * 72,
        "",
        f"{'Credential':<42} Purpose / Setup",
        "─" * 72,
    ]
    for item in missing:
        name = item["name"]
        purpose = item["purpose"]
        lines.append(f"\n### {name}")
        lines.append(f"  {purpose}")

    lines += [
        "",
        "─" * 72,
        "",
        "SECURITY NOTE: Do NOT paste secret values into this file or the inbox",
        "file. Add each credential to runner/langgraph/.env as:",
        "  CREDENTIAL_NAME=<value>",
        "The inbox file is used only as an 'unblock' signal — it is never read.",
        "",
    ]
    return "\n".join(lines) + "\n"


def run_batch_ahead_check(
    available: Optional[set] = None,
    *,
    force: bool = False,
) -> dict:
    """Scan roadmap dependencies and issue one consolidated credential request.

    Idempotent: skips when the outbox file already exists (``force=False``) or
    when the inbox fulfillment file exists (already done). Returns a summary
    dict so callers can log or surface the result.

    Returns ``{"ran": bool, "status": str, "missing_count": int, "missing": list}``.
    """
    _OUTBOX_DIR.mkdir(parents=True, exist_ok=True)
    _INBOX_DIR.mkdir(parents=True, exist_ok=True)

    inbox_filename = "dependency_batch_provided.txt"
    outbox_path = _OUTBOX_DIR / "dependency_batch_request.txt"
    inbox_path = _INBOX_DIR / inbox_filename

    if inbox_path.exists():
        log_event("dependency_batch_ahead", {"status": "fulfilled", "ran": False})
        return {"ran": False, "status": "fulfilled", "missing_count": 0, "missing": []}

    if outbox_path.exists() and not force:
        log_event("dependency_batch_ahead", {"status": "already_sent", "ran": False})
        return {"ran": False, "status": "already_sent", "missing_count": 0, "missing": []}

    if available is None:
        try:
            from config import get_config
            available = available_credential_names(config=get_config())
        except Exception:
            available = set()

    missing = [
        {"name": name, "purpose": purpose}
        for name, purpose in _ROADMAP_DEPS.items()
        if name not in available
    ]

    if not missing:
        log_event("dependency_batch_ahead", {
            "status": "all_present", "ran": True, "missing_count": 0,
        })
        return {"ran": True, "status": "all_present", "missing_count": 0, "missing": []}

    outbox_path.write_text(_format_batch_request(missing, inbox_filename))

    log_event("dependency_batch_request", {
        "count": len(missing),
        "missing": [m["name"] for m in missing],
        "outbox": str(outbox_path),
        "inbox_to_create": f"inbox/{inbox_filename}",
        "message": (
            f"{len(missing)} roadmap credential(s) needed — "
            f"check outbox/dependency_batch_request.txt"
        ),
    })

    return {
        "ran": True,
        "status": "pending",
        "missing_count": len(missing),
        "missing": missing,
        "outbox": str(outbox_path),
    }
