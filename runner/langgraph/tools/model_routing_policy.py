"""Model routing policy helpers for per-worker model selection.

The policy determines which model variant is used for each worker based on
the configured trade-off tier (performance, economy, latency). Resolution
order: task-level override → config-level override → policy tier table.
These helpers are pure: graph.py and workers own the actual dispatch.
"""

_VALID_POLICIES = frozenset({
    "default",      # per-worker default model or the MODEL env var
    "performance",  # most capable model for each worker
    "economy",      # most cost-effective model for each worker
    "latency",      # fastest model for each worker
    "disabled",     # skip resolution; workers use their built-in defaults
})

# Models are listed as: policy tier → model id. Must stay in sync with the
# currently available Claude and OpenAI model families.
_WORKER_MODELS: dict[str, dict[str, str]] = {
    "claude": {
        "default":     "claude-sonnet-4-6",
        "performance": "claude-opus-4-8",
        "economy":     "claude-haiku-4-5-20251001",
        "latency":     "claude-haiku-4-5-20251001",
    },
    "chatgpt": {
        "default":     "gpt-4o",
        "performance": "gpt-4o",
        "economy":     "gpt-4o-mini",
        "latency":     "gpt-4o-mini",
    },
    "codex": {
        "default":     "gpt-4o",
        "performance": "gpt-4o",
        "economy":     "gpt-4o-mini",
        "latency":     "gpt-4o-mini",
    },
}


def normalize_policy(policy: str | None) -> str:
    value = (policy or "default").strip().lower().replace("-", "_")
    if value in ("off", "false", "none"):
        return "disabled"
    if value not in _VALID_POLICIES:
        return "default"
    return value


def resolve_model(
    worker: str,
    policy: str | None,
    *,
    task_model_override: str | None = None,
    config_model_override: str | None = None,
) -> str | None:
    """Return the model name to use for *worker* under *policy*.

    Resolution order (first match wins):
    1. ``task_model_override`` — task-level ``preferred_model`` field.
    2. ``config_model_override`` — env-var model override (e.g. CLAUDE_MODEL).
    3. Policy-derived model from the worker/tier table.
    4. ``None`` when policy is ``disabled`` or worker is unknown.
    """
    normalized = normalize_policy(policy)
    if normalized == "disabled":
        return None
    if task_model_override:
        return task_model_override.strip()
    if config_model_override:
        return config_model_override.strip()
    worker_table = _WORKER_MODELS.get(worker or "")
    if not worker_table:
        return None
    return worker_table.get(normalized) or worker_table.get("default")


def evaluate_model_routing_policy(
    *,
    worker: str | None,
    policy: str | None,
    task: dict | None = None,
    config_model_override: str | None = None,
) -> dict:
    """Build a model routing decision for *worker* under *policy*.

    Returns a dict with:
      - resolved_model: the model name to pass to the worker (None = use default)
      - policy: normalized policy value
      - source: what drove the resolution
      - worker: the worker name
      - task_id: id from the task dict
    """
    task = task or {}
    normalized = normalize_policy(policy)
    task_override = task.get("preferred_model") or None

    model = resolve_model(
        worker or "",
        policy,
        task_model_override=task_override,
        config_model_override=config_model_override,
    )

    if normalized == "disabled":
        source = "disabled"
    elif task_override:
        source = "task_override"
    elif config_model_override:
        source = "config_override"
    else:
        source = "policy"

    return {
        "resolved_model": model,
        "policy": normalized,
        "worker": worker,
        "source": source,
        "task_id": task.get("id"),
    }


def format_routing_summary(decision: dict) -> str:
    """Format a human-readable model routing summary."""
    lines = [
        "Model Routing Decision",
        "",
        f"Worker:  {decision.get('worker') or 'unknown'}",
        f"Policy:  {decision.get('policy')}",
        f"Source:  {decision.get('source')}",
        f"Model:   {decision.get('resolved_model') or '(worker default)'}",
        f"Task:    {decision.get('task_id') or 'unknown'}",
    ]
    return "\n".join(lines) + "\n"
