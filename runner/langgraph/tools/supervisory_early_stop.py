"""Supervisory early-stop rules (M4c babysitter layer).

Five pure-function decision rules that judge the RUN, not individual tasks.
None calls a model. None overrides an existing gate that said stop.
They only ever STOP EARLIER or SKIP — never cause work to proceed that a gate
blocked.

All five are disabled as a unit when SUPERVISORY_EARLY_STOP_ENABLED=false,
which restores exactly today's behaviour.

(a) classify_ci_failure_environmental — distinguish environment-broken CI from
    task-broken CI before routing to the repair budget.
(b) detect_worker_auth_failure — 401/403 and revoked-token signals are never
    retryable; stop the loop immediately with worker_auth_failed.
(c) check_count_is_stable — a check set is only trustworthy once its total has
    been stable across two consecutive polls, or matches the repo's
    branch-protection required-checks list.
(d) reconcile_pr_gate_sets — compare the repo's required-status-check contexts
    against what the runner will treat as blocking; report disagreement at
    startup.
(e) evaluate_spend_without_progress — stop with no_progress_for_spend when
    cumulative tokens or elapsed time exceed a configurable ceiling without a
    single successful merge.
"""
from __future__ import annotations

import re
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# (a) CI failure — environmental vs task
# ---------------------------------------------------------------------------

# Pattern that matches the Anthropic API status field in JSON output.
_API_STATUS_RE = re.compile(r'"api_error_status"\s*:\s*(\d+)')


def _fetch_sha_check_conclusions_default(
    repo: str,
    sha: str,
    token: Optional[str],
) -> dict:
    """Fetch {check_name: conclusion} for *sha* from the GitHub REST API.

    Returns an empty dict on any error — degrade gracefully; the caller treats
    an empty result as "unknown, do not classify environmental".
    """
    if not repo or not sha or not token:
        return {}
    try:
        import requests
        r = requests.get(
            f"https://api.github.com/repos/{repo}/commits/{sha}/check-runs",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            timeout=10,
        )
        if r.status_code != 200:
            return {}
        return {
            run.get("name", ""): run.get("conclusion")
            for run in r.json().get("check_runs", [])
            if run.get("conclusion")
        }
    except Exception:
        return {}


def _list_open_pr_heads_default(
    repo: str,
    token: Optional[str],
    current_pr_number: Optional[int] = None,
) -> list:
    """Return a list of ``{"sha": str, "branch": str, "number": int}`` dicts for
    open PRs, excluding *current_pr_number*.  Capped at 10 to limit API calls.
    """
    if not repo or not token:
        return []
    try:
        import requests
        r = requests.get(
            f"https://api.github.com/repos/{repo}/pulls",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
            params={"state": "open", "per_page": "20"},
            timeout=10,
        )
        if r.status_code != 200:
            return []
        result = []
        for pr in r.json()[:10]:
            number = pr.get("number")
            if current_pr_number and number == current_pr_number:
                continue
            sha = (pr.get("head") or {}).get("sha", "")
            branch = (pr.get("head") or {}).get("ref", "")
            if sha:
                result.append({"sha": sha, "branch": branch, "number": number})
        return result
    except Exception:
        return []


