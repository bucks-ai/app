"""Codex worker adapter — CLI, outbox, or manual fallback."""
import json
import shutil
from config import get_config
from state import WorkerResult
from tools.log_tools import log_event
from tools.shell_tools import run_command
from workers.base_worker import BaseWorker


def parse_codex_cli_jsonl(raw: str) -> dict | None:
    """Parse Codex CLI `exec --json` JSONL output (one JSON object per line).

    Returns ``{"result_text": str|None, "tokens_used": int|None}`` or
    ``None`` if no parseable JSONL events were found at all. Codex CLI does
    not report a dollar cost anywhere in this stream, so callers must leave
    ``api_cost`` at its default (None) and let cost_budget_guard fall back
    to the configured per-task estimate — never guess a cost here.

    Known event shapes (per Codex CLI docs):
      {"type": "item.completed", "item": {"type": "agent_message", "text": "..."}}
      {"type": "turn.completed", "usage": {"input_tokens": N, "output_tokens": N, ...}}
    `usage.input_tokens`/`output_tokens` are cumulative-per-turn totals (not
    additive across turns the way Claude's cache fields are), so the last
    usage event seen wins rather than summing across turns.
    """
    if not raw:
        return None
    agent_messages = []
    tokens_used = None
    saw_any_event = False
    for line in raw.splitlines():
        line = line.strip()
        if not line or line[0] != "{":
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue
        if not isinstance(event, dict):
            continue
        saw_any_event = True

        if event.get("type") == "item.completed":
            item = event.get("item") or {}
            if item.get("type") == "agent_message" and item.get("text"):
                agent_messages.append(item["text"])

        usage = event.get("usage")
        if isinstance(usage, dict) and ("input_tokens" in usage or "output_tokens" in usage):
            tokens_used = int(usage.get("input_tokens") or 0) + int(usage.get("output_tokens") or 0)

    if not saw_any_event:
        return None

    return {
        "result_text": agent_messages[-1] if agent_messages else None,
        "tokens_used": tokens_used,
    }


class CodexWorker(BaseWorker):
    name = "codex"

    def run_worker_prompt(self, prompt: str, task: dict) -> WorkerResult:
        task_id = task.get("id", "task")
        log_event("worker_started", {"worker": "codex", "task_id": task_id})

        if shutil.which("codex"):
            result = self._run_cli(prompt, task_id)
        else:
            result = self._run_outbox(prompt, task_id)

        log_event("worker_finished", {"worker": "codex", "task_id": task_id, "success": result.success})
        return result

    def _run_cli(self, prompt: str, task_id: str) -> WorkerResult:
        path = self._write_outbox(task_id, prompt)
        # Use `codex exec` subcommand for non-interactive execution.
        # Pass prompt via stdin ("-") to avoid ARG_MAX limits and escaping issues.
        # --dangerously-bypass-approvals-and-sandbox replaces the old --approval-mode full-auto.
        # --json streams JSONL events (agent messages + per-turn token usage) to stdout.
        cmd = ["codex", "exec", "--json", "--dangerously-bypass-approvals-and-sandbox", "--cd", get_config().repo_path, "-"]
        r = run_command(cmd, stdin_data=prompt, timeout=600)

        output_text = r.output
        tokens_used = None
        if r.success:
            parsed = parse_codex_cli_jsonl(r.output)
            if parsed is not None:
                if parsed["result_text"] is not None:
                    output_text = parsed["result_text"]
                tokens_used = parsed["tokens_used"]
            else:
                log_event("codex_cli_json_parse_failed", {"task_id": task_id})

        return WorkerResult(
            worker="codex",
            mode="cli",
            success=r.success,
            output=output_text,
            error=r.error,
            prompt_path=path,
            tokens_used=tokens_used,
            # api_cost intentionally left None: Codex CLI reports no dollar
            # cost; cost_budget_guard falls back to ESTIMATED_COST_PER_TASK_DOLLARS.
        )

    def _run_outbox(self, prompt: str, task_id: str) -> WorkerResult:
        path = self._write_outbox(task_id, prompt)
        inbox = self._inbox_path(task_id)
        print(f"\n[Codex] CLI not found. Prompt written to:\n  {path}")
        print(f"Run Codex manually, then paste the response to:\n  {inbox}")
        response = self._read_inbox(task_id, timeout_seconds=10)
        return WorkerResult(
            worker="codex",
            mode="outbox",
            success=bool(response),
            output=response,
            prompt_written=True,
            prompt_path=path,
            response_path=inbox if response else None,
        )
