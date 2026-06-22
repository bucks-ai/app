"""Risk-Based Merge Approval Policy.

Classifies the risk level of a proposed merge and applies a configurable
approval policy before any commit/push/merge is attempted.

Risk classification
-------------------
The risk level (low / medium / high) is derived from:
  - An explicit ``risk_level`` or ``high_risk`` field on the task dict.
  - Keywords in the task title, type, or description.
  - Changed file patterns (migrations, auth, .env, SQL, admin, config).
  - The number of files changed.
  - Destructive SQL keywords found in the diff (DROP, TRUNCATE, DELETE FROM).

Merge approval policy (MERGE_APPROVAL_POLICY)
---------------------------------------------
  auto                             — never pause; risk is assessed and logged only.
  require_approval_on_high         — pause for human approval when risk is high (default).
  require_approval_on_medium_and_high — pause for medium and high risk.
  always_require                   — always require human approval before merging.

When a pause is required the gate writes a human-readable request to
``outbox/<task_id>_merge_approval_request.txt`` and waits for a fulfillment
file at ``inbox/<task_id>_merge_approved.txt``.  The loop sets
``merge_approval_status = "pending"`` and stops cleanly at
``decide_continue_or_stop``.  The contents of the fulfillment file are never
read — its existence is the unblock signal.

Config:
  RISK_BASED_MERGE_APPROVAL_ENABLED=true  (default)
  MERGE_APPROVAL_POLICY=require_approval_on_high  (default)
"""
import re
from tools.log_tools import log_event

_HIGH_RISK_KEYWORDS = frozenset({
    "auth", "authentication", "authz", "authorization",
    "payment", "billing", "stripe", "checkout",
    "migration", "migrate",
    "sql", "database", "schema", "supabase",
    "security", "credential", "secret", "token",
    "infrastructure", "production",
    "permission", "rbac", "role", "admin",
    # "delete", "drop", "truncate", "purge" are intentionally omitted — they are
    # common in routine task descriptions (delete endpoint, dropdown, purge cache)
    # and destructive SQL variants are already caught by _DESTRUCTIVE_SQL_RE below.
    "encryption", "crypto", "hash", "password",
})

_HIGH_RISK_FILE_PATTERNS = (
    re.compile(r"\.sql$", re.IGNORECASE),
    re.compile(r"migration", re.IGNORECASE),
    re.compile(r"\.env", re.IGNORECASE),
    re.compile(r"(?<![a-z])auth(?![a-z])", re.IGNORECASE),
    re.compile(r"admin", re.IGNORECASE),
    re.compile(r"security", re.IGNORECASE),
    re.compile(r"password", re.IGNORECASE),
    re.compile(r"secret", re.IGNORECASE),
    re.compile(r"credential", re.IGNORECASE),
)

_DESTRUCTIVE_SQL_RE = re.compile(
    r"\b(DROP\s+TABLE|TRUNCATE|DELETE\s+FROM|DROP\s+DATABASE|DROP\s+SCHEMA)\b",
    re.IGNORECASE,
)

_VALID_POLICIES = frozenset({
    "auto",
    "require_approval_on_high",
    "require_approval_on_medium_and_high",
    "always_require",
})


def classify_merge_risk(task: dict, diff_text: str = "", summary: dict = None) -> dict:
    """Return a risk classification dict for the proposed merge.

    Returns:
        risk_level  (str)   'low', 'medium', or 'high'.
        score       (int)   Cumulative risk score.
        reasons     (list)  Human-readable explanations for the score.
        factors     (dict)  Breakdown of contributing factors.
    """
    if summary is None:
        summary = {}

    score = 0
    reasons: list = []
    factors: dict = {}

    # 1. Explicit risk flags on the task.
    explicit = str(task.get("risk_level", "")).lower()
    if explicit == "high" or task.get("high_risk") is True:
        score += 3
        label = "explicit high_risk=True" if task.get("high_risk") is True else "explicit risk_level=high"
        reasons.append(label)
        factors["explicit_high"] = True
    elif explicit == "medium":
        score += 2
        reasons.append("explicit risk_level=medium")
        factors["explicit_medium"] = True

    # 2. Keyword scan across task text fields.
    text = " ".join([
        str(task.get("title", "")),
        str(task.get("type", "")),
        str(task.get("description", "")),
    ]).lower()
    keyword_hits = sorted(kw for kw in _HIGH_RISK_KEYWORDS if kw in text)
    if keyword_hits:
        kw_score = min(len(keyword_hits), 3)
        score += kw_score
        reasons.append(f"high-risk keywords in task: {', '.join(keyword_hits[:5])}")
        factors["keyword_hits"] = keyword_hits

    # 3. Changed file analysis.
    files_created = summary.get("files_created") or []
    files_modified = summary.get("files_modified") or []
    all_files = [
        str(f).strip() for f in files_created + files_modified
        if str(f).strip() and str(f).strip().lower() not in {"none", "n/a", ""}
    ]

    if len(all_files) > 10:
        score += 1
        reasons.append(f"large change set: {len(all_files)} files")
        factors["large_change_set"] = len(all_files)

    pattern_hits: set = set()
    for fname in all_files:
        for pat in _HIGH_RISK_FILE_PATTERNS:
            if pat.search(fname):
                pattern_hits.add(pat.pattern)
                break
    if pattern_hits:
        pat_score = min(len(pattern_hits), 2)
        score += pat_score
        reasons.append(f"{len(pattern_hits)} sensitive file pattern(s) matched")
        factors["sensitive_file_patterns"] = sorted(pattern_hits)

    # 4. Destructive SQL keywords in the diff.
    if diff_text and _DESTRUCTIVE_SQL_RE.search(diff_text):
        score += 2
        reasons.append("destructive SQL keywords found in diff (DROP/TRUNCATE/DELETE FROM)")
        factors["destructive_sql"] = True

    # Map cumulative score to risk level.
    if score == 0:
        risk_level = "low"
    elif score <= 2:
        risk_level = "medium"
    else:
        risk_level = "high"

    return {
        "risk_level": risk_level,
        "score": score,
        "reasons": reasons,
        "factors": factors,
    }


