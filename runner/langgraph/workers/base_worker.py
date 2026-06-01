"""Base worker interface."""
from abc import ABC, abstractmethod
from state import WorkerResult


class BaseWorker(ABC):
    name: str = "base"

    @abstractmethod
    def run_worker_prompt(self, prompt: str, task: dict) -> WorkerResult:
        """Submit a prompt to the worker and return a WorkerResult."""
        ...

    def _outbox_path(self, task_id: str, suffix: str = "prompt") -> str:
        from pathlib import Path
        outbox = Path(__file__).parent.parent / "outbox"
        outbox.mkdir(exist_ok=True)
        return str(outbox / f"{task_id}_{suffix}.txt")

    def _inbox_path(self, task_id: str, suffix: str = "response") -> str:
        from pathlib import Path
        inbox = Path(__file__).parent.parent / "inbox"
        inbox.mkdir(exist_ok=True)
        return str(inbox / f"{task_id}_{suffix}.txt")

    def _write_outbox(self, task_id: str, prompt: str) -> str:
        path = self._outbox_path(task_id)
        with open(path, "w") as f:
            f.write(prompt)
        return path

    def _read_inbox(self, task_id: str, timeout_seconds: int = 10) -> str | None:
        import time
        path = self._inbox_path(task_id)
        deadline = time.time() + timeout_seconds
        while time.time() < deadline:
            try:
                text = open(path).read().strip()
                if text:
                    return text
            except FileNotFoundError:
                pass
            time.sleep(1)
        return None
