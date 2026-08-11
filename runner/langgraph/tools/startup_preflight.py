"""Startup preflight — verify production assumptions ONCE, loudly, before any
task is claimed (M4c.0).

The recurring failure shape this exists for: the runner assumes something about
the world that is only true on the founder's laptop, then discovers it 40
minutes into a task, or never. Every check below is a real incident:

- ``pending_migrations`` — ``public._runner_migrations`` existed locally but not
  in the production database, so the M1 RLS migration failed on it; separately,
  three merged additive SQL files were never applied to production and Execute
  500'd for a whole mission (M4a).
- ``production_sha`` / ``vercel_project`` — the Vercel project was not
  git-connected, so ``main`` merged for hours while production served stale code
  and the founder debugged a "missing feature" that was in the repo the whole
  time (M4b).
- ``github_repo`` — a wrong repo name (``testflow`` vs ``testflow-demo``) burned
  a full run before failing at clone.
- ``required_tables`` / ``credentials`` — the same class of assumption, one layer
  down.

CRITICAL BEHAVIOUR: the preflight REPORTS, it does not halt. Only ``git_state``
(dirty tree / wrong branch, per m4c-01) is marked ``halting`` — that is the one
condition under which work is actively unsafe, because workers inherit the
runner's tree. Everything else is a loud Slack warning and the loop continues.
A preflight that blocked would just become a new source of stops, which is
exactly what this mission exists to reduce.

Status vocabulary (per check):

- ``pass`` — the assumption was verified true.
- ``fail`` — the assumption was verified FALSE. Loud, but non-halting unless the
  check also sets ``halting``.
- ``warn`` — could not verify (unreachable API, unreadable ledger). Not knowing
  is worth saying out loud too: the M4b outage was invisible for hours.
- ``skip`` — the integration is not configured at all, so there is nothing to
  verify. Does not affect the overall verdict.

Overall verdict is the worst per-check status: FAIL > WARN > PASS.

Secret hygiene: no function here returns, logs, or embeds a credential value.
Credentials are reported by env-var NAME only, and git remote URLs (which can
embed a scoped token) are never surfaced — only the SHA they resolve to.
"""
from __future__ import annotations

import subprocess
from datetime import datetime
from typing import Callable, Optional

from tools.log_tools import log_event

PASS = "pass"
WARN = "warn"
FAIL = "fail"
SKIP = "skip"

# Skip ranks with pass: an unconfigured integration is not a problem to report,
# it is an absence of something to check.
_STATUS_RANK = {PASS: 0, SKIP: 0, WARN: 1, FAIL: 2}
_OVERALL_BY_RANK = {0: "PASS", 1: "WARN", 2: "FAIL"}
_ICON = {PASS: "+", SKIP: ".", WARN: "~", FAIL: "!"}

# Tables the runner itself reads or writes every session. A missing one does not
# surface until the query that needs it runs, usually mid-task.
DEFAULT_REQUIRED_TABLES = (
    "missions",
    "mission_tasks",
    "agent_runs",
    "businesses",
    "business_sandbox",
)

_MIGRATIONS_DIR_NAME = "supabase/migrations"


def make_check(
    name: str,
    status: str,
    detail: str,
    *,
    halting: bool = False,
    data: Optional[dict] = None,
) -> dict:
    """Build one preflight check result.

    ``halting`` marks the (currently sole) condition under which the loop must
    not proceed — see the module docstring.
    """
    return {
        "name": name,
        "status": status,
        "detail": detail,
        "halting": halting,
        "data": data or {},
    }


# ---------------------------------------------------------------------------
# Individual checks — each is pure given its injected reader
# ---------------------------------------------------------------------------

