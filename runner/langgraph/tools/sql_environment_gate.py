"""SQL environment-aware approval policy gate.

Decides whether SQL approval is required before applying a migration, based
on the target environment (production / staging / development / preview) and
a configurable approval policy.

Policy values:
  auto                        — never require approval via this gate;
                                falls back to the legacy REQUIRE_SQL_APPROVAL flag.
  require_on_production       — require approval only when SQL_ENVIRONMENT=production.
  require_on_warning          — require approval when the scan has warnings or blocked terms.
  always_require              — always require approval regardless of environment.

Environment detection order:
  1. SQL_ENVIRONMENT env var (explicit).
  2. Inferred from SUPABASE_URL: contains "prod" → production,
     contains "stag" → staging, otherwise → development.
"""

import re


_PROD_URL_PATTERN = re.compile(r"prod", re.IGNORECASE)
_STAG_URL_PATTERN = re.compile(r"stag", re.IGNORECASE)

_KNOWN_POLICIES = frozenset(
    {"auto", "require_on_production", "require_on_warning", "always_require"}
)
_KNOWN_ENVIRONMENTS = frozenset({"production", "staging", "development", "preview"})


def infer_environment(supabase_url: str | None) -> str:
    """Infer deployment environment from the Supabase URL when SQL_ENVIRONMENT is unset."""
    if not supabase_url:
        return "development"
    if _PROD_URL_PATTERN.search(supabase_url):
        return "production"
    if _STAG_URL_PATTERN.search(supabase_url):
        return "staging"
    return "development"


def evaluate_sql_approval_policy(
    scan_result: dict,
    sql_environment: str,
    policy: str,
) -> dict:
    """Return whether SQL approval is required under the given policy.

    Args:
        scan_result: Output of sql_guard.scan_sql_text / scan_sql_file
                     (keys: ok, warnings, blocked_terms).
        sql_environment: Target environment string (production / staging /
                         development / preview).
        policy: One of the policy values listed at the module top.

    Returns:
        dict with keys:
          approval_required (bool)  — True when human approval must precede apply.
          reason (str)              — Human-readable explanation.
    """
    env = (sql_environment or "development").lower().strip()
    pol = (policy or "require_on_production").lower().strip()

    if pol not in _KNOWN_POLICIES:
        return {
            "approval_required": True,
            "reason": f"Unknown SQL_APPROVAL_POLICY '{policy}' — defaulting to require approval.",
        }

    if pol == "auto":
        return {
            "approval_required": False,
            "reason": "SQL_APPROVAL_POLICY=auto: approval delegated to legacy REQUIRE_SQL_APPROVAL flag.",
        }

    if pol == "always_require":
        return {
            "approval_required": True,
            "reason": "SQL_APPROVAL_POLICY=always_require: approval required in all environments.",
        }

    if pol == "require_on_production":
        required = env == "production"
        return {
            "approval_required": required,
            "reason": (
                f"SQL_APPROVAL_POLICY=require_on_production: environment is '{env}' — "
                + ("approval required." if required else "no approval needed.")
            ),
        }

    if pol == "require_on_warning":
        warnings = scan_result.get("warnings") or []
        blocked = scan_result.get("blocked_terms") or []
        has_concern = bool(warnings or blocked)
        return {
            "approval_required": has_concern,
            "reason": (
                "SQL_APPROVAL_POLICY=require_on_warning: "
                + (
                    f"scan has {len(warnings)} warning(s) and {len(blocked)} blocked term(s) — approval required."
                    if has_concern
                    else "scan is clean — no approval needed."
                )
            ),
        }

    # Unreachable, but be safe.
    return {
        "approval_required": True,
        "reason": f"Unhandled policy '{policy}' — defaulting to require approval.",
    }