def requires_approval(risk_level: str, policy: str) -> bool:
    """Return True when the policy demands human approval for this risk level."""
    if policy not in _VALID_POLICIES:
        policy = "require_approval_on_high"

    if policy == "auto":
        return False
    if policy == "always_require":
        return True
    if policy == "require_approval_on_high":
        return risk_level == "high"
    if policy == "require_approval_on_medium_and_high":
        return risk_level in ("medium", "high")
    return False


def format_approval_request(
    task_id: str,
    task_title: str,
    classification: dict,
    inbox_filename: str,
) -> str:
    """Build a human-readable approval request written to outbox/."""
    risk_level = classification["risk_level"]
    score = classification["score"]
    reasons = classification["reasons"]
    lines = [
        f"Merge Approval Request — {task_id}",
        "=" * 60,
        f"Task:       {task_title}",
        f"Risk level: {risk_level.upper()}  (score: {score})",
        "",
        "Risk factors:",
    ]
    for r in reasons:
        lines.append(f"  • {r}")
    if not reasons:
        lines.append("  (none detected — policy requires approval for all merges)")
    lines += [
        "",
        "To approve this merge, create the file:",
        f"  inbox/{inbox_filename}",
        "",
        "The file contents are not read — its existence is the approval signal.",
        "To reject, do not create the file; instead re-queue the task with a",
        "reduced scope or adjust the MERGE_APPROVAL_POLICY environment variable.",
    ]
    return "\n".join(lines)


def guard_merge_approval(
    task: dict,
    diff_text: str = "",
    summary: dict = None,
    *,
    policy: str = "require_approval_on_high",
    approved: bool = False,
    context: str = "",
) -> dict:
    """Evaluate the merge approval gate.

    Returns:
        passed          (bool)  True when the merge may proceed.
        skipped         (bool)  True when no approval is required by policy.
        requires_human  (bool)  True when human approval is needed.
        approved        (bool)  True when approval has been provided.
        risk_level      (str)   'low', 'medium', or 'high'.
        classification  (dict)  Full classification breakdown.
        issues          (list)  Non-empty when the gate blocks.
    """
    if summary is None:
        summary = {}
    task_id = task.get("id")

    classification = classify_merge_risk(task, diff_text=diff_text, summary=summary)
    risk_level = classification["risk_level"]
    needs_approval = requires_approval(risk_level, policy)

    if not needs_approval:
        log_event("merge_approval_skipped", {
            "task_id": task_id,
            "context": context,
            "risk_level": risk_level,
            "score": classification["score"],
            "policy": policy,
        }, task_id=task_id)
        return {
            "passed": True,
            "skipped": True,
            "requires_human": False,
            "approved": True,
            "risk_level": risk_level,
            "classification": classification,
            "issues": [],
        }

    if approved:
        log_event("merge_approval_granted", {
            "task_id": task_id,
            "context": context,
            "risk_level": risk_level,
            "score": classification["score"],
            "policy": policy,
        }, task_id=task_id)
        return {
            "passed": True,
            "skipped": False,
            "requires_human": True,
            "approved": True,
            "risk_level": risk_level,
            "classification": classification,
            "issues": [],
        }

    issue = f"merge requires human approval (risk={risk_level}, policy={policy})"
    log_event("merge_approval_pending", {
        "task_id": task_id,
        "context": context,
        "risk_level": risk_level,
        "score": classification["score"],
        "policy": policy,
        "reasons": classification["reasons"],
    }, task_id=task_id)
    return {
        "passed": False,
        "skipped": False,
        "requires_human": True,
        "approved": False,
        "risk_level": risk_level,
        "classification": classification,
        "issues": [issue],
    }