def check_git_state(repo_path: str, evaluate: Optional[Callable[[str], dict]] = None) -> dict:
    """The one halting check: is the runner's own tree safe to work from?

    Delegates the verdict to ``dispatch_preflight.evaluate_loop_start`` (m4c-01)
    so there is exactly one definition of "safe to start".
    """
    if evaluate is None:
        from tools.dispatch_preflight import evaluate_loop_start
        evaluate = evaluate_loop_start

    verdict = evaluate(repo_path)
    if verdict.get("ok"):
        return make_check(
            "git_state", PASS,
            f"on '{verdict.get('branch')}' with a clean working tree",
        )
    return make_check(
        "git_state", FAIL,
        verdict.get("message") or verdict.get("reason") or "unsafe starting state",
        halting=True,
        data={
            "reason": verdict.get("reason"),
            "branch": verdict.get("branch"),
            "dirty": verdict.get("dirty"),
        },
    )


def check_pending_migrations(
    migrations_dir: str,
    has_database: bool,
    list_fn: Optional[Callable[[str], dict]] = None,
) -> dict:
    """Are all files in ``supabase/migrations`` recorded in the
    ``_runner_migrations`` ledger?

    Pending files are a WARN, not a FAIL: ``check_pending_migrations_if_needed``
    may still auto-apply the additive ones a moment later. The point here is
    that the founder sees the list at startup rather than discovering it from a
    500 in production.
    """
    if not has_database:
        return make_check(
            "pending_migrations", SKIP,
            "DATABASE_URL / DIRECT_DATABASE_URL not configured — ledger not readable",
        )

    if list_fn is None:
        from tools.db_tools import list_pending_migrations
        list_fn = list_pending_migrations

    result = list_fn(migrations_dir)
    if not result.get("success"):
        return make_check(
            "pending_migrations", WARN,
            f"could not read the _runner_migrations ledger: {result.get('error')}",
        )

    data = result.get("data") or {}
    pending = data.get("pending") or []
    if pending:
        return make_check(
            "pending_migrations", WARN,
            f"{len(pending)} migration(s) not in the ledger: {', '.join(pending)}",
            data={"pending": pending},
        )
    return make_check(
        "pending_migrations", PASS,
        f"all {data.get('total_count', 0)} migration(s) recorded in the ledger",
    )


def deployment_commit_sha(deployment: dict) -> str:
    """Extract the source commit SHA from a Vercel deployment record.

    Vercel namespaces the field by git provider (``githubCommitSha``,
    ``gitlabCommitSha``, ``bitbucketCommitSha``); accept any of them so this
    doesn't silently return "" if the project is ever moved.
    """
    meta = (deployment or {}).get("meta") or {}
    for key in ("githubCommitSha", "gitlabCommitSha", "bitbucketCommitSha"):
        sha = meta.get(key)
        if sha:
            return str(sha)
    return ""


def check_production_sha(
    repo_path: str,
    project_id: str,
    has_vercel: bool,
    origin_sha_fn: Optional[Callable[[str], str]] = None,
    deployment_fn: Optional[Callable[[str], dict]] = None,
) -> dict:
    """Is what production actually serves the same commit as ``origin/main``?

    A deploy in flight at loop start legitimately reads as drift — that costs
    one noisy line at startup, which is the trade this mission is explicitly
    willing to make against silently serving stale code for hours (M4b).
    """
    if not has_vercel:
        return make_check("production_sha", SKIP, "VERCEL_TOKEN not configured")
    if not project_id:
        return make_check(
            "production_sha", WARN,
            "VERCEL_PROJECT_ID not set — cannot tell which commit production serves",
        )

    if origin_sha_fn is None:
        origin_sha_fn = origin_main_sha
    if deployment_fn is None:
        from tools.vercel_tools import get_production_deployment
        deployment_fn = get_production_deployment

    origin_sha = origin_sha_fn(repo_path)
    if not origin_sha:
        return make_check(
            "production_sha", WARN,
            "could not resolve origin/main — deployed commit not comparable",
        )

    result = deployment_fn(project_id)
    if not result.get("available"):
        return make_check(
            "production_sha", WARN,
            f"could not read the production deployment: {result.get('error') or result.get('reason')}",
        )

    deployment = result.get("deployment")
    if not deployment:
        return make_check(
            "production_sha", WARN,
            "Vercel reports no production deployment for this project",
        )

    deployed_sha = deployment_commit_sha(deployment)
    if not deployed_sha:
        return make_check(
            "production_sha", WARN,
            "production deployment carries no source commit "
            "(deployed outside git — a CLI/manual deploy?)",
        )

    if deployed_sha[:7].lower() == origin_sha[:7].lower():
        return make_check(
            "production_sha", PASS,
            f"production serves origin/main ({origin_sha[:7]})",
        )
    return make_check(
        "production_sha", FAIL,
        f"production serves {deployed_sha[:7]} but origin/main is {origin_sha[:7]} — "
        f"production is NOT running main (a deploy in flight reads the same way)",
        data={"deployed_sha": deployed_sha[:7], "origin_sha": origin_sha[:7]},
    )


