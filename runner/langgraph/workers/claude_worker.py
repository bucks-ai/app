"""Claude Code worker adapter — CLI, outbox, or manual fallback."""
import json
import os
import shutil
from config import get_config
from state import WorkerResult
from tools.log_tools import log_event
from tools.shell_tools import run_command
from tools.claude_subagent_pack import select_subagent, build_subagent_prompt_prefix
from tools.claude_hooks_safety_pack import write_hooks, validate_hooks
from workers.base_worker import BaseWorker

# Token fields from Anthropic's usage object. cache_creation_input_tokens and
# cache_read_input_tokens are additive (not already counted in input_tokens),
# so a plain sum over all four gives the true total.
_CLAUDE_USAGE_TOKEN_FIELDS = (
    "input_tokens",
    "output_tokens",
    "cache_creation_input_tokens",
    "cache_read_input_tokens",
)


def parse_claude_cli_json(raw: str) -> dict | None:
    """Parse Claude Code CLI `--print --output-format json` output.

    Returns ``{"result_text": str|None, "total_cost_usd": float|None,
    "tokens_used": int|None}`` or ``None`` if `raw` isn't a parseable
    ``{"type": "result", ...}`` envelope. Never raises — callers treat a
    ``None`` return the same as "no JSON output available".
    """
    text = (raw or "").strip()
    if not text:
        return None
    try:
        obj = json.loads(text)
    except json.JSONDecodeError:
        # shell_tools.run_command concatenates stdout+stderr, so any stray
        # stderr text before/after the JSON breaks a naive json.loads.
        # Fall back to the outermost {...} substring.
        start, end = text.find("{"), text.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            obj = json.loads(text[start:end + 1])
        except json.JSONDecodeError:
            return None

    if not isinstance(obj, dict) or obj.get("type") != "result":
        return None

    usage = obj.get("usage")
    tokens_used = None
    if isinstance(usage, dict) and any(f in usage for f in _CLAUDE_USAGE_TOKEN_FIELDS):
        tokens_used = sum(int(usage.get(f) or 0) for f in _CLAUDE_USAGE_TOKEN_FIELDS)

    return {
        "result_text": obj.get("result"),
        "total_cost_usd": obj.get("total_cost_usd"),
        "tokens_used": tokens_used,
    }


class ClaudeWorker(BaseWorker):
    name = "claude"

    def run_worker_prompt(self, prompt: str, task: dict) -> WorkerResult:
        task_id = task.get("id", "task")
        model = task.get("resolved_model") or None
        cfg = get_config()
        auth_mode = cfg.claude_auth_mode

        # Inject subagent context when the pack is enabled.
        if cfg.claude_subagent_pack_enabled:
            subagent = select_subagent(task)
            prefix = build_subagent_prompt_prefix(subagent)
            if prefix:
                prompt = prefix + prompt
            log_event("claude_subagent_selected", {
                "task_id": task_id,
                "subagent": subagent["name"],
                "task_type": task.get("type", ""),
            })

        log_event("worker_started", {
            "worker": "claude",
            "task_id": task_id,
            "model": model,
            "auth_mode": auth_mode,
        })

        repo_path = task.get("repo_path") or cfg.repo_path

        if shutil.which("claude"):
            result = self._run_cli(prompt, task_id, model=model, auth_mode=auth_mode, repo_path=repo_path)
        else:
            result = self._run_outbox(prompt, task_id)

        log_event("worker_finished", {"worker": "claude", "task_id": task_id, "success": result.success})
        return result

    def _run_cli(
        self,
        prompt: str,
        task_id: str,
        model: str | None = None,
        auth_mode: str = "api_key",
        repo_path: str | None = None,
    ) -> WorkerResult:
        cfg = get_config()
        repo_path = repo_path or cfg.repo_path
        if cfg.claude_hooks_safety_pack_enabled:
            if cfg.claude_hooks_safety_pack_auto_install:
                result = write_hooks(repo_path)
                if result["merged"]:
                    log_event("claude_hooks_installed", {"path": result["path"], "task_id": task_id})
            else:
                v = validate_hooks(repo_path)
                if not v["valid"]:
                    log_event("claude_hooks_missing", {
                        "task_id": task_id,
                        "reason": v["reason"],
                        "path": v["path"],
                    })

        path = self._write_outbox(task_id, prompt)
        cmd = ["claude", "--print", "--dangerously-skip-permissions", "--output-format", "json"]
        if model:
            cmd += ["--model", model]
        cmd.append(f"@{path}")

        # In subscription mode strip ANTHROPIC_API_KEY so the CLI falls back to
        # the OAuth/keychain token set up via `claude auth login` or `claude
        # setup-token`, rather than the API key taking precedence.
        env = None
        if auth_mode == "subscription":
            env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

        # Configurable wall-clock cap for one CLI invocation.  600s proved too
        # small for heavy multi-file tasks (M0.9: m1-11/m1-12 zod rollouts
        # timed out at exactly 600s while smaller tasks completed fine).
        r = run_command(cmd, timeout=cfg.claude_cli_timeout_s, env=env)

        output_text = r.output
        api_cost = None
        tokens_used = None
        if r.success:
            parsed = parse_claude_cli_json(r.output)
            if parsed is not None:
                if parsed["result_text"] is not None:
                    output_text = parsed["result_text"]
                tokens_used = parsed["tokens_used"]
                # Subscription runs are covered by the flat monthly fee, not
                # billed per-call — record 0.0 rather than the CLI's internal
                # cost estimate, but keep the real token counts if reported.
                api_cost = 0.0 if auth_mode == "subscription" else parsed["total_cost_usd"]
            else:
                log_event("claude_cli_json_parse_failed", {"task_id": task_id})

        return WorkerResult(
            worker="claude",
            mode="cli",
            success=r.success,
            output=output_text,
            error=r.error,
            prompt_path=path,
            api_cost=api_cost,
            tokens_used=tokens_used,
        )

    def _run_outbox(self, prompt: str, task_id: str) -> WorkerResult:
        path = self._write_outbox(task_id, prompt)
        inbox = self._inbox_path(task_id)
        print(f"\n[Claude] CLI not found. Prompt written to:\n  {path}")
        print(f"Run Claude Code manually, then paste the response to:\n  {inbox}")
        response = self._read_inbox(task_id, timeout_seconds=10)
        return WorkerResult(
            worker="claude",
            mode="outbox",
            success=bool(response),
            output=response,
            prompt_written=True,
            prompt_path=path,
            response_path=inbox if response else None,
        )