def classify_ci_failure_environmental(
    failed_checks: list,
    repo: str,
    base_sha: str,
    token: Optional[str],
    *,
    current_pr_number: Optional[int] = None,
    enabled: bool = True,
    fetch_commit_check_conclusions_fn: Optional[Callable] = None,
    list_open_pr_heads_fn: Optional[Callable] = None,
) -> dict:
    """Decide whether the *failed_checks* are an environmental CI problem.

    An environmental failure is one where the SAME named check is also failing
    on the base commit or on at least one other open PR.  Environmental failures
    must NOT be routed to repair — the task did not cause them, so spending the
    repair budget on them is wasted.

    Args:
        failed_checks: list of check run names that failed on the current PR.
        repo:          ``owner/repo`` string.
        base_sha:      SHA of the main/base branch head.
        token:         GitHub personal-access token.
        current_pr_number: PR number to exclude from the "other open PRs" scan.
        enabled:       When False, always returns ``{"environmental": False}``.
        fetch_commit_check_conclusions_fn: injectable for testing.
            Signature: (repo, sha, token) -> dict[name, conclusion]
        list_open_pr_heads_fn: injectable for testing.
            Signature: (repo, token, current_pr_number) -> list[{sha, branch, number}]

    Returns:
        environmental   — True when the failure should be skipped, not repaired.
        corroborating   — list of {"branch": str, "sha": str} where the check also fails.
        reason          — human-readable explanation.
    """
    _no = {"environmental": False, "corroborating": [], "reason": ""}
    if not enabled:
        return _no
    if not failed_checks:
        return _no

    fetch_fn = fetch_commit_check_conclusions_fn or _fetch_sha_check_conclusions_default
    list_fn = list_open_pr_heads_fn or _list_open_pr_heads_default

    failed_set = set(failed_checks)
    corroborating: list = []

    # Check the base commit first — cheapest signal.
    if base_sha:
        base_conclusions = fetch_fn(repo, base_sha, token)
        base_failures = {
            name for name, conclusion in base_conclusions.items()
            if conclusion not in ("success", "skipped")
        }
        overlap = failed_set & base_failures
        if overlap:
            corroborating.append({"branch": "base", "sha": base_sha[:7]})

    # Check other open PRs.
    pr_heads = list_fn(repo, token, current_pr_number)
    for pr_info in pr_heads:
        pr_sha = pr_info.get("sha", "")
        pr_branch = pr_info.get("branch", "")
        if not pr_sha:
            continue
        pr_conclusions = fetch_fn(repo, pr_sha, token)
        pr_failures = {
            name for name, conclusion in pr_conclusions.items()
            if conclusion not in ("success", "skipped")
        }
        overlap = failed_set & pr_failures
        if overlap:
            corroborating.append({
                "branch": pr_branch,
                "sha": pr_sha[:7],
                "pr_number": pr_info.get("number"),
            })

    if corroborating:
        check_names = ", ".join(sorted(failed_set)[:3])
        return {
            "environmental": True,
            "corroborating": corroborating,
            "reason": (
                f"CI failure on check(s) [{check_names}] is environmental: "
                f"same check also fails on {len(corroborating)} other ref(s)"
            ),
        }
    return _no


# ---------------------------------------------------------------------------
# (b) Worker auth failures — never retryable
# ---------------------------------------------------------------------------

# HTTP 401/403 indicators — may appear as status codes in JSON output or as
# text in error/output from the CLI.
_AUTH_STATUS_CODES = frozenset({401, 403})

# Text patterns that indicate an authentication / authorisation failure that a
# retry cannot fix.  Case-insensitive substring matching.
_AUTH_PATTERNS = (
    "oauth access token has been revoked",
    "oauth token revoked",
    "access token revoked",
    "authentication token has been revoked",
    "invalid authentication token",
    "invalid oauth token",
    "invalid api key",
    "revoked",        # broad but positioned after more specific matches
    "token expired",
    "token has expired",
    "credentials have expired",
    "failed to authenticate",
    "authentication failed",
    "unauthorized",   # API key or OAuth rejected outright
)

# JSON field patterns for the HTTP status in Claude CLI output.
_API_STATUS_RE_AUTH = re.compile(r'"api_error_status"\s*:\s*(401|403)')


def detect_worker_auth_failure(error: str, output: str = "") -> dict:
    """Detect a non-retryable authentication or authorisation failure.

    A 401/403 or a revoked/expired/invalid token message indicates that no
    amount of retries will help — a human must re-authenticate.

    Args:
        error:  Worker result ``error`` field (stderr / exception text).
        output: Worker result ``output`` field (stdout / response body).

    Returns:
        auth_failed — True when an auth failure was detected.
        pattern     — The matched pattern or field name.
    """
    combined = " ".join(filter(None, [error, output])).lower()

    # Check the structured JSON status field first (most reliable signal).
    if _API_STATUS_RE_AUTH.search(combined):
        return {"auth_failed": True, "pattern": "api_error_status:401/403"}

    # Check for text patterns.
    for pattern in _AUTH_PATTERNS:
        if pattern in combined:
            return {"auth_failed": True, "pattern": pattern}

    return {"auth_failed": False, "pattern": ""}


# ---------------------------------------------------------------------------
# (c) Check-count stability before trusting conclusions
# ---------------------------------------------------------------------------


def check_count_is_stable(
    curr_total: int,
    prev_total: Optional[int],
    required_checks: Optional[list] = None,
) -> bool:
    """Return True when the check set count is trustworthy.

    A count is trustworthy when:
    - It is the same as the previous poll (two consecutive polls agree), OR
    - It is at least as large as the repo's branch-protection required-checks
      list (meaning all required checks are registered).

    The second condition lets the runner conclude on the very first
    all-complete poll when GitHub's branch-protection data says those are all
    the checks there will be, instead of waiting for a second poll.

    Args:
        curr_total:     Number of check runs seen in the current poll.
        prev_total:     Number of check runs seen in the previous poll, or
                        None if this is the first all-complete poll.
        required_checks: List of required-status-check context names from
                         branch protection, or None if unavailable.

    Returns True when the count should be trusted.
    """
    if curr_total <= 0:
        return False
    # Stability: same count for two consecutive polls.
    if prev_total is not None and curr_total == prev_total:
        return True
    # Branch-protection anchor: we have at least as many checks as required.
    if required_checks is not None and curr_total >= len(required_checks) > 0:
        return True
    return False