def interpret_vercel_project(project: dict) -> dict:
    """Pure: does this Vercel project record show a git connection?

    Returns ``{"connected": bool, "provider": str, "repo": str}``. A project
    with no ``link`` is the M4b outage: merges to ``main`` produce no deploy at
    all, and nothing anywhere reports an error.
    """
    link = (project or {}).get("link") or {}
    provider = str(link.get("type") or "")
    org = link.get("org") or link.get("owner") or link.get("projectNamespace") or ""
    repo = link.get("repo") or link.get("projectName") or link.get("slug") or ""
    full_name = f"{org}/{repo}" if org and repo else (repo or "")
    return {"connected": bool(link), "provider": provider, "repo": full_name}


def check_vercel_project(
    project_id: str,
    has_vercel: bool,
    fetch: Optional[Callable[[str], dict]] = None,
) -> dict:
    """Is the Vercel project reachable, and is it git-connected?"""
    if not has_vercel:
        return make_check("vercel_project", SKIP, "VERCEL_TOKEN not configured")
    if not project_id:
        return make_check(
            "vercel_project", WARN,
            "VERCEL_PROJECT_ID not set — deploy target unverifiable",
        )

    if fetch is None:
        from tools.vercel_tools import get_project
        fetch = get_project

    result = fetch(project_id)
    if not result.get("available"):
        return make_check(
            "vercel_project", WARN,
            f"Vercel project unreachable: {result.get('error') or result.get('reason')}",
        )

    link = interpret_vercel_project(result.get("project") or {})
    if not link["connected"]:
        return make_check(
            "vercel_project", FAIL,
            "Vercel project is reachable but NOT git-connected — merges to main "
            "will never deploy and production can serve stale code indefinitely",
        )
    provider = link["provider"] or "git"
    target = f" ({provider}: {link['repo']})" if link["repo"] else f" ({provider})"
    return make_check("vercel_project", PASS, f"reachable and git-connected{target}")


def check_github_repo(
    repo_full_name: str,
    has_github: bool,
    fetch: Optional[Callable[[str], dict]] = None,
) -> dict:
    """Does the configured ``GITHUB_REPO`` actually exist for this token?

    The ``testflow`` / ``testflow-demo`` run burned its whole budget before
    failing at clone; a single GET at startup costs one request.
    """
    if not has_github:
        return make_check("github_repo", SKIP, "GITHUB_TOKEN not configured")
    if not repo_full_name:
        return make_check("github_repo", WARN, "GITHUB_REPO not set")

    if fetch is None:
        from tools.github_tools import get_repo
        fetch = get_repo

    result = fetch(repo_full_name)
    if result.get("available"):
        return make_check("github_repo", PASS, f"'{repo_full_name}' is reachable")

    status_code = result.get("status_code")
    if status_code in (403, 404):
        return make_check(
            "github_repo", FAIL,
            f"'{repo_full_name}' does not exist or is not visible to GITHUB_TOKEN "
            f"(HTTP {status_code}) — every clone this session will fail",
            data={"status_code": status_code},
        )
    return make_check(
        "github_repo", WARN,
        f"could not reach '{repo_full_name}': {result.get('error')}",
    )


