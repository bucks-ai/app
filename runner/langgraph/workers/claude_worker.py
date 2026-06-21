"""Claude Code worker adapter — CLI, outbox, or manual fallback."""
import os
import shutil
from config import get_config
from state import WorkerResult
from tools.log_tools import log_event
from tools.shell_tools import run_command
from tools.claude_subagent_pack import select_subagent, build_subagent_prompt_prefix
from tools.claude_hooks_safety_pack import write_hooks, validate_hooks
from workers.base_worker import BaseWorker


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

        if shutil.which("claude"):
            result = self._run_cli(prompt, task_id, model=model, auth_mode=auth_mode)
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
    ) -> WorkerResult:
        cfg = get_config()
        if cfg.claude_hooks_safety_pack_enabled:
            repo_path = cfg.repo_path
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
        cmd = ["claude", "--print", "--dangerously-skip-permissions"]
        if model:
            cmd += ["--model", model]
        cmd.append(f"@{path}")

        # In subscription mode strip ANTHROPIC_API_KEY so the CLI falls back to
        # the OAuth/keychain token set up via `claude auth login` or `claude
        # setup-token`, rather than the API key taking precedence.
        env = None
        if auth_mode == "subscription":
            env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

        r = run_command(cmd, timeout=600, env=env)
        return WorkerResult(
            worker="claude",
            mode="cli",
            success=r.success,
            output=r.output,
            error=r.error,
            prompt_path=path,
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
