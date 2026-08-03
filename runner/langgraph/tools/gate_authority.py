"""Gate authority registry and proportionality policy (M4c.0).

Every blocking gate in the runner answers two questions that were previously
implicit and, in several cases, answered wrongly:

1. **Who is the authority?**  Most gates re-implement a judgement that something
   outside the runner already makes — GitHub branch protection decides what
   blocks a merge, ``check.sh``/CI decides whether the code is sound, the SQL
   guard decides whether a statement is destructive, the runner's own config
   decides whether a credential exists.  When a gate guesses instead of
   consulting that authority it can be *stricter than the system it is
   protecting*.  Motivating case (2026-08-02): ``poll_pr_checks`` failed PR #94
   because an advisory ``[informational]`` job reported failure while all five
   required checks were green.  Branch protection would have merged it happily.
   That one false failure exhausted m4c-01's retries and killed the loop.

2. **Is halting the whole loop proportionate?**  A gate that judges *this task*
   (missing acceptance criteria, an unreviewed diff, a credential this task
   needs) has no business stopping the other nine queued tasks.  A gate that
   judges *the run* (session spend cap, repeated worker timeouts, a stale loop,
   a human's strategic pause) legitimately stops everything.  The default is
   therefore **skip-this-task-and-continue**; loop-wide halts are opt-in per
   gate and must be justified by the gate assessing run-level state.

This module holds the registry and the pure decision helpers so the policy is
declarative, greppable, and unit-testable without touching the graph. The graph
node ``graph._record_gate_block`` applies the decision and the state mutation.

Nothing here weakens a genuinely destructive-action gate: entries marked
``destructive`` guard irreversible operations (non-additive SQL, spend past the
session cap) and keep their loop-wide halt.
"""
from typing import Optional

# Scope of a gate's block.
SCOPE_TASK = "task"   # skip this task, let the loop pick up the next one
SCOPE_LOOP = "loop"   # stop the whole run

# ``GATE_BLOCK_SCOPE`` policy values.
POLICY_PROPORTIONATE = "proportionate"  # default: honour each gate's declared scope
POLICY_LOOP = "loop"                    # legacy: every gate block halts the run

_REQUIRED_KEYS = frozenset({"authority", "external", "assesses", "scope", "destructive", "rationale"})

# Registry — one entry per blocking gate.
#
#   authority   name of whoever actually governs this decision
#   external    True when that authority lives outside the runner (GitHub, CI,
#               a human, the provider's API, the runner's own config/env)
#   assesses    "task" (this unit of work) or "run" (the session as a whole)
#   scope       proportionate blast radius of a block
#   destructive True when the gate guards an irreversible action; such gates
#               keep a loop-wide halt regardless of what they assess
GATE_REGISTRY: dict[str, dict] = {
    "pr_checks": {
        "authority": "github_branch_protection",
        "external": True,
        "assesses": "task",
        "scope": SCOPE_TASK,
        "destructive": False,
        "rationale": (
            "Branch protection lists the required checks; runs matching "
            "PR_CHECKS_NON_BLOCKING are advisory and reported, never fatal."
        ),
    },
    "merge_approval": {
        "authority": "human_approval_file",
        "external": True,
        "assesses": "task",
        "scope": SCOPE_TASK,
        "destructive": False,
        "rationale": (
            "A human approves one merge, not the run. The request stays in "
            "outbox/ and the task stays blocked until inbox/ says otherwise."
        ),
    },
    "sql_approval": {
        "authority": "sql_guard_and_approval_policy",
        "external": False,
        "assesses": "task",
        "scope": SCOPE_TASK,
        "destructive": True,
        "rationale": (
            "The SQL guard is the authority on whether a statement is "
            "non-additive; it blocks the apply, not the loop. Approval waits "
            "leave the task pending and the run alive."
        ),
    },
    "resource_credential": {
        "authority": "runner_config_env",
        "external": True,
        "assesses": "task",
        "scope": SCOPE_TASK,
        "destructive": False,
        "rationale": (
            "Config/env is the authority on whether a credential exists. "
            "Names already present are filtered out before a request is "
            "written (M2/M4b halted repeatedly on VERCEL_TOKEN and "
            "VERCEL_PROJECT_ID that were in .env the whole time)."
        ),
    },
    "acceptance_criteria": {
        "authority": "task_record",
        "external": True,
        "assesses": "task",
        "scope": SCOPE_TASK,
        "destructive": False,
        "rationale": "One under-specified task says nothing about the next one.",
    },
    "definition_of_done": {
        "authority": "check_script",
        "external": True,
        "assesses": "task",
        "scope": SCOPE_TASK,
        "destructive": False,
        "rationale": (
            "check.sh/CI is the authority on whether the work is sound; the "
            "DoD heuristic is a second opinion about one task's output."
        ),
    },
    "independent_code_review": {
        "authority": "ci_and_branch_protection",
        "external": True,
        "assesses": "task",
        "scope": SCOPE_TASK,
        "destructive": False,
        "rationale": "A rejected diff blocks its own merge; other tasks are unaffected.",
    },
    "high_risk_review": {
        "authority": "claude_review_verdict",
        "external": True,
        "assesses": "task",
        "scope": SCOPE_TASK,
        "destructive": False,
        "rationale": "The verdict is about this diff, and the model can be wrong.",
    },
    "strategic": {
        "authority": "human_approval_file",
        "external": True,
        "assesses": "run",
        "scope": SCOPE_LOOP,
        "destructive": False,
        "rationale": (
            "A deliberate whole-run pause every N tasks — halting everything "
            "is the entire point of the gate, not a side effect."
        ),
    },
    "cost_budget_session": {
        "authority": "session_spend_cap",
        "external": False,
        "assesses": "run",
        "scope": SCOPE_LOOP,
        "destructive": True,
        "rationale": "Spend is irreversible and the cap is a run-level budget.",
    },
    "cost_budget_task": {
        "authority": "task_spend_cap",
        "external": False,
        "assesses": "task",
        "scope": SCOPE_TASK,
        "destructive": False,
        "rationale": (
            "One expensive task overrunning MAX_TASK_COST_DOLLARS does not "
            "exhaust the session budget; skip it and keep spending the rest."
        ),
    },
    "worker_timeout": {
        "authority": "worker_process_exit",
        "external": True,
        "assesses": "run",
        "scope": SCOPE_LOOP,
        "destructive": False,
        "rationale": (
            "Only fires after MAX_WORKER_TIMEOUTS across the session — by then "
            "the evidence is systemic, not task-specific."
        ),
    },
    "stale_run": {
        "authority": "wall_clock",
        "external": False,
        "assesses": "run",
        "scope": SCOPE_LOOP,
        "destructive": False,
        "rationale": "A wedged loop is a property of the run itself.",
    },
    "repeated_error": {
        "authority": "session_error_history",
        "external": False,
        "assesses": "run",
        "scope": SCOPE_LOOP,
        "destructive": False,
        "rationale": "The same error across tasks is systemic by definition.",
    },
    "repeated_task": {
        "authority": "session_attempt_counts",
        "external": False,
        "assesses": "run",
        "scope": SCOPE_LOOP,
        "destructive": False,
        "rationale": "Re-running one task forever burns the whole run's budget.",
    },
    "codex_usage_limit": {
        "authority": "codex_provider_response",
        "external": True,
        "assesses": "run",
        "scope": SCOPE_LOOP,
        "destructive": False,
        "rationale": "The provider rate-limits the account, so every task is affected.",
    },
    "worker_health": {
        "authority": "worker_health_probe",
        "external": True,
        "assesses": "run",
        "scope": SCOPE_LOOP,
        "destructive": False,
        "rationale": "An unusable worker binary blocks every task equally.",
    },
    "deploy": {
        "authority": "vercel_deployment_status",
        "external": True,
        "assesses": "run",
        "scope": SCOPE_LOOP,
        "destructive": False,
        "rationale": (
            "A broken production deploy makes further merges unsafe; already "
            "opt-out via BLOCK_ON_DEPLOY_FAILURE."
        ),
    },
    "launch_readiness": {
        "authority": "launch_readiness_scorecard",
        "external": False,
        "assesses": "run",
        "scope": SCOPE_LOOP,
        "destructive": False,
        "rationale": "A pre-flight check of the whole environment, before any task starts.",
    },
}