def check_required_tables(
    tables: tuple,
    exists_fn: Optional[Callable[[str], Optional[bool]]] = None,
) -> dict:
    """Are the tables the runner queries every session actually present?

    ``exists_fn(table)`` returns True / False / None, where None means "could
    not determine" — reported separately from a confirmed absence so an
    unreachable database is never mistaken for a missing schema.
    """
    tables = tuple(tables or ())
    if not tables:
        return make_check("required_tables", SKIP, "no required tables configured")
    if exists_fn is None:
        return make_check(
            "required_tables", SKIP,
            "no database or Supabase credentials — table presence unverifiable",
        )

    missing, unknown = [], []
    for table in tables:
        exists = exists_fn(table)
        if exists is None:
            unknown.append(table)
        elif not exists:
            missing.append(table)

    if missing:
        return make_check(
            "required_tables", FAIL,
            f"{len(missing)} required table(s) absent: {', '.join(missing)}",
            data={"missing": missing, "unknown": unknown},
        )
    if unknown:
        return make_check(
            "required_tables", WARN,
            f"could not verify {len(unknown)} table(s): {', '.join(unknown)}",
            data={"unknown": unknown},
        )
    return make_check("required_tables", PASS, f"all {len(tables)} required table(s) present")


def required_credentials(config_snapshot: dict) -> list[dict]:
    """Pure: which credentials does THIS configuration actually depend on?

    Only settings that are switched on generate a requirement — a runner with
    ``AUTO_DEPLOY=false`` does not need ``VERCEL_TOKEN``, and reporting it as
    missing would be noise. Each entry is
    ``{"name": <env var>, "present": bool, "needed_by": <setting>}``; ``name``
    is an environment variable NAME and never a value.
    """
    s = config_snapshot or {}
    reqs = [
        {
            "name": "ANTHROPIC_API_KEY or CLAUDE_AUTH_MODE=subscription",
            "present": bool(s.get("anthropic")) or s.get("claude_auth_mode") == "subscription",
            "needed_by": "Claude worker dispatch",
        },
        {
            "name": "GITHUB_TOKEN",
            "present": bool(s.get("github")),
            "needed_by": "GITHUB_REPO / MERGE_VIA_PR" if s.get("merge_via_pr") else "GITHUB_REPO",
        },
    ]
    if s.get("auto_apply_sql"):
        reqs.append({
            "name": "SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY",
            "present": bool(s.get("supabase")),
            "needed_by": "AUTO_APPLY_SQL",
        })
    if s.get("auto_apply_migrations"):
        reqs.append({
            "name": "DIRECT_DATABASE_URL or DATABASE_URL",
            "present": bool(s.get("database")),
            "needed_by": "AUTO_APPLY_MIGRATIONS",
        })
    if s.get("auto_deploy"):
        reqs.append({
            "name": "VERCEL_TOKEN",
            "present": bool(s.get("vercel")),
            "needed_by": "AUTO_DEPLOY",
        })
    if s.get("slack_notify"):
        reqs.append({
            "name": "SLACK_WEBHOOK_URL",
            "present": bool(s.get("slack")),
            "needed_by": "SLACK_NOTIFY",
        })
    if s.get("slack_interactive_approvals"):
        reqs.append({
            "name": "SLACK_BOT_TOKEN + SLACK_APP_TOKEN + SLACK_CHANNEL_ID",
            "present": bool(s.get("slack_interactive_approvals_configured")),
            "needed_by": "SLACK_INTERACTIVE_APPROVALS",
        })
    return reqs


def check_credentials(config_snapshot: dict) -> dict:
    """Is every credential this configuration names actually resolvable?

    Names only, never values — a missing credential is reported so the founder
    can supply it, and a present one is never echoed.
    """
    reqs = required_credentials(config_snapshot)
    missing = [r["name"] for r in reqs if not r["present"]]
    if missing:
        detail = "; ".join(
            f"{r['name']} (needed by {r['needed_by']})" for r in reqs if not r["present"]
        )
        return make_check(
            "credentials", FAIL,
            f"{len(missing)} credential(s) named by config but unresolvable: {detail}",
            data={"missing": missing},
        )
    return make_check("credentials", PASS, f"all {len(reqs)} required credential(s) resolvable")


