"""Slack interactive approvals daemon — standalone long-running process.

Watches ``outbox/`` for new approval-request files written by the existing
file-based gates (merge approval, SQL approval, resource/credential request,
strategic review — see ``graph.py`` and ``tools/slack_approvals.py`` for the
exact file conventions this daemon replicates on the inbox side). For each
new request it posts a Block Kit message with Approve/Reject buttons to
``SLACK_CHANNEL_ID`` over the Slack Web API, then listens for button clicks
over Socket Mode. A click writes the *same* fulfillment file into ``inbox/``
that a human would otherwise have created by hand — the graph itself is
never touched by this daemon.

Run alongside the runner loop (not instead of it):

    python approvals_daemon.py &
    python main.py run-loop

Requires (see README.md "Slack Interactive Approvals" and the env table):
    SLACK_INTERACTIVE_APPROVALS=true
    SLACK_BOT_TOKEN   (xoxb-...  — chat:write, channels:read scopes)
    SLACK_APP_TOKEN   (xapp-...  — Socket Mode, connections:write scope)
    SLACK_CHANNEL_ID  (the channel to post approval requests into)

Exits nonzero immediately with a clear message when the feature flag is off
or any required token/id is missing — this is a standalone process with no
one else to report a degraded state to, so it fails loudly at startup rather
than silently doing nothing.

All mapping logic (which files are approval requests, what the buttons mean,
what to write to inbox/) lives in the pure ``tools/slack_approvals`` module so
it's unit-testable without Slack; this file is the thin, side-effecting
driver around it.
"""
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from config import get_config
from tools.log_tools import log_event
from tools.slack_approvals import (
    classify_outbox_file,
    build_approval_blocks,
    build_result_blocks,
    parse_button_value,
    resolve_action,
)

_RUNNER_DIR = Path(__file__).parent
_OUTBOX_DIR = _RUNNER_DIR / "outbox"
_INBOX_DIR = _RUNNER_DIR / "inbox"

POLL_INTERVAL_SECONDS = 3


def validate_startup_config(cfg) -> list:
    """Return a list of human-readable problems that must block startup.

    Pure (no I/O beyond reading already-loaded config), so it's unit-testable
    without spinning up the daemon or mocking Slack.
    """
    problems = []
    if not cfg.slack_interactive_approvals:
        problems.append(
            "SLACK_INTERACTIVE_APPROVALS is not enabled (set it to 'true' to run this daemon)."
        )
        return problems  # no point also complaining about tokens if the feature is off
    if not cfg.slack_bot_token:
        problems.append("SLACK_BOT_TOKEN is not set (needs a bot token with chat:write).")
    if not cfg.slack_app_token:
        problems.append("SLACK_APP_TOKEN is not set (needs an app-level token with connections:write).")
    if not cfg.slack_channel_id:
        problems.append("SLACK_CHANNEL_ID is not set (the channel to post approval requests into).")
    return problems


