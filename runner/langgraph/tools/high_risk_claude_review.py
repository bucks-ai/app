"""High-Risk Claude Review Gate.

Provides a Claude-powered secondary review for tasks flagged as high-risk.
Runs after the static Independent Code Review Gate, before resource/credential
checks, so dangerous changes are caught by an intelligent reviewer before any
commit is made.

Gate behaviour (controlled via config.py / env vars):
- HIGH_RISK_CLAUDE_REVIEW_ENABLED=true (default): gate is active.
- HIGH_RISK_CLAUDE_REVIEW_STRICT_MODE=false (default): REJECTED/NEEDS_REVIEW
  verdicts are logged as warnings and the commit proceeds; set to true to block.
- HIGH_RISK_CLAUDE_REVIEW_MODEL=claude-haiku-4-5-20251001 (default): Anthropic
  model used for the review call.

A task is considered high-risk when it carries an explicit ``high_risk: true``
or ``risk_level: "high"`` field, or when its title/type/description mentions
keywords associated with auth, payments, DB migrations, secrets, or security.

Key/mode behaviour:
- When ``ANTHROPIC_API_KEY`` is set, the gate always calls the Anthropic SDK.
- When ``CLAUDE_AUTH_MODE=subscription`` and no API key is present, the gate
  falls back to the ``claude`` CLI (which uses the subscription token), so the
  review still runs instead of being silently skipped.
- When neither an API key nor the CLI is available, the gate is silently
  skipped rather than blocking a run.
"""
import os
import re
from typing import Optional
from tools.log_tools import log_event

# Keywords in task title/type/description that suggest a high-risk change.
_HIGH_RISK_KEYWORDS = frozenset({
    "auth", "authentication", "authz", "authorization",
    "payment", "billing", "stripe", "checkout",
    "migration", "migrate",
    "sql", "database", "schema", "supabase",
    "security", "credential", "secret", "token", "api_key",
    "infrastructure", "deploy", "production",
    "permission", "rbac", "role", "admin",
    "delete", "drop", "truncate", "purge",
    "encryption", "crypto", "hash", "password",
})

_VERDICT_APPROVED = "approved"
_VERDICT_REJECTED = "rejected"
_VERDICT_NEEDS_REVIEW = "needs_review"


def is_high_risk(task: dict) -> bool:
    """Return True when the task is flagged or inferred to be high-risk."""
    if task.get("high_risk") is True:
        return True
    if str(task.get("risk_level", "")).lower() == "high":
        return True

    text = " ".join([
        str(task.get("title", "")),
        str(task.get("type", "")),
        str(task.get("description", "")),
    ]).lower()
    return any(kw in text for kw in _HIGH_RISK_KEYWORDS)


def build_review_prompt(diff_text: str, task: dict, summary: dict) -> str:
    """Build the concise review prompt sent to Claude."""
    task_title = task.get("title", "(untitled)")
    task_type = task.get("type", "general")

    files_created = summary.get("files_created") or []
    files_modified = summary.get("files_modified") or []
    all_files = [
        str(f).strip() for f in files_created + files_modified
        if str(f).strip() and str(f).strip().lower() not in {"none", "n/a", ""}
    ]
    files_str = ", ".join(all_files[:10]) or "(none reported)"

    diff_preview = (diff_text or "")[:4000]
    if len(diff_text or "") > 4000:
        diff_preview += "\n... (diff truncated)"

    return f"""You are a senior security reviewer performing a focused pre-commit review.

Task: {task_title}
Type: {task_type}
Files changed: {files_str}

Diff:
{diff_preview}

Review this change for:
1. Security vulnerabilities (exposed secrets, auth bypasses, injection risks)
2. Correctness of high-risk operations (SQL mutations, auth changes, payment logic)
3. Dangerous patterns (hardcoded credentials, missing validation, unbounded deletes)

Respond with EXACTLY one of:
  APPROVED: <one-sentence reason>
  NEEDS_REVIEW: <one-sentence concern>
  REJECTED: <one-sentence reason>

Your verdict:"""