def check_pr_gate_alignment(
    repo: str,
    branch: str,
    pr_checks_non_blocking: list,
    has_github: bool,
    fetch_required_checks_fn: Optional[Callable] = None,
) -> dict:
    """Compare the repo's required-status-check contexts against what the runner
    treats as blocking (M4c supervisory rule d).

    A mismatch occurs when a check context required by branch protection would
    also be classified as non-blocking by the runner's PR_CHECKS_NON_BLOCKING
    filter — meaning the runner silently ignores something the repo enforces.

    Reports only: does not auto-change either side.  A WARN (not FAIL) because
    the runner successfully polled before; this is a configuration notice, not
    evidence that work is blocked.
    """
    if not has_github:
        return make_check(
            "pr_gate_alignment", SKIP, "GITHUB_TOKEN not configured"
        )
    if not repo:
        return make_check(
            "pr_gate_alignment", SKIP, "GITHUB_REPO not set"
        )

    if fetch_required_checks_fn is None:
        from tools.github_tools import get_branch_required_checks
        fetch_required_checks_fn = lambda: get_branch_required_checks(repo, branch)

    try:
        result = fetch_required_checks_fn()
    except Exception as e:
        return make_check(
            "pr_gate_alignment", WARN,
            f"could not fetch branch-protection required checks: {e}",
        )

    if not result.get("available"):
        return make_check(
            "pr_gate_alignment", WARN,
            f"branch-protection required checks unreachable: {result.get('error') or 'unknown'}",
        )

    from tools.supervisory_early_stop import reconcile_pr_gate_sets
    reconcile = reconcile_pr_gate_sets(
        pr_checks_non_blocking or [],
        result.get("contexts") or [],
    )

    if reconcile["mismatch"]:
        ignored = reconcile.get("runner_ignores_repo_requires") or []
        log_event("pr_gate_mismatch", {
            "repo": repo,
            "branch": branch,
            "runner_non_blocking_when_repo_required": ignored,
            "runner_pr_checks_non_blocking": list(pr_checks_non_blocking or []),
            "repo_required_contexts": list(result.get("contexts") or []),
            "reason": reconcile["reason"],
        })
        return make_check(
            "pr_gate_alignment", WARN,
            reconcile["reason"],
            data={
                "runner_ignores": ignored,
                "repo_contexts": result.get("contexts"),
            },
        )

    return make_check(
        "pr_gate_alignment", PASS,
        f"runner gate set matches repo branch-protection "
        f"({len(result.get('contexts', []))} required check(s))",
    )


def check_repo_health(
    repo_path: str,
    *,
    enabled: bool = True,
    timeout: int = 120,
    run_fn=None,
) -> dict:
    """Run scripts/check.sh once to verify the base repo is healthy (M4c.4).

    This is a HALTING check: a repo where scripts/check.sh fails is broken
    before any task touches it. Dispatching workers into it wastes budget on
    work that will never pass the post-task verification gate. The loop must
    not proceed until the repo is fixed.

    ``enabled=False`` reproduces the pre-M4c.4 behaviour exactly — no
    check.sh run at startup, no halt from this check.
    """
    if not enabled:
        return make_check(
            "repo_health", SKIP,
            "REPO_HEALTH_PREFLIGHT=false — repo health check skipped",
        )

    from tools.repo_health_preflight import run_repo_health_check

    result = run_repo_health_check(repo_path, timeout=timeout, run_fn=run_fn)

    if result["healthy"]:
        return make_check(
            "repo_health", PASS,
            "scripts/check.sh passed on the base repo",
        )

    if result.get("timed_out"):
        short_detail = (
            f"scripts/check.sh timed out after {timeout}s — "
            "startup blocked; fix the script or increase REPO_HEALTH_PREFLIGHT_TIMEOUT_S"
        )
    else:
        short_detail = (
            f"scripts/check.sh exited {result.get('exit_code')} on the base repo — "
            "this is a pre-existing environment problem, not a task failure"
        )

    return make_check(
        "repo_health", FAIL,
        short_detail,
        halting=True,
        data={
            "exit_code": result.get("exit_code"),
            "timed_out": result.get("timed_out"),
            "output_excerpt": result.get("output_excerpt"),
        },
    )


# ---------------------------------------------------------------------------
# Default readers
# ---------------------------------------------------------------------------