class ApprovalsDaemon:
    """Polls outbox/ for approval requests and drives them via Slack.

    ``_tracked`` maps (request_type, request_id) -> {"channel", "ts"} for the
    Slack message currently awaiting a click, so a click can update the right
    message. ``_seen`` is the set of outbox filenames already handled (posted,
    or recognized as not an approval request) so a poll never re-posts.
    """

    def __init__(self, cfg):
        from slack_sdk import WebClient
        from slack_sdk.socket_mode import SocketModeClient

        self.cfg = cfg
        self.web_client = WebClient(token=cfg.slack_bot_token)
        self.socket_client = SocketModeClient(app_token=cfg.slack_app_token, web_client=self.web_client)
        self.socket_client.socket_mode_request_listeners.append(self._handle_socket_request)
        self._tracked = {}
        self._seen = set()

    def start(self):
        _OUTBOX_DIR.mkdir(exist_ok=True)
        _INBOX_DIR.mkdir(exist_ok=True)
        self.socket_client.connect()
        log_event("slack_approvals_daemon_started", {"channel": self.cfg.slack_channel_id})
        print(f"Slack interactive approvals daemon started — watching outbox/, posting to channel {self.cfg.slack_channel_id}. Ctrl+C to stop.")
        try:
            while True:
                self._poll_outbox()
                time.sleep(POLL_INTERVAL_SECONDS)
        except KeyboardInterrupt:
            print("\nStopping approvals daemon...")
        finally:
            self.socket_client.close()
            log_event("slack_approvals_daemon_stopped", {})

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
                # Already resolved (e.g. approved by hand before the daemon started).
                self._seen.add(path.name)
                continue
            self._post_request(path, classification)
            self._seen.add(path.name)

    def _post_request(self, outbox_path: Path, classification: dict):
        try:
            body = outbox_path.read_text(errors="replace")
        except OSError as e:
            log_event("slack_approvals_read_failed", {"file": outbox_path.name, "error": str(e)})
            return

        blocks = build_approval_blocks(
            classification["request_type"], classification["request_id"], outbox_path.name, body,
        )
        try:
            resp = self.web_client.chat_postMessage(
                channel=self.cfg.slack_channel_id,
                text=f"Approval needed: {classification['request_type']} ({classification['request_id']})",
                blocks=blocks,
            )
        except Exception as e:
            log_event("slack_approvals_post_failed", {
                "file": outbox_path.name,
                "request_type": classification["request_type"],
                "request_id": classification["request_id"],
                "error": str(e),
            })
            return

        self._tracked[(classification["request_type"], classification["request_id"])] = {
            "channel": resp.get("channel"),
            "ts": resp.get("ts"),
        }
        log_event("slack_approvals_posted", {
            "request_type": classification["request_type"],
            "request_id": classification["request_id"],
            "file": outbox_path.name,
        })

    def _handle_socket_request(self, client, req):
        from slack_sdk.socket_mode.response import SocketModeResponse

        # Ack immediately per Slack's Socket Mode contract, regardless of what
        # follows below — an unacked request gets redelivered as a retry.
        client.send_socket_mode_response(SocketModeResponse(envelope_id=req.envelope_id))

        if req.type != "interactive":
            return
        payload = req.payload or {}
        actions = payload.get("actions") or []
        if not actions:
            return

        action = actions[0]
        action_id = action.get("action_id")
        if action_id == "runner_approve":
            action_kind = "approve"
        elif action_id == "runner_reject":
            action_kind = "reject"
        else:
            log_event("slack_approvals_unknown_action", {"action_id": action_id})
            return

        user = payload.get("user") or {}
        actor = user.get("name") or user.get("username") or user.get("id") or "unknown"

        try:
            parsed = parse_button_value(action.get("value"))
        except ValueError as e:
            log_event("slack_approvals_malformed_payload", {"error": str(e), "actor": actor})
            return

        decision = resolve_action(parsed["request_type"], parsed["request_id"], action_kind)
        if decision["should_write"]:
            inbox_path = _INBOX_DIR / decision["inbox_filename"]
            if not inbox_path.exists():
                inbox_path.write_text(decision["content"])

        log_event("slack_approvals_resolved", {
            "request_type": parsed["request_type"],
            "request_id": parsed["request_id"],
            "outcome": decision["outcome"],
            "actor": actor,
        })

        key = (parsed["request_type"], parsed["request_id"])
        tracked = self._tracked.pop(key, None)
        channel = (payload.get("channel") or {}).get("id") or (tracked or {}).get("channel")
        ts = (payload.get("message") or {}).get("ts") or (tracked or {}).get("ts")
        if channel and ts:
            try:
                self.web_client.chat_update(
                    channel=channel,
                    ts=ts,
                    text=f"{parsed['request_type']} {parsed['request_id']}: {decision['outcome']}",
                    blocks=build_result_blocks(parsed["request_type"], parsed["request_id"], decision["outcome"], actor),
                )
            except Exception as e:
                log_event("slack_approvals_update_failed", {"error": str(e)})


def main():
    cfg = get_config()
    problems = validate_startup_config(cfg)
    if problems:
        print("Cannot start Slack interactive approvals daemon:", file=sys.stderr)
        for p in problems:
            print(f"  - {p}", file=sys.stderr)
        sys.exit(1)

    daemon = ApprovalsDaemon(cfg)
    daemon.start()


if __name__ == "__main__":
    main()
