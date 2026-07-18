"""M4b: runner executes missions against a foreign (business) repo.

Lets the runner work outside its own repo, safely, when a claimed mission's
business has a ``sandbox_config`` (see
``supabase/migrations/0004_businesses_sandbox_config.sql``):

    {"repo_full_name": "owner/name", "github_token_secret_name": "ENV_VAR_NAME"}

``prepare_business_repo`` is the single entry point ``graph.py`` calls: it
validates the sandbox config, refuses anything that resolves to the bucks-ai
repo itself, resolves a scoped GitHub token from the environment (by name —
never a stored value), clones/fetches the target repo into an isolated
per-business workspace, and returns the local path to use as that mission's
``repo_path`` override.

CRITICAL SAFETY invariants (all unit-tested in
``tests/test_foreign_repo_workspace.py``):
  - A business mission must NEVER run with ``repo_path`` equal to the
    bucks-ai repo — enforced twice: ``is_bucks_ai_repo`` rejects the
    sandbox's ``repo_full_name`` before any clone happens, and
    ``guard_business_repo_path`` re-checks the resolved workspace path
    right before it is handed back (defense in depth).
  - The scoped GitHub token is read fresh from the environment by name at
    each use and is never written to a task dict, state, or a log event —
    only the secret's *name* is ever persisted or logged (see AGENTS.md,
    "Never print secrets"). Git subprocess output is redacted before it is
    logged, since git error messages echo the credentialed clone URL verbatim
    on failure.
"""
import os
import subprocess
from pathlib import Path
from typing import Optional

from tools.log_tools import log_event

_WORKSPACES_DIRNAME = ".workspaces"


class ForeignRepoGuardError(Exception):
    """Raised when a business mission's resolved repo_path is unsafe."""


def _safe_path_segment(value: str) -> str:
    """Strip path separators/traversal so a business_id can never escape
    the workspaces directory (defense in depth — business_id comes from
    Supabase and is expected to be a UUID, but nothing enforces that here)."""
    return "".join(c for c in str(value) if c.isalnum() or c in ("-", "_")) or "unknown"


def workspace_dir_for_business(business_id: str, cfg=None) -> str:
    """Return ``runner/langgraph/.workspaces/<business_id>/`` — gitignored,
    created on demand by ``ensure_workspace``."""
    runner_dir = Path(__file__).resolve().parent.parent
    return str(runner_dir / _WORKSPACES_DIRNAME / _safe_path_segment(business_id))


def _normalize_repo_full_name(value: Optional[str]) -> str:
    return (value or "").strip().strip("/").lower()


def is_bucks_ai_repo(repo_full_name: str, cfg=None) -> bool:
    """True when *repo_full_name* (``owner/name``) refers to the bucks-ai repo
    itself — a sandbox_config must never be allowed to point here."""
    if cfg is None:
        from config import get_config
        cfg = get_config()
    candidate = _normalize_repo_full_name(repo_full_name)
    if not candidate:
        return False
    known = {_normalize_repo_full_name(cfg.github_repo), "bucks-ai/bucks-ai"}
    known.discard("")
    return candidate in known


def resolve_scoped_github_token(secret_name: str) -> dict:
    """Read a GitHub token from the environment by *secret_name*.

    Returns ``{"success": True, "token": ..., "secret_name": ...}`` or
    ``{"success": False, "error": "missing_secret", "secret_name": ...}``.
    Callers must only ever surface ``secret_name`` in logs/outbox text —
    never ``token``.
    """
    secret_name = (secret_name or "").strip()
    if not secret_name:
        return {"success": False, "error": "no_secret_name"}
    token = os.environ.get(secret_name)
    if not token:
        return {"success": False, "error": "missing_secret", "secret_name": secret_name}
    return {"success": True, "token": token, "secret_name": secret_name}


def _redact(text: str, token: Optional[str]) -> str:
    if token and text and token in text:
        return text.replace(token, "***REDACTED***")
    return text


def _run_git(args: list[str], cwd: Optional[str], token: Optional[str] = None, timeout: int = 120) -> dict:
    """Run a git subprocess. Never uses ``tools.shell_tools.run_command`` here:
    that helper logs the raw command + output verbatim on failure, and git's
    own error messages echo a credentialed clone URL back on auth/network
    failure — this wrapper redacts the token from everything it logs first."""
    try:
        result = subprocess.run(
            ["git"] + args, cwd=cwd, capture_output=True, text=True, timeout=timeout,
        )
        output = _redact((result.stdout or "") + (result.stderr or ""), token)
        success = result.returncode == 0
        if not success:
            log_event("error", {
                "op": "foreign_repo_git",
                "args": [_redact(a, token) for a in args],
                "returncode": result.returncode,
                "output": output[:500],
            })
        return {"success": success, "output": output.strip()}
    except subprocess.TimeoutExpired:
        return {"success": False, "output": "", "error": "timeout"}
    except Exception as e:
        return {"success": False, "output": "", "error": _redact(str(e), token)}