def _git_sha(args: list[str], repo_path: str, timeout: int = 30) -> str:
    """Run a git command that prints a SHA, returning "" on any failure.

    Deliberately avoids ``shell_tools.run_command``: it logs raw output on
    failure, and git echoes the (possibly token-bearing) remote URL in network
    error messages. Only the SHA ever leaves this function.
    """
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=repo_path,
            capture_output=True,
            text=True,
            timeout=timeout,
        )
    except Exception:
        return ""
    if result.returncode != 0:
        return ""
    first = (result.stdout or "").strip().split("\n")[0]
    return first.split()[0] if first else ""


def origin_main_sha(repo_path: str, branch: str = "main") -> str:
    """SHA of ``origin/<branch>`` as it exists on the remote right now.

    ``ls-remote`` is preferred over the local ``origin/main`` ref because the
    local ref is only as fresh as the last fetch — and a stale ref would make
    this check confidently compare production against yesterday's main. Falls
    back to the local ref when the remote is unreachable (offline runs).
    """
    return (
        _git_sha(["ls-remote", "origin", f"refs/heads/{branch}"], repo_path)
        or _git_sha(["rev-parse", f"origin/{branch}"], repo_path)
    )


def _default_table_exists_fn(cfg) -> Optional[Callable[[str], Optional[bool]]]:
    """Resolve the cheapest available way to ask "does this table exist?".

    Prefers one ``information_schema`` query over the direct connection; falls
    back to a per-table Supabase REST probe. Returns None when neither is
    configured, which ``check_required_tables`` reports as a skip.
    """
    if cfg.has_database:
        from tools.db_tools import inspect_schema
        result = inspect_schema()
        if result.get("success"):
            keys = (result.get("data") or {}).get("tables") or {}
            present = set()
            for qualified in keys:
                present.add(qualified)
                present.add(qualified.split(".")[-1])
            return lambda table: table in present
        # Reachability failed — every table is "unknown", not "missing".
        return lambda table: None

    if cfg.has_supabase:
        from tools.supabase_tools import verify_table_exists

        def _exists(table: str) -> Optional[bool]:
            result = verify_table_exists(table)
            if result.get("success"):
                return True
            # verify_table_exists cannot distinguish "no such table" from
            # "network down"; both surface as success=False. Treat it as a
            # confirmed absence only when Postgres says so.
            error = str(result.get("error") or "").lower()
            if "does not exist" in error or "not find the table" in error or "pgrst205" in error:
                return False
            return None

        return _exists

    return None


# ---------------------------------------------------------------------------
# Aggregation + reporting
# ---------------------------------------------------------------------------

def summarize_checks(checks: list[dict]) -> dict:
    """Pure: fold per-check results into one consolidated verdict.

    Returns ``status`` (PASS/WARN/FAIL — the worst per-check status),
    ``counts`` per status, ``unsafe`` (any halting check failed) and
    ``unsafe_checks`` (their names).
    """
    checks = list(checks or [])
    counts = {PASS: 0, WARN: 0, FAIL: 0, SKIP: 0}
    for check in checks:
        counts[check["status"]] = counts.get(check["status"], 0) + 1

    worst = max((_STATUS_RANK.get(c["status"], 0) for c in checks), default=0)
    unsafe_checks = [
        c["name"] for c in checks if c.get("halting") and c["status"] == FAIL
    ]
    return {
        "status": _OVERALL_BY_RANK[worst],
        "counts": counts,
        "checks": checks,
        "unsafe": bool(unsafe_checks),
        "unsafe_checks": unsafe_checks,
    }


def format_preflight_report(summary: dict) -> str:
    """Render the consolidated summary as one human-readable block."""
    counts = summary.get("counts") or {}
    header = (
        f"Startup Preflight: {summary.get('status', 'PASS')}  "
        f"({counts.get(PASS, 0)} pass, {counts.get(FAIL, 0)} fail, "
        f"{counts.get(WARN, 0)} warn, {counts.get(SKIP, 0)} skip)"
    )
    lines = [header]
    for check in summary.get("checks") or []:
        icon = _ICON.get(check["status"], "?")
        lines.append(f"  [{icon}] {check['name']:<20} {check['detail']}")
    if summary.get("unsafe"):
        lines.append(
            "  HALTING: " + ", ".join(summary["unsafe_checks"])
            + " — the loop will not claim a task until this is resolved."
        )
    elif summary.get("status") != "PASS":
        lines.append(
            "  Reporting only — the loop continues. Trace any later failure back here."
        )
    return "\n".join(lines) + "\n"


