"""Codex-to-Claude repair escalation.

When a Codex worker fails with a non-usage-limit error, this gate re-runs the
same task via Claude Code as a repair attempt. If Claude succeeds, the successful
output replaces the failed Codex result so the rest of the pipeline (checks,
commit, deploy) proceeds normally. If Claude also fails, state is unchanged and
the normal failure-guard path handles the original Codex failure.

Usage-limit errors (HTTP 429, quota exhaustion) are explicitly excluded: those
are tracked and accumulated by ``codex_usage_limit_guard`` so the loop can halt
when Codex is persistently out of quota; swallowing them here would prevent the
guard from ever accumulating.

Gate behaviour (controlled via config.py / env vars):
- CODEX_TO_CLAUDE_ESCALATION_ENABLED=true (default): escalation is active.
"""
from typing import Optional

from tools.codex_usage_limit_guard import _is_usage_limit_error


def should_escalate(worker_result: dict, current_worker: str) -> bool:
    """True when Codex failed with a non-usage-limit error.

    Returns False when:
    - The worker was not Codex.
    - The worker succeeded.
    - The failure looks like an OpenAI/Codex quota or rate-limit error (those
      are handled by ``codex_usage_limit_guard`` and should still accumulate).
    """
    if current_worker != "codex":
        return False
    if worker_result.get("success", False):
        return False
    error = worker_result.get("error") or ""
    if _is_usage_limit_error(error):
        return False
    return True


def build_repair_prompt(original_prompt: str, codex_result: dict, task: dict) -> str:
    """Build a repair prompt for Claude describing what Codex couldn't finish.

    Includes the original task prompt verbatim so Claude can pick up where
    Codex left off (or start from scratch if there is no partial output).
    """
    codex_error = (codex_result.get("error") or "").strip()
    codex_output = (codex_result.get("output") or "").strip()

    error_section = f"Codex error:\n{codex_error}" if codex_error else "Codex returned no output."
    output_section = (
        f"\n\nCodex partial output (may be incomplete — use as context only):\n{codex_output[:2000]}"
        + ("\n... (truncated)" if len(codex_output) > 2000 else "")
        if codex_output
        else ""
    )

    return (
        "The Codex worker attempted the following task but failed. "
        "Your job is to complete it from scratch using Claude Code.\n\n"
        f"{error_section}{output_section}\n\n"
        "--- ORIGINAL TASK ---\n"
        f"{original_prompt}"
    )