# ---------------------------------------------------------------------------
# (d) PR gate reconciliation — runner vs repo
# ---------------------------------------------------------------------------


def reconcile_pr_gate_sets(
    non_blocking_substrings: list,
    required_check_contexts: list,
) -> dict:
    """Compare what the repo REQUIRES against what the runner treats as blocking.

    The runner treats a check as non-blocking when its name contains any
    substring from *non_blocking_substrings*.  A mismatch occurs when:

    - A check context required by the repo would be classified non-blocking by
      the runner (runner MORE lenient than the repo — it will ignore a check
      that branch protection enforces).
    - No checks are required by the repo (branch protection is off or unconfigured).

    Reporting only — the caller must not auto-change either side.

    Args:
        non_blocking_substrings: PR_CHECKS_NON_BLOCKING list (substrings,
                                 case-insensitive).
        required_check_contexts: list of exact context names from the repo's
                                 branch-protection required-status-checks.

    Returns:
        mismatch                    — True when disagreement was found.
        runner_ignores_repo_requires — list of required contexts the runner
                                       would classify as non-blocking.
        reason                      — human-readable summary.
    """
    non_blocking_lower = [s.lower() for s in (non_blocking_substrings or [])]

    ignored_by_runner: list = []
    for context in (required_check_contexts or []):
        name_lower = (context or "").lower()
        if any(marker in name_lower for marker in non_blocking_lower):
            ignored_by_runner.append(context)

    if not required_check_contexts:
        return {
            "mismatch": False,
            "runner_ignores_repo_requires": [],
            "reason": "branch protection has no required status checks — nothing to reconcile",
        }

    if ignored_by_runner:
        return {
            "mismatch": True,
            "runner_ignores_repo_requires": ignored_by_runner,
            "reason": (
                f"runner's PR_CHECKS_NON_BLOCKING causes it to ignore "
                f"{len(ignored_by_runner)} check(s) that the repo requires: "
                + ", ".join(f'"{c}"' for c in ignored_by_runner[:5])
            ),
        }

    return {
        "mismatch": False,
        "runner_ignores_repo_requires": [],
        "reason": "runner gate set matches repo branch-protection requirements",
    }


# ---------------------------------------------------------------------------
# (e) Spend-without-progress ceiling
# ---------------------------------------------------------------------------

NO_PROGRESS_STOP = "no_progress_for_spend"


def evaluate_spend_without_progress(
    session_tokens: int,
    elapsed_minutes: float,
    merges_this_session: int,
    max_tokens: int = 0,
    max_minutes: int = 0,
    *,
    enabled: bool = True,
) -> dict:
    """Stop the run when significant spend occurred but zero merges landed.

    A run that spends at either ceiling without producing a single merged PR is
    not making progress — it is burning budget on work that will be thrown away.

    Args:
        session_tokens:      Cumulative tokens used this session.
        elapsed_minutes:     Elapsed session wall-clock minutes.
        merges_this_session: Number of PRs successfully merged this session.
        max_tokens:          Token ceiling.  0 = unlimited (disabled).
        max_minutes:         Time ceiling in minutes.  0 = unlimited (disabled).
        enabled:             When False, always returns ``{"ceiling_hit": False}``.

    Returns:
        ceiling_hit  — True when the ceiling was reached with no merges.
        stop_reason  — ``NO_PROGRESS_STOP`` when ceiling_hit, else None.
        report       — human-readable summary string.
    """
    _no = {"ceiling_hit": False, "stop_reason": None, "report": ""}
    if not enabled:
        return _no

    # Any merge counts as progress.
    if merges_this_session > 0:
        return _no

    tokens_exceeded = max_tokens > 0 and session_tokens >= max_tokens
    minutes_exceeded = max_minutes > 0 and elapsed_minutes >= max_minutes

    if not (tokens_exceeded or minutes_exceeded):
        return _no

    reasons = []
    if tokens_exceeded:
        reasons.append(f"{session_tokens:,} tokens >= {max_tokens:,} token ceiling")
    if minutes_exceeded:
        reasons.append(f"{elapsed_minutes:.1f} min >= {max_minutes} min ceiling")

    report = (
        f"No progress for spend: {'; '.join(reasons)}. "
        f"Tokens spent: {session_tokens:,}. "
        f"Merges achieved: 0. "
        "A human must inspect what blocked every task and restart the loop."
    )
    return {
        "ceiling_hit": True,
        "stop_reason": NO_PROGRESS_STOP,
        "report": report,
    }
