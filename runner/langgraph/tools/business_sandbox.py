"""M4b sandbox-config reconciliation: the runner's read path onto
``business_sandbox`` — the single source of truth for per-business sandbox
configuration.

The founder-facing Settings UI (``src/lib/sandbox.ts``,
``src/app/api/businesses/[id]/sandbox/route.ts``) writes
``repo_full_name`` / ``vercel_project_id`` / ``github_token_secret_name`` /
``vercel_token_secret_name`` into the RLS-protected, typed
``business_sandbox`` table (``supabase/migrations/0004_business_sandbox.sql``).
Every runner consumer of a business's sandbox config
(``tools/foreign_repo_workspace.py::prepare_business_repo``,
``tools/seeded_mission_queue.py::evaluate_business_mission_claim``,
``graph.py::_resolve_business_deploy_target``) reads it through
``fetch_business_sandbox`` below, so the founder's Settings tab actually
configures what the runner executes against.

DEPRECATED: ``businesses.sandbox_config`` (JSONB; see
``supabase/migrations/0004_businesses_sandbox_config.sql`` and
``0005_business_sandbox_config_vercel_target.sql``) is no longer read or
written anywhere in the runner. The column is left in place (no destructive
migration) but is dead — see
``supabase/migrations/0006_deprecate_businesses_sandbox_config.sql``. A
business whose only populated sandbox data lives on that legacy column is
correctly treated as unconfigured; there is no fallback onto it.
"""
from typing import Optional

from tools.log_tools import log_event

SANDBOX_FIELDS = (
    "repo_full_name",
    "vercel_project_id",
    "github_token_secret_name",
    "vercel_token_secret_name",
)


def fetch_business_sandbox(business_id: str) -> Optional[dict]:
    """Return the ``business_sandbox`` row for *business_id*, or ``None`` when
    no row exists or on any error (degrades gracefully, mirroring
    ``tools/foreign_repo_workspace.py::fetch_business_by_id``).

    Mirrors ``src/lib/sandbox.ts::getSandboxConfigForBusiness`` — the returned
    dict carries the same field names: ``repo_full_name``,
    ``vercel_project_id``, ``github_token_secret_name``,
    ``vercel_token_secret_name``, ``status``, plus row metadata.
    """
    try:
        from config import get_config
        from supabase import create_client
        cfg = get_config()
        client = create_client(cfg.supabase_url, cfg.supabase_service_role_key)
        result = (
            client.table("business_sandbox")
            .select("*")
            .eq("business_id", business_id)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        return rows[0] if rows else None
    except Exception as e:
        log_event("business_sandbox_error", {
            "op": "fetch_business_sandbox", "business_id": business_id, "error": str(e),
        })
        return None


def is_sandbox_configured(sandbox: Optional[dict]) -> bool:
    """True when every field in ``SANDBOX_FIELDS`` is set on *sandbox*.

    Mirrors ``src/lib/sandbox.ts::computeSandboxStatus(...) == "configured"``.
    ``None`` (no ``business_sandbox`` row at all) is always unconfigured.
    """
    sandbox = sandbox or {}
    return all(str(sandbox.get(field) or "").strip() for field in SANDBOX_FIELDS)