def parse_verdict(response_text: str) -> str:
    """Parse Claude's response into a canonical verdict string."""
    if not response_text:
        return _VERDICT_NEEDS_REVIEW
    upper = response_text.strip().upper()
    if upper.startswith("APPROVED"):
        return _VERDICT_APPROVED
    if upper.startswith("REJECTED"):
        return _VERDICT_REJECTED
    return _VERDICT_NEEDS_REVIEW


def call_claude_review(
    prompt: str,
    model: str = "claude-haiku-4-5-20251001",
    api_key: Optional[str] = None,
) -> dict:
    """Call the Anthropic API and return {verdict, response_text, error}."""
    try:
        import anthropic  # already in requirements.txt
        client = anthropic.Anthropic(api_key=api_key) if api_key else anthropic.Anthropic()
        message = client.messages.create(
            model=model,
            max_tokens=256,
            messages=[{"role": "user", "content": prompt}],
        )
        response_text = message.content[0].text if message.content else ""
        return {
            "verdict": parse_verdict(response_text),
            "response_text": response_text,
            "error": None,
        }
    except Exception as exc:
        return {
            "verdict": _VERDICT_NEEDS_REVIEW,
            "response_text": "",
            "error": str(exc),
        }


def call_claude_cli_review(
    prompt: str,
    model: str = "claude-haiku-4-5-20251001",
) -> dict:
    """Run the review via the ``claude`` CLI (subscription mode fallback).

    Used when ``CLAUDE_AUTH_MODE=subscription`` and no ``ANTHROPIC_API_KEY`` is
    present. Strips the API key from the subprocess environment so the CLI uses
    the subscription OAuth/keychain token instead.

    Returns the same ``{verdict, response_text, error}`` shape as
    ``call_claude_review``.
    """
    import shutil
    import tempfile
    from tools.shell_tools import run_command

    if not shutil.which("claude"):
        return {
            "verdict": _VERDICT_NEEDS_REVIEW,
            "response_text": "",
            "error": "claude CLI not found",
        }

    tmp_path = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, prefix="hrr_review_"
        ) as f:
            f.write(prompt)
            tmp_path = f.name

        cmd = ["claude", "--print", "--dangerously-skip-permissions"]
        if model:
            cmd += ["--model", model]
        cmd.append(f"@{tmp_path}")

        # Strip ANTHROPIC_API_KEY so the CLI uses the subscription token.
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}

        result = run_command(cmd, timeout=120, env=env)
        if not result.success:
            return {
                "verdict": _VERDICT_NEEDS_REVIEW,
                "response_text": "",
                "error": result.error or "claude CLI returned a non-zero exit code",
            }

        response_text = result.output or ""
        return {
            "verdict": parse_verdict(response_text),
            "response_text": response_text,
            "error": None,
        }
    except Exception as exc:
        return {
            "verdict": _VERDICT_NEEDS_REVIEW,
            "response_text": "",
            "error": str(exc),
        }
    finally:
        if tmp_path:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass


def guard_high_risk_claude_review(
    diff_text: str,
    summary: dict,
    task: dict,
    context: str = "",
    *,
    strict_mode: bool = False,
    model: str = "claude-haiku-4-5-20251001",
    api_key: Optional[str] = None,
    claude_auth_mode: str = "api_key",
) -> dict:
    """Run the High-Risk Claude review gate and log the result.

    Returns:
        passed      (bool)      True when the review approved or was skipped.
        skipped     (bool)      True when the task is not high-risk or no key.
        verdict     (str)       'approved' | 'rejected' | 'needs_review' | 'skipped'.
        issues      (list[str]) Failure reasons; empty when passed.
        strict_mode (bool)      Mirrors the input flag.
    """
    task_id = task.get("id")

    if not is_high_risk(task):
        return {
            "passed": True, "skipped": True,
            "verdict": "skipped", "issues": [], "strict_mode": strict_mode,
        }

    resolved_key = api_key or os.getenv("ANTHROPIC_API_KEY")

    if not resolved_key:
        # Subscription mode: fall back to the claude CLI so the gate still
        # runs without an API key.
        if claude_auth_mode == "subscription":
            import shutil
            if shutil.which("claude"):
                prompt = build_review_prompt(diff_text, task, summary)
                log_event("high_risk_review_cli_fallback", {
                    "task_id": task_id,
                    "context": context,
                    "reason": "subscription mode; no ANTHROPIC_API_KEY; using claude CLI",
                }, task_id=task_id)
                result = call_claude_cli_review(prompt, model=model)
                # Continue into verdict handling below (skip the SDK call).
                verdict = result["verdict"]
                error = result.get("error")
                response_text = result.get("response_text", "")

                if error:
                    log_event("high_risk_review_error", {
                        "task_id": task_id,
                        "context": context,
                        "error": error,
                    }, task_id=task_id)
                    return {
                        "passed": True, "skipped": False,
                        "verdict": _VERDICT_NEEDS_REVIEW,
                        "issues": [f"review CLI error: {error}"],
                        "strict_mode": strict_mode,
                    }

                if verdict == _VERDICT_APPROVED:
                    log_event("high_risk_review_approved", {
                        "task_id": task_id,
                        "context": context,
                        "verdict": verdict,
                        "response": response_text[:200],
                        "mode": "cli",
                    }, task_id=task_id)
                    return {
                        "passed": True, "skipped": False,
                        "verdict": verdict, "issues": [], "strict_mode": strict_mode,
                    }

                issue = f"high-risk review {verdict}: {response_text[:200]}"
                if strict_mode:
                    log_event("high_risk_review_rejected", {
                        "task_id": task_id,
                        "context": context,
                        "verdict": verdict,
                        "response": response_text[:200],
                        "strict_mode": True,
                        "mode": "cli",
                    }, task_id=task_id)
                else:
                    log_event("high_risk_review_warned", {
                        "task_id": task_id,
                        "context": context,
                        "verdict": verdict,
                        "response": response_text[:200],
                        "strict_mode": False,
                        "mode": "cli",
                    }, task_id=task_id)

                return {
                    "passed": False, "skipped": False,
                    "verdict": verdict, "issues": [issue], "strict_mode": strict_mode,
                }
            else:
                log_event("high_risk_review_skipped", {
                    "task_id": task_id,
                    "context": context,
                    "reason": "subscription mode; no ANTHROPIC_API_KEY and no claude CLI found",
                }, task_id=task_id)
        else:
            log_event("high_risk_review_skipped", {
                "task_id": task_id,
                "context": context,
                "reason": "no ANTHROPIC_API_KEY; skipping high-risk Claude review",
            }, task_id=task_id)

        return {
            "passed": True, "skipped": True,
            "verdict": "skipped", "issues": [], "strict_mode": strict_mode,
        }

    prompt = build_review_prompt(diff_text, task, summary)
    result = call_claude_review(prompt, model=model, api_key=resolved_key)

    verdict = result["verdict"]
    error = result.get("error")
    response_text = result.get("response_text", "")

    if error:
        log_event("high_risk_review_error", {
            "task_id": task_id,
            "context": context,
            "error": error,
        }, task_id=task_id)
        return {
            "passed": True, "skipped": False,
            "verdict": _VERDICT_NEEDS_REVIEW,
            "issues": [f"review API error: {error}"],
            "strict_mode": strict_mode,
        }

    if verdict == _VERDICT_APPROVED:
        log_event("high_risk_review_approved", {
            "task_id": task_id,
            "context": context,
            "verdict": verdict,
            "response": response_text[:200],
        }, task_id=task_id)
        return {
            "passed": True, "skipped": False,
            "verdict": verdict, "issues": [], "strict_mode": strict_mode,
        }

    issue = f"high-risk review {verdict}: {response_text[:200]}"
    if strict_mode:
        log_event("high_risk_review_rejected", {
            "task_id": task_id,
            "context": context,
            "verdict": verdict,
            "response": response_text[:200],
            "strict_mode": True,
        }, task_id=task_id)
    else:
        log_event("high_risk_review_warned", {
            "task_id": task_id,
            "context": context,
            "verdict": verdict,
            "response": response_text[:200],
            "strict_mode": False,
        }, task_id=task_id)

    return {
        "passed": False, "skipped": False,
        "verdict": verdict, "issues": [issue], "strict_mode": strict_mode,
    }