# Unknown gates fall back to the conservative, pre-M4c.0 behaviour so a
# mis-typed gate name can never silently downgrade a block to a skip.
_UNKNOWN_GATE = {
    "authority": "runner_local_policy",
    "external": False,
    "assesses": "run",
    "scope": SCOPE_LOOP,
    "destructive": False,
    "rationale": "Unregistered gate — defaults to the conservative loop-wide halt.",
}


def gate_authority(gate: str) -> dict:
    """Return the registry descriptor for ``gate`` (a copy, plus ``known``)."""
    entry = GATE_REGISTRY.get(gate)
    descriptor = dict(entry or _UNKNOWN_GATE)
    descriptor["gate"] = gate
    descriptor["known"] = entry is not None
    return descriptor


def authority_payload(gate: str, **extra) -> dict:
    """Fields every blocking gate must merge into its ``log_event`` payload.

    Records *which authority the gate consulted*, so a block in the flight
    recorder can always be traced back to who actually governs the decision.
    """
    descriptor = gate_authority(gate)
    payload = {
        "gate": gate,
        "authority": descriptor["authority"],
        "authority_external": descriptor["external"],
        "gate_assesses": descriptor["assesses"],
    }
    payload.update(extra)
    return payload


def evaluate_gate_block(
    gate: str,
    *,
    systemic: bool = False,
    policy: str = POLICY_PROPORTIONATE,
) -> dict:
    """Decide the blast radius of a block raised by ``gate``.

    ``systemic`` lets a caller escalate a normally task-scoped gate when the
    evidence is run-level (e.g. the session spend cap rather than one task's).
    ``policy`` is ``GATE_BLOCK_SCOPE``: ``"loop"`` restores the pre-M4c.0
    behaviour where every gate block stops the run.

    Returns ``{"gate", "authority", "authority_external", "scope",
    "halt_loop", "destructive", "payload"}``.
    """
    descriptor = gate_authority(gate)
    # Scope is only ever *widened* here, never narrowed: a gate's declared scope
    # is its floor, so no policy value can downgrade a destructive gate's block
    # (non-additive SQL, spend past the session cap) into a skip.
    scope = descriptor["scope"]
    if systemic or policy == POLICY_LOOP:
        scope = SCOPE_LOOP

    return {
        "gate": gate,
        "authority": descriptor["authority"],
        "authority_external": descriptor["external"],
        "scope": scope,
        "halt_loop": scope == SCOPE_LOOP,
        "destructive": descriptor["destructive"],
        "payload": authority_payload(gate, block_scope=scope, gate_block_policy=policy),
    }


def normalize_policy(value: Optional[str]) -> str:
    """Coerce a ``GATE_BLOCK_SCOPE`` value; anything unrecognised is the default."""
    normalized = (value or "").strip().lower()
    return normalized if normalized in (POLICY_PROPORTIONATE, POLICY_LOOP) else POLICY_PROPORTIONATE
