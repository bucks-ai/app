"""Codex worker adapter — CLI, outbox, or manual fallback."""
import shutil
from config import get_config
from state import WorkerResult
from tools.log_tools import log_event
from tools.shell_tools import run_command
from workers.base_worker import BaseWorker


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
        cmd = ["codex", "--approval-mode", "full-auto", "--quiet", prompt]
        r = run_command(cmd, timeout=600)
        return WorkerResult(
            worker="codex",
            mode="cli",
            success=r.success,
            output=r.output,
            error=r.error,
            prompt_path=path,
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
