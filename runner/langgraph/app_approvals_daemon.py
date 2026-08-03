"""In-app approvals daemon — standalone long-running process.

Gives the bucks.ai app the same approval power as ``approvals_daemon.py``
(the Slack daemon), over the *same* ``outbox/``/``inbox/`` conventions —
mirrors new approval-request files into the Supabase ``approvals`` table
(``supabase/m4a-approvals-queue.sql``) for the app's Approvals panel to list,
then watches that table for founder decisions and writes the *same*
fulfillment file into ``inbox/`` a human (or the Slack daemon) would
otherwise have created. The graph itself is never touched by this daemon.

Run alongside the runner loop (not instead of it), optionally alongside the
Slack daemon too — the two are idempotent with each other via the inbox
file's existence check:

    python app_approvals_daemon.py &
    python main.py run-loop

Requires (see README.md "In-App Approval Queue" and the env table):
    APP_APPROVALS_ENABLED=true
    SUPABASE_URL
    SUPABASE_SERVICE_ROLE_KEY
    RUNNER_OWNER_USER_ID   (auth.users.id stamped on every approvals row)

Exits nonzero immediately with a clear message when the feature flag is off
or any required var is missing — same fail-loudly-at-startup posture as
approvals_daemon.py.

All mapping logic (which outbox files are approval requests, what an
approvals-table row becomes, what a decision means for the inbox side) lives
in the pure ``tools/app_approvals`` and ``tools/slack_approvals`` modules so
it's unit-testable without Supabase; this file is the thin, side-effecting
driver around it.
"""
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from tools.log_tools import log_event
from tools.slack_approvals import classify_outbox_file
from tools.app_approvals import classification_to_row, decision_to_inbox_write, needs_inbox_sync

_RUNNER_DIR = Path(__file__).parent
_OUTBOX_DIR = _RUNNER_DIR / "outbox"
_INBOX_DIR = _RUNNER_DIR / "inbox"

POLL_INTERVAL_SECONDS = 3


def validate_startup_config(cfg) -> list:
    """Return a list of human-readable problems that must block startup.

    Pure (no I/O beyond reading already-loaded config), so it's unit-testable
    without spinning up the daemon or a Supabase connection.
    """
    problems = []
    if not cfg.app_approvals_enabled:
        problems.append(
            "APP_APPROVALS_ENABLED is not enabled (set it to 'true' to run this daemon)."
        )
        return problems  # no point also complaining about the rest if the feature is off
    if not cfg.has_supabase:
        problems.append("SUPABASE_URL / SUPABASE_SERVICE_ROLE_KEY are not set.")
    if not cfg.runner_owner_user_id:
        problems.append("RUNNER_OWNER_USER_ID is not set (needed to stamp approvals rows for RLS).")
    return problems


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class AppApprovalsDaemon:
    """Mirrors outbox/ approval requests into Supabase and inbox-syncs decisions.

    ``_seen`` is the set of outbox filenames already handled (upserted, or
    recognized as not an approval request) so a poll never re-upserts.
    """

    def __init__(self, cfg):
        from supabase import create_client

        self.cfg = cfg
        self.client = create_client(cfg.supabase_url, cfg.supabase_service_role_key)
        self._seen = set()

    def start(self):
        _OUTBOX_DIR.mkdir(exist_ok=True)
        _INBOX_DIR.mkdir(exist_ok=True)
        log_event("app_approvals_daemon_started", {})
        print("In-app approvals daemon started — watching outbox/ and the approvals table. Ctrl+C to stop.")
        try:
            while True:
                self._poll_outbox()
                self._poll_decisions()
                time.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nStopping app approvals daemon...")
        finally:
            log_event("app_approvals_daemon_stopped", {})

    def _poll_outbox(self):
        for path in sorted(_OUTBOX_DIR.glob("*")):
            if path.name in self._seen or path.name == ".gitkeep":
                continue
            classification = classify_outbox_file(path.name)
            if not classification:
                self._seen.add(path.name)
                continue
            inbox_path = _INBOX_DIR / classification["inbox_filename"]
            if inbox_path.exists():
                # Already resolved (e.g. approved by hand, or via Slack, before this daemon saw it).
                self._seen.add(path.name)
                continue
            self._upsert_request(path, classification)
            self._seen.add(path.name)

    def _upsert_request(self, outbox_path: Path, classification: dict):
        try:
            body = outbox_path.read_text(errors="replace")
        except OSError as e:
            log_event("app_approvals_read_failed", {"file": outbox_path.name, "error": str(e)})
            return

        row = classification_to_row(classification, self.cfg.runner_owner_user_id, outbox_path.name, body)
        try:
            self.client.table("approvals").upsert(
                row, on_conflict="request_type,request_id", ignore_duplicates=True
            ).execute()
        except Exception as e:
            log_event("app_approvals_upsert_failed", {
                "file": outbox_path.name,
                "request_type": classification["request_type"],
                "request_id": classification["request_id"],
                "error": str(e),
            })
            return

        log_event("app_approvals_upserted", {
            "request_type": classification["request_type"],
            "request_id": classification["request_id"],
            "file": outbox_path.name,
        })

    def _poll_decisions(self):
        try:
            resp = (
                self.client.table("approvals")
                .select("*")
                .in_("status", ["approved", "rejected"])
                .is_("inbox_synced_at", "null")
                .execute()
            )
        except Exception as e:
            log_event("app_approvals_poll_failed", {"error": str(e)})
            return

        for row in resp.data or []:
            self._sync_decision(row)

    def _sync_decision(self, row: dict):
        if not needs_inbox_sync(row):
            return

        decision = decision_to_inbox_write(row)
        if decision["should_write"]:
            inbox_path = _INBOX_DIR / decision["inbox_filename"]
            if not inbox_path.exists():
                inbox_path.write_text(decision["content"])

        try:
            self.client.table("approvals").update({"inbox_synced_at": _now_iso()}).eq("id", row["id"]).execute()
        except Exception as e:
            log_event("app_approvals_sync_mark_failed", {"id": row.get("id"), "error": str(e)})
            return

        log_event("app_approvals_resolved", {
            "request_type": row.get("request_type"),
            "request_id": row.get("request_id"),
            "outcome": decision["outcome"],
            "actor": row.get("decided_by") or "unknown",
        })


def main():
    cfg = get_config()
    problems = validate_startup_config(cfg)
    if problems:
        print("Cannot start in-app approvals daemon:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)

    daemon = AppApprovalsDaemon(cfg)
    daemon.start()


if __name__ == "__main__":
    main()
