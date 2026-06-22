"""ChatGPT planner adapter — decides next tasks and receives worker summaries."""
import json
from pathlib import Path
from config import get_config
from state import WorkerResult
from tools.log_tools import log_event
from workers.base_worker import BaseWorker

_PLANNER_SYSTEM = """You are the lead engineer and planner for bucks.ai, an autonomous development system.
Your job is to:
1. Decide what task to work on next based on the project state and prior worker results.
2. Provide a concise task description the worker can act on.
3. Return a JSON object with keys: id, title, type, preferred_worker, branch, status="queued".

Prefer: Claude for backend/schema/API/agent tasks. Codex for UI/frontend/polish tasks.
Always return valid JSON."""

_NEXT_TASK_PROMPT = """Here is the current project state and latest worker summary:

{summary}{completed_context}

Based on this, what is the next development task? Return a JSON task object."""


class ChatGPTWorker(BaseWorker):
    name = "chatgpt"

    def run_worker_prompt(self, prompt: str, task: dict) -> WorkerResult:
        cfg = get_config()
        task_id = task.get("id", "planner")
        model = task.get("resolved_model") or cfg.chatgpt_model or "gpt-4o"

        log_event("planner_started", {"task_id": task_id, "mode": "api" if cfg.has_openai else "outbox", "model": model})

        if cfg.has_openai:
            return self._run_api(prompt, task_id, cfg.openai_api_key, model=model)
        return self._run_outbox(prompt, task_id)

    def _run_api(self, prompt: str, task_id: str, api_key: str, model: str = "gpt-4o") -> WorkerResult:
        try:
            from openai import OpenAI
            client = OpenAI(api_key=api_key)
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _PLANNER_SYSTEM},
                    {"role": "user", "content": prompt},
                ],
                temperature=0.2,
            )
            output = response.choices[0].message.content
            log_event("planner_finished", {"task_id": task_id, "mode": "api", "model": model, "output_len": len(output)})
            return WorkerResult(worker="chatgpt", mode="api", success=True, output=output)
        except Exception as e:
            log_event("error", {"worker": "chatgpt", "error": str(e)})
            return WorkerResult(worker="chatgpt", mode="api", success=False, error=str(e))

    def _run_outbox(self, prompt: str, task_id: str) -> WorkerResult:
        path = self._write_outbox(task_id, prompt)
        print(f"\n[ChatGPT] No OPENAI_API_KEY — prompt written to: {path}")
        print("Paste the ChatGPT response into:", self._inbox_path(task_id))
        response = self._read_inbox(task_id, timeout_seconds=5)
        log_event("planner_finished", {"task_id": task_id, "mode": "outbox", "got_response": bool(response)})
        return WorkerResult(
            worker="chatgpt",
            mode="outbox",
            success=bool(response),
            output=response,
            prompt_written=True,
            prompt_path=path,
        )

    def ask_for_next_task(
        self, summary: str, completed_tasks: list[dict] | None = None
    ) -> dict | None:
        completed_context = ""
        if completed_tasks:
            recent = completed_tasks[-10:]  # cap to last 10 to avoid prompt bloat
            lines = "\n".join(
                f"  - {t.get('id', '?')}: {t.get('title', '(no title)')}"
                for t in recent
            )
            completed_context = (
                f"\n\nAlready completed tasks (do NOT re-propose these):\n{lines}"
            )
        prompt = _NEXT_TASK_PROMPT.format(summary=summary, completed_context=completed_context)
        result = self.run_worker_prompt(prompt, {"id": "planner-next"})
        if not result.success or not result.output:
            return None
        try:
            text = result.output.strip()
            # Strip markdown fences if present
            if text.startswith("```"):
                text = "\n".join(text.split("\n")[1:])
                text = text.rsplit("```", 1)[0]
            return json.loads(text)
        except json.JSONDecodeError:
            log_event("error", {"worker": "chatgpt", "error": "could not parse task JSON", "output": result.output[:200]})
            return None