def ensure_workspace(
    business_id: str,
    repo_full_name: str,
    token: str,
    cfg=None,
    git_run=None,
) -> dict:
    """Clone (first run) or fetch (subsequent runs) *repo_full_name* into the
    isolated per-business workspace directory.

    Returns ``{"success": bool, "path": str, "cloned": bool, "fetched": bool,
    "error": Optional[str]}``. ``git_run`` is injectable
    (``git_run(args, cwd, token, timeout) -> {"success", "output", ...}``) so
    tests can exercise this without a real git binary or network.
    """
    git_run = git_run or _run_git
    path = workspace_dir_for_business(business_id, cfg)
    os.makedirs(os.path.dirname(path), exist_ok=True)

    if os.path.isdir(os.path.join(path, ".git")):
        result = git_run(["fetch", "origin"], path, token)
        if not result["success"]:
            return {
                "success": False, "path": path, "cloned": False, "fetched": False,
                "error": result.get("error") or result.get("output"),
            }
        return {"success": True, "path": path, "cloned": False, "fetched": True}

    clone_url = f"https://x-access-token:{token}@github.com/{repo_full_name}.git"
    result = git_run(["clone", clone_url, path], None, token)
    if not result["success"]:
        return {
            "success": False, "path": path, "cloned": False, "fetched": False,
            "error": result.get("error") or result.get("output"),
        }
    return {"success": True, "path": path, "cloned": True, "fetched": False}


def guard_business_repo_path(repo_path: str, cfg=None) -> None:
    """Hard guardrail: raise if *repo_path* resolves to the bucks-ai repo.

    Defense in depth — ``ensure_workspace`` always constructs a path under
    ``.workspaces/<business_id>/``, so this should never trip, but it is the
    last check before a business mission's repo_path is handed back to the
    caller, catching any future code path that might set it incorrectly.
    """
    if cfg is None:
        from config import get_config
        cfg = get_config()
    if os.path.realpath(repo_path) == os.path.realpath(cfg.repo_path):
        raise ForeignRepoGuardError(
            f"refusing to run a business mission with repo_path == bucks-ai repo ({cfg.repo_path})"
        )


def fetch_business_by_id(business_id: str) -> Optional[dict]:
    """Return the Supabase ``businesses`` row for *business_id*, or ``None``
    on any error (degrades gracefully, mirroring tools/seeded_mission_queue.py)."""
    try:
        from config import get_config
        from supabase import create_client
        cfg = get_config()
        client = create_client(cfg.supabase_url, cfg.supabase_service_role_key)
        result = (
            client.table("businesses").select("*").eq("id", business_id).limit(1).execute()
        )
        rows = result.data or []
        return rows[0] if rows else None
    except Exception as e:
        log_event("foreign_repo_workspace_error", {
            "op": "fetch_business_by_id", "business_id": business_id, "error": str(e),
        })
        return None


def prepare_business_repo(task: dict, business: dict, cfg=None, git_run=None) -> dict:
    """Top-level orchestration: resolve a business mission's sandboxed repo.

    Returns one of:
      {"success": True, "repo_path": ..., "repo_full_name": ..., "github_token_secret_name": ...}
      {"success": False, "reason": "no_sandbox_config"}
      {"success": False, "reason": "forbidden_repo", "repo_full_name": ...}
      {"success": False, "reason": "missing_secret", "secret_name": ...}
      {"success": False, "reason": "workspace_error", "error": ...}
    """
    if cfg is None:
        from config import get_config
        cfg = get_config()

    sandbox = (business or {}).get("sandbox_config") or {}
    repo_full_name = (sandbox.get("repo_full_name") or "").strip()
    secret_name = (sandbox.get("github_token_secret_name") or "").strip()
    business_id = str((business or {}).get("id") or task.get("business_id") or "")

    if not repo_full_name or not secret_name or not business_id:
        return {"success": False, "reason": "no_sandbox_config"}

    if is_bucks_ai_repo(repo_full_name, cfg):
        log_event("business_repo_forbidden", {
            "business_id": business_id, "repo_full_name": repo_full_name,
        })
        return {"success": False, "reason": "forbidden_repo", "repo_full_name": repo_full_name}

    token_result = resolve_scoped_github_token(secret_name)
    if not token_result["success"]:
        return {"success": False, "reason": "missing_secret", "secret_name": secret_name}

    workspace = ensure_workspace(business_id, repo_full_name, token_result["token"], cfg, git_run)
    if not workspace["success"]:
        return {"success": False, "reason": "workspace_error", "error": workspace.get("error")}

    guard_business_repo_path(workspace["path"], cfg)

    return {
        "success": True,
        "repo_path": workspace["path"],
        "repo_full_name": repo_full_name,
        "github_token_secret_name": secret_name,
    }
