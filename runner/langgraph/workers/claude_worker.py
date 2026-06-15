"""Claude Code worker adapter — CLI, outbox, or manual fallback."""
import shutil
from config import get_config
from state import WorkerResult
from tools.log_tools import log_event
from tools.shell_tools import run_command
from workers.base_worker import BaseWorker


class ClaudeWorker(BaseWorker):
    name = "claude"

    def run_worker_prompt(self, prompt: str, task: dict) -> WorkerResult:
        task_id = task.get("id", "task")
        model = task.get("resolved_model") or None
        log_event("worker_started", {"worker": "claude", "task_id": task_id, "model": model})

        if shutil.which("claude"):
            result = self._run_cli(prompt, task_id, model=model)
        else:
            result = self._run_outbox(prompt, task_id)

        log_event("worker_finished", {"worker": "claude", "task_id": task_id, "success": result.success})
        return result

    def _run_cli(self, prompt: str, task_id: str, model: str | None = None) -> WorkerResult:
        path = self._write_outbox(task_id, prompt)
        cmd = ["claude", "--print", "--dangerously-skip-permissions"]
        if model:
            cmd += ["--model", model]
        cmd.append(f"@{path}")
        r = run_command(cmd, timeout=600)
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