def _named(name: str, fn: Callable[[], dict]) -> Callable[[], dict]:
    """Tag a probe with the check it produces.

    Without this, a probe that raises before returning has no name to report
    against, and the resulting WARN says only "unknown_check" — which defeats
    the point of a report meant to be traced back to hours later.
    """
    fn.check_name = name
    return fn


def run_startup_preflight(cfg, probes: Optional[list] = None) -> dict:
    """Run every check once and return the consolidated report.

    ``probes`` (a list of zero-arg callables returning check dicts) overrides
    the default set, so the orchestration can be tested without any network,
    database, or git.
    """
    if probes is None:
        migrations_dir = f"{cfg.repo_path.rstrip('/')}/{_MIGRATIONS_DIR_NAME}"
        table_exists_fn = _default_table_exists_fn(cfg)
        required_tables = tuple(
            getattr(cfg, "preflight_required_tables", None) or DEFAULT_REQUIRED_TABLES
        )
        probes = [
            _named("git_state", lambda: check_git_state(cfg.repo_path)),
            _named("repo_health", lambda: check_repo_health(
                cfg.repo_path,
                enabled=getattr(cfg, "repo_health_preflight_enabled", True),
                timeout=getattr(cfg, "repo_health_preflight_timeout_s", 120),
            )),
            _named("pending_migrations",
                   lambda: check_pending_migrations(migrations_dir, cfg.has_database)),
            _named("production_sha",
                   lambda: check_production_sha(cfg.repo_path, cfg.vercel_project_id, cfg.has_vercel)),
            _named("vercel_project",
                   lambda: check_vercel_project(cfg.vercel_project_id, cfg.has_vercel)),
            _named("github_repo", lambda: check_github_repo(cfg.github_repo, cfg.has_github)),
            _named("required_tables",
                   lambda: check_required_tables(required_tables, table_exists_fn)),
            _named("credentials", lambda: check_credentials(cfg.report())),
            # M4c supervisory rule (d): compare runner's non-blocking list with
            # the repo's actual required-status-checks so mismatches are visible
            # at startup instead of discovered mid-task.
            _named("pr_gate_alignment", lambda: check_pr_gate_alignment(
                cfg.github_repo,
                "main",
                getattr(cfg, "pr_checks_non_blocking", []),
                cfg.has_github,
            )),
        ]

    checks = []
    for probe in probes:
        try:
            checks.append(probe())
        except Exception as e:
            # A probe that raises must never be the reason the loop can't start:
            # this whole module exists to REDUCE stops. Report and move on.
            checks.append(make_check(
                getattr(probe, "check_name", "unknown_check"), WARN,
                f"check raised {type(e).__name__} — assumption unverified",
            ))

    summary = summarize_checks(checks)
    summary["report"] = format_preflight_report(summary)
    summary["generated_at"] = datetime.utcnow().isoformat()
    return summary


def guard_startup_preflight(cfg, probes: Optional[list] = None) -> dict:
    """Run the preflight and emit the ``preflight_report`` event.

    One event carries every check's status so a failure hours later can be
    traced back to a warning that was already visible at startup. The event is
    in the default Slack notify set — that fan-out IS the "loud" in "report
    loudly"; this function still never halts on its own.
    """
    summary = run_startup_preflight(cfg, probes=probes)
    log_event("preflight_report", {
        "status": summary["status"],
        "counts": summary["counts"],
        "unsafe": summary["unsafe"],
        "unsafe_checks": summary["unsafe_checks"],
        "checks": [
            {"name": c["name"], "status": c["status"], "detail": c["detail"]}
            for c in summary["checks"]
        ],
        "report": summary["report"],
    })
    return summary
