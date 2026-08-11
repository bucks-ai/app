"""Auto-approval policy: the founder approves everything (M4c).

The runner makes routine decisions autonomously by writing the same inbox
fulfillment file a human approve-click would, keeping the file-based gate
contracts intact and the graph nodes untouched.

Auto-approval is NEVER applied to two classes:
  (a) Genuinely destructive or irreversible actions: non-additive SQL
      (DROP TABLE, TRUNCATE, DELETE FROM, ALTER TABLE DROP COLUMN, …),
      spend past the session cap, anything the sql_guard flags as blocked.
  (b) Resource/credential gates where the thing does not exist yet —
      there is no API key to approve because one hasn't been created.
      Those tasks are set aside (SKIP-AND-CONTINUE) and auto-requeued the
      instant the credential appears in the runner's env (see
      ``task_tools.auto_requeue_credential_satisfied_tasks``).

Merge approval: auto-approve if CI passed and the diff does not contain
destructive SQL.  Even a high-risk-score merge (many files, auth keywords,
migration patterns) is approved — the score drives observability, not a
veto.  The guard retains its veto only for genuinely irreversible SQL.

SQL approval: auto-approve if the sql_text contains no destructive
statements.  The sql_guard's blocked-term scan is the primary authority;
this function provides the same check for the approval gate path.

Strategic gate: always auto-approve.  The interval is a tempo knob for
operators who want periodic checkpoints; the founder's standing instruction
is to proceed without waiting.
"""
import re

# Mirrors the destructive-SQL patterns in tools/risk_based_merge_approval.py
# and tools/sql_guard.py.  Kept in sync intentionally — if one changes, the
# other should too.
_DESTRUCTIVE_SQL_RE = re.compile(
    r"\b(DROP\s+TABLE|DROP\s+DATABASE|DROP\s+SCHEMA|TRUNCATE\b|"
    r"DELETE\s+FROM|ALTER\s+TABLE\s+\S+\s+DROP)",
    re.IGNORECASE,
)


def is_destructive_diff(diff_text: str) -> bool:
    """True when *diff_text* contains a destructive SQL statement."""
    return bool(_DESTRUCTIVE_SQL_RE.search(diff_text or ""))


def should_auto_approve_merge(decision: dict, diff_text: str = "") -> bool:
    """Return True when the runner may approve this merge without waiting.

    Blocked when:
    * ``decision["classification"]["factors"]`` has ``destructive_sql: True``
      (``classify_merge_risk`` already detected destructive SQL in the diff).
    * *diff_text* contains a destructive SQL keyword (belt-and-suspenders check).

    Everything else — high-risk keyword score, large change set, auth file
    patterns — is approved autonomously.  The risk classification still runs
    and is logged; it just no longer gates the merge.
    """
    factors = (decision.get("classification") or {}).get("factors", {})
    if factors.get("destructive_sql"):
        return False
    if is_destructive_diff(diff_text):
        return False
    return True


def should_auto_approve_sql(sql_text: str) -> bool:
    """Return True when *sql_text* contains no destructive statements.

    Used to auto-approve SQL that the environment gate would otherwise hold
    for human review.  Only additive SQL (CREATE TABLE, ALTER TABLE ADD
    COLUMN, INSERT, etc.) passes; any DROP / TRUNCATE / DELETE FROM / ALTER
    TABLE … DROP blocks auto-approval and falls back to human review.
    """
    return not bool(_DESTRUCTIVE_SQL_RE.search(sql_text or ""))


def should_auto_approve_strategic() -> bool:
    """The founder approves everything — the strategic gate included.

    Returns True unconditionally.  Callers should still check
    ``cfg.auto_approve_enabled`` before calling this so the flag is the
    single point of control.
    """
    return True
