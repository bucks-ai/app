"""Configuration loader for bucks.ai Autonomous Development Runner."""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path, override=False)


# Default set of runner events worth pushing to Slack. Curated to the important
# lifecycle moments — completions, failures, and human-action prompts — so Slack
# isn't flooded with every fine-grained flight-recorder event. Override via the
# SLACK_NOTIFY_EVENTS env var (comma-separated event types).
_DEFAULT_SLACK_EVENTS = frozenset({
    "task_completed",
    "error",
    "loop_stopped",
    "loop_blocked_on_deploy",
    "loop_blocked_on_failures",
    "loop_blocked_on_repeated_error",
    "loop_blocked_on_repeated_task",
    "deploy_poll_failed",
    "deploy_poll_timeout",
    "rollback_revert_policy_required",
    "sql_scan_blocked",
    "sql_approval_pending",
    "resource_request_pending",
    "check_failed",
    "loop_blocked_on_worker_timeout",
    "loop_blocked_on_cost_budget",
    "loop_blocked_on_strategic_gate",
    "strategic_gate_triggered",
    "strategic_gate_approved",
    "loop_blocked_on_codex_usage_limit",
    "task_definition_of_done_rejected",
    "task_definition_of_done_warned",
    # A task that exited clean but proved nothing. The whole point of M4c is
    # that this is louder than a crash, not quieter.
    "task_completion_evidence_missing",
    "auto_repair_failed",
    "merge_approval_required",
    "pr_checks_failed",
    "pr_checks_timeout",
    "pr_checks_no_runs",
    "pr_checks_wake_exhausted",
    # A conflict the runner refused to guess at, and — most important — work
    # that was stashed for safety but could not be restored. The latter is the
    # only way founder edits can end up somewhere unexpected, so it must always
    # reach a human.
    "git_conflict_escalated",
    "git_work_restore_failed",
    "git_work_protect_failed",
    "product_eval_failed",
    "worker_dispatch_crash",
    "loop_blocked_on_stale_run",
    "loop_blocked_on_worker_health",
    "stale_run_warning",
    "live_batch_validation_complete",
    "claude_subscription_cooldown_detected",
    "claude_subscription_cooldown_resumed",
    "loop_blocked_on_claude_subscription_cooldown",
    "analytics_report_ready",
    "migrations_pending",
    "migration_applied",
    "gate_blocked",
    "config_invariant_violated",
    "preflight_report",
    # The one message per stop that says what stopped the loop and what to do
    # about it (M4c.0). Paired with the bare "loop_stopped" token above: that
    # one is the alert, this one is the diagnosis.
    "loop_stop_report",
    "stop_diagnostics_degraded",
})


def _normalize_gate_block_scope(raw: Optional[str]) -> str:
    # tools/gate_authority owns the vocabulary; imported lazily so config.py
    # stays importable on its own (tools/__init__.py is empty, so there is no
    # cycle — this just keeps the module's import surface honest).
    from tools.gate_authority import normalize_policy

    return normalize_policy(raw)


def _load_slack_events() -> frozenset:
    raw = os.getenv("SLACK_NOTIFY_EVENTS")
    if not raw:
        return _DEFAULT_SLACK_EVENTS
    return frozenset(e.strip() for e in raw.split(",") if e.strip())


@dataclass
class RunnerConfig:
    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    anthropic_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    github_token: Optional[str] = field(default_factory=lambda: os.getenv("GITHUB_TOKEN"))
    github_repo: Optional[str] = field(
        default_factory=lambda: os.getenv("GITHUB_REPO") or os.getenv("GITHUB_REPOSITORY")
    )
    supabase_url: Optional[str] = field(default_factory=lambda: os.getenv("SUPABASE_URL"))
    supabase_service_role_key: Optional[str] = field(
        default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    )
    database_url: Optional[str] = field(default_factory=lambda: os.getenv("DATABASE_URL"))
    direct_database_url: Optional[str] = field(
        default_factory=lambda: os.getenv("DIRECT_DATABASE_URL")
    )
    vercel_token: Optional[str] = field(default_factory=lambda: os.getenv("VERCEL_TOKEN"))
    vercel_project_id: Optional[str] = field(
        default_factory=lambda: os.getenv("VERCEL_PROJECT_ID")
    )
    posthog_personal_api_key: Optional[str] = field(
        default_factory=lambda: os.getenv("POSTHOG_PERSONAL_API_KEY")
    )
    posthog_project_id: Optional[str] = field(
        default_factory=lambda: os.getenv("POSTHOG_PROJECT_ID")
    )
    posthog_host: str = field(
        default_factory=lambda: os.getenv("POSTHOG_HOST", "https://us.i.posthog.com")
    )
    sentry_auth_token: Optional[str] = field(default_factory=lambda: os.getenv("SENTRY_AUTH_TOKEN"))
    sentry_org: Optional[str] = field(default_factory=lambda: os.getenv("SENTRY_ORG"))
    sentry_project: Optional[str] = field(default_factory=lambda: os.getenv("SENTRY_PROJECT"))
    slack_webhook_url: Optional[str] = field(
        default_factory=lambda: os.getenv("SLACK_WEBHOOK_URL")
    )
    slack_notify: bool = field(
        default_factory=lambda: os.getenv("SLACK_NOTIFY", "true").lower() == "true"
    )
    slack_notify_events: frozenset = field(default_factory=_load_slack_events)
    slack_interactive_approvals: bool = field(
        default_factory=lambda: os.getenv("SLACK_INTERACTIVE_APPROVALS", "false").lower() == "true"
    )
    slack_bot_token: Optional[str] = field(default_factory=lambda: os.getenv("SLACK_BOT_TOKEN"))
    slack_app_token: Optional[str] = field(default_factory=lambda: os.getenv("SLACK_APP_TOKEN"))
    slack_channel_id: Optional[str] = field(default_factory=lambda: os.getenv("SLACK_CHANNEL_ID"))
    app_approvals_enabled: bool = field(
        default_factory=lambda: os.getenv("APP_APPROVALS_ENABLED", "false").lower() == "true"
    )
    runner_owner_user_id: Optional[str] = field(
        default_factory=lambda: os.getenv("RUNNER_OWNER_USER_ID")
    )
    repo_path: str = field(
        default_factory=lambda: os.getenv("BUCKS_AI_REPO_PATH", "/home/arnav/bucks-ai")
    )
    runner_mode: str = field(
        default_factory=lambda: os.getenv("RUNNER_MODE", "browser_or_cli")
    )
    max_loop_tasks: int = field(
        default_factory=lambda: int(os.getenv("MAX_LOOP_TASKS", "10"))
    )
    # M4c.0: measured and retained. Observed loop sessions (n=59) spanned at
    # most 203.2 min with p95 145.3 — 480 has never been the binding stop, and
    # it must stay well above MAX_STALE_TASK_MINUTES so a stuck loop reports
    # `stale_run` rather than `max_runtime` (invariant 5).
    max_runtime_minutes: int = field(
        default_factory=lambda: int(os.getenv("MAX_RUNTIME_MINUTES", "480"))
    )
    auto_merge: bool = field(
        default_factory=lambda: os.getenv("AUTO_MERGE", "true").lower() == "true"
    )
    auto_cleanup_branches: bool = field(
        default_factory=lambda: os.getenv("AUTO_CLEANUP_BRANCHES", "true").lower() == "true"
    )
    merge_via_pr: bool = field(
        default_factory=lambda: os.getenv("MERGE_VIA_PR", "true").lower() == "true"
    )
    # M4c.0 calibration (docs/M4C0-THRESHOLD-CALIBRATION.md): observed check
    # completion over 61 samples was p95 681.6s / max 695.5s, so the old 900s
    # left only 1.3x headroom and produced 8 pr_checks_timeout events.
    pr_checks_timeout_s: int = field(
        default_factory=lambda: int(os.getenv("PR_CHECKS_TIMEOUT_S", "1200"))
    )
    pr_checks_poll_interval_s: int = field(
        default_factory=lambda: int(os.getenv("PR_CHECKS_POLL_INTERVAL_S", "20"))
    )
    # M4c.0: check runs register within one poll interval — 67 samples, max
    # 22.6s. 120s is 5x that ceiling and fast-fails a check-less PR at 240s
    # instead of 360s.
    pr_checks_empty_grace_s: int = field(
        default_factory=lambda: int(os.getenv("PR_CHECKS_EMPTY_GRACE_S", "120"))
    )
    # Check runs whose NAME contains any of these (case-insensitive) substrings
    # are advisory: their conclusion is reported but never blocks a merge.
    # Branch protection is the authority on what actually blocks; a job that is
    # informational by design (M2's Vercel-preview E2E) must not gate the runner.
    pr_checks_non_blocking: list = field(
        default_factory=lambda: [
            s.strip().lower()
            for s in os.getenv("PR_CHECKS_NON_BLOCKING", "[informational]").split(",")
            if s.strip()
        ]
    )
    # M4c git/PR autonomy (tools/git_autonomy.py). A PR whose head SHA never got
    # check runs scheduled is woken by pushing a fresh head SHA on top of latest
    # main, then re-polled — instead of failing the task and waiting for the
    # founder to do it by hand. 0 disables the recovery entirely.
    pr_checks_wake_attempts: int = field(
        default_factory=lambda: int(os.getenv("PR_CHECKS_WAKE_ATTEMPTS", "1"))
    )
    # Ordered ladder of wake strategies; see git_autonomy.DEFAULT_WAKE_STRATEGIES.
    pr_checks_wake_strategies: list = field(
        default_factory=lambda: [
            s.strip().lower()
            for s in os.getenv(
                "PR_CHECKS_WAKE_STRATEGIES", "update_branch,rebase,merge_base,empty_commit"
            ).split(",")
            if s.strip()
        ]
    )
    # Auto-resolve conflicts that are provably formatting-only (identical code
    # after line-wrap/whitespace normalisation). Anything semantic is always
    # escalated regardless of this flag.
    git_auto_resolve_trivial_conflicts: bool = field(
        default_factory=lambda: os.getenv("GIT_AUTO_RESOLVE_TRIVIAL_CONFLICTS", "true").lower() == "true"
    )
    # File suffixes eligible for trivial-conflict auto-resolution. The default
    # (git_autonomy._DEFAULT_AUTO_RESOLVE_SUFFIXES) deliberately excludes
    # formats where whitespace or a trailing comma IS content (.md, .json,
    # .yaml, .sh).
    git_trivial_conflict_suffixes: list = field(
        default_factory=lambda: [
            s.strip().lower() if s.strip().startswith(".") else f".{s.strip().lower()}"
            for s in os.getenv("GIT_TRIVIAL_CONFLICT_SUFFIXES", "").split(",")
            if s.strip()
        ]
    )
    # AGENTS.md forbids `git push --force`. The rebase rung of the check-wake
    # ladder rewrites an already-pushed branch and so is inert unless this is
    # on; even then it pushes with --force-with-lease, which refuses when origin
    # moved since our fetch (i.e. when a human pushed to the branch). Off by
    # default: the merge_base rung reaches the same end state without any
    # history rewrite.
    git_allow_force_with_lease: bool = field(
        default_factory=lambda: os.getenv("GIT_ALLOW_FORCE_WITH_LEASE", "false").lower() == "true"
    )
    # Prefer `pull --rebase` over a merge when syncing a branch with its base.
    # M4b needed the founder to hand-choose rebase vs reset on a diverged main;
    # rebase is now the standing answer and reset is never an option.
    git_prefer_rebase: bool = field(
        default_factory=lambda: os.getenv("GIT_PREFER_REBASE", "true").lower() == "true"
    )
    auto_deploy: bool = field(
        default_factory=lambda: os.getenv("AUTO_DEPLOY", "true").lower() == "true"
    )
    auto_deploy_poll: bool = field(
        default_factory=lambda: os.getenv("AUTO_DEPLOY_POLL", "true").lower() == "true"
    )
    block_on_deploy_failure: bool = field(
        default_factory=lambda: os.getenv("BLOCK_ON_DEPLOY_FAILURE", "true").lower() == "true"
    )
    rollback_revert_policy: str = field(
        default_factory=lambda: os.getenv("ROLLBACK_REVERT_POLICY", "manual")
    )
    vercel_poll_timeout: int = field(
        default_factory=lambda: int(os.getenv("VERCEL_POLL_TIMEOUT", "180"))
    )
    vercel_poll_interval: int = field(
        default_factory=lambda: int(os.getenv("VERCEL_POLL_INTERVAL", "5"))
    )
    auto_apply_sql: bool = field(
        default_factory=lambda: os.getenv("AUTO_APPLY_SQL", "true").lower() == "true"
    )
    require_sql_approval: bool = field(
        default_factory=lambda: os.getenv("REQUIRE_SQL_APPROVAL", "false").lower() == "true"
    )
    sql_environment: str = field(
        default_factory=lambda: os.getenv("SQL_ENVIRONMENT", "")
    )
    sql_approval_policy: str = field(
        default_factory=lambda: os.getenv("SQL_APPROVAL_POLICY", "require_on_production")
    )
    auto_apply_migrations: bool = field(
        default_factory=lambda: os.getenv("AUTO_APPLY_MIGRATIONS", "false").lower() == "true"
    )
    resource_gate_enabled: bool = field(
        default_factory=lambda: os.getenv("RESOURCE_GATE", "true").lower() == "true"
    )
    # How wide a gate's block reaches. "proportionate" (default) honours each
    # gate's declared scope in tools/gate_authority.py, so a gate judging one
    # task skips that task and lets the loop continue; "loop" restores the
    # pre-M4c.0 behaviour where every gate block stops the whole run.
    gate_block_scope: str = field(
        default_factory=lambda: _normalize_gate_block_scope(os.getenv("GATE_BLOCK_SCOPE"))
    )
    failure_guard_enabled: bool = field(
        default_factory=lambda: os.getenv("FAILURE_GUARD", "true").lower() == "true"
    )
    max_task_retries: int = field(
        default_factory=lambda: int(os.getenv("MAX_TASK_RETRIES", "1"))
    )
    max_consecutive_failures: int = field(
        default_factory=lambda: int(os.getenv("MAX_CONSECUTIVE_FAILURES", "3"))
    )
    max_repeated_errors: int = field(
        default_factory=lambda: int(os.getenv("MAX_REPEATED_ERRORS", "3"))
    )
    repeated_error_window: int = field(
        default_factory=lambda: int(os.getenv("REPEATED_ERROR_WINDOW", "10"))
    )
    max_task_attempts: int = field(
        default_factory=lambda: int(os.getenv("MAX_TASK_ATTEMPTS", "3"))
    )
    worker_timeout_guard_enabled: bool = field(
        default_factory=lambda: os.getenv("WORKER_TIMEOUT_GUARD", "true").lower() == "true"
    )
    max_worker_timeouts: int = field(
        default_factory=lambda: int(os.getenv("MAX_WORKER_TIMEOUTS", "3"))
    )
    # M4c.0 calibration: 570s sat below the observed p90 of healthy worker runs
    # (606.4s), so 22/181 successful runs — 12.2% — were classified as timeouts
    # the CLI never caused. The threshold now sits *above* the CLI ceiling, so
    # only a genuine hard kill can be labelled a timeout. Invariant 1 in
    # tools/config_invariants.py enforces that ordering.
    worker_timeout_threshold: int = field(
        default_factory=lambda: int(os.getenv("WORKER_TIMEOUT_THRESHOLD", "2700"))
    )
    # M4c.0: worker p95 was 755.1s overall and 1653.4s for `test` tasks, and the
    # old 1800s ceiling right-censored the distribution (a run finished at
    # exactly 1800.3s). 2400s clears the `test` p95 with ~45% headroom.
    claude_cli_timeout_s: int = field(
        default_factory=lambda: int(os.getenv("CLAUDE_CLI_TIMEOUT_S", "2400"))
    )
    cost_budget_guard_enabled: bool = field(
        default_factory=lambda: os.getenv("COST_BUDGET_GUARD", "true").lower() == "true"
    )
    max_session_cost_dollars: float = field(
        default_factory=lambda: float(os.getenv("MAX_SESSION_COST_DOLLARS", "0.0"))
    )
    max_task_cost_dollars: float = field(
        default_factory=lambda: float(os.getenv("MAX_TASK_COST_DOLLARS", "0.0"))
    )
    estimated_cost_per_task_dollars: float = field(
        default_factory=lambda: float(os.getenv("ESTIMATED_COST_PER_TASK_DOLLARS", "0.0"))
    )
    strategic_gate_enabled: bool = field(
        default_factory=lambda: os.getenv("STRATEGIC_GATE", "true").lower() == "true"
    )
    strategic_pause_interval: int = field(
        default_factory=lambda: int(os.getenv("STRATEGIC_PAUSE_INTERVAL", "0"))
    )
    codex_usage_limit_guard_enabled: bool = field(
        default_factory=lambda: os.getenv("CODEX_USAGE_LIMIT_GUARD", "true").lower() == "true"
    )
    max_codex_usage_limit_errors: int = field(
        default_factory=lambda: int(os.getenv("MAX_CODEX_USAGE_LIMIT_ERRORS", "2"))
    )
    model_routing_policy: str = field(
        default_factory=lambda: os.getenv("MODEL_ROUTING_POLICY", "default")
    )
    claude_model: str = field(
        default_factory=lambda: os.getenv("CLAUDE_MODEL", "")
    )
    chatgpt_model: str = field(
        default_factory=lambda: os.getenv("CHATGPT_MODEL", "")
    )
    context_compression_max_tokens: int = field(
        default_factory=lambda: int(os.getenv("CONTEXT_COMPRESSION_MAX_TOKENS", "12000"))
    )
    context_compression_keep_recent: int = field(
        default_factory=lambda: int(os.getenv("CONTEXT_COMPRESSION_KEEP_RECENT", "4"))
    )
    claude_auth_mode: str = field(
        default_factory=lambda: os.getenv("CLAUDE_AUTH_MODE", "api_key")
    )
    mission_compiler_enabled: bool = field(
        default_factory=lambda: os.getenv("MISSION_COMPILER", "true").lower() == "true"
    )
    seeded_mission_queue_enabled: bool = field(
        default_factory=lambda: os.getenv("SEEDED_MISSION_QUEUE", "true").lower() == "true"
    )
    seeded_mission_queue_strict: bool = field(
        default_factory=lambda: os.getenv("SEEDED_MISSION_QUEUE_STRICT", "false").lower() == "true"
    )
    business_execution_enabled: bool = field(
        default_factory=lambda: os.getenv("BUSINESS_EXECUTION_ENABLED", "false").lower() == "true"
    )
    planner_quality_gate_v2_enabled: bool = field(
        default_factory=lambda: os.getenv("PLANNER_QUALITY_GATE_V2", "true").lower() == "true"
    )
    planner_scope_guard_enabled: bool = field(
        default_factory=lambda: os.getenv("PLANNER_SCOPE_GUARD", "true").lower() == "true"
    )
    acceptance_criteria_gate_enabled: bool = field(
        default_factory=lambda: os.getenv("ACCEPTANCE_CRITERIA_GATE_ENABLED", "true").lower() == "true"
    )
    acceptance_criteria_strict_mode: bool = field(
        default_factory=lambda: os.getenv("ACCEPTANCE_CRITERIA_STRICT_MODE", "false").lower() == "true"
    )
    definition_of_done_gate_enabled: bool = field(
        default_factory=lambda: os.getenv("DEFINITION_OF_DONE_GATE_ENABLED", "true").lower() == "true"
    )
    definition_of_done_strict_mode: bool = field(
        default_factory=lambda: os.getenv("DEFINITION_OF_DONE_STRICT_MODE", "false").lower() == "true"
    )
    # M4c: completion requires positive, verified evidence. Intentionally has no
    # strict/warn split — the DoD gate's warn-only default is how ai-infra-03
    # was scored complete twice with nothing deployed.
    completion_evidence_gate_enabled: bool = field(
        default_factory=lambda: os.getenv("COMPLETION_EVIDENCE_GATE_ENABLED", "true").lower() == "true"
    )
    claude_subagent_pack_enabled: bool = field(
        default_factory=lambda: os.getenv("CLAUDE_SUBAGENT_PACK_ENABLED", "true").lower() == "true"
    )
    claude_hooks_safety_pack_enabled: bool = field(
        default_factory=lambda: os.getenv("CLAUDE_HOOKS_SAFETY_PACK_ENABLED", "true").lower() == "true"
    )
    claude_hooks_safety_pack_auto_install: bool = field(
        default_factory=lambda: os.getenv("CLAUDE_HOOKS_SAFETY_PACK_AUTO_INSTALL", "true").lower() == "true"
    )
    independent_code_review_enabled: bool = field(
        default_factory=lambda: os.getenv("INDEPENDENT_CODE_REVIEW_ENABLED", "true").lower() == "true"
    )
    independent_code_review_strict_mode: bool = field(
        default_factory=lambda: os.getenv("INDEPENDENT_CODE_REVIEW_STRICT_MODE", "false").lower() == "true"
    )
    high_risk_claude_review_enabled: bool = field(
        default_factory=lambda: os.getenv("HIGH_RISK_CLAUDE_REVIEW_ENABLED", "true").lower() == "true"
    )
    high_risk_claude_review_strict_mode: bool = field(
        default_factory=lambda: os.getenv("HIGH_RISK_CLAUDE_REVIEW_STRICT_MODE", "false").lower() == "true"
    )
    high_risk_claude_review_model: str = field(
        default_factory=lambda: os.getenv("HIGH_RISK_CLAUDE_REVIEW_MODEL", "claude-haiku-4-5-20251001")
    )
    codex_to_claude_escalation_enabled: bool = field(
        default_factory=lambda: os.getenv("CODEX_TO_CLAUDE_ESCALATION_ENABLED", "true").lower() == "true"
    )
    auto_repair_loop_enabled: bool = field(
        default_factory=lambda: os.getenv("AUTO_REPAIR_LOOP_ENABLED", "true").lower() == "true"
    )
    max_auto_repair_attempts: int = field(
        default_factory=lambda: int(os.getenv("MAX_AUTO_REPAIR_ATTEMPTS", "2"))
    )
    risk_based_merge_approval_enabled: bool = field(
        default_factory=lambda: os.getenv("RISK_BASED_MERGE_APPROVAL_ENABLED", "true").lower() == "true"
    )
    merge_approval_policy: str = field(
        default_factory=lambda: os.getenv("MERGE_APPROVAL_POLICY", "require_approval_on_high")
    )
    e2e_enabled: bool = field(
        default_factory=lambda: os.getenv("E2E_ENABLED", "false").lower() == "true"
    )
    e2e_base_url: Optional[str] = field(
        default_factory=lambda: os.getenv("E2E_BASE_URL")
    )
    e2e_timeout_ms: int = field(
        default_factory=lambda: int(os.getenv("E2E_TIMEOUT_MS", "15000"))
    )
    e2e_headless: bool = field(
        default_factory=lambda: os.getenv("E2E_HEADLESS", "true").lower() == "true"
    )
    ui_flow_validation_enabled: bool = field(
        default_factory=lambda: os.getenv("UI_FLOW_VALIDATION_ENABLED", "false").lower() == "true"
    )
    ui_flow_config_path: Optional[str] = field(
        default_factory=lambda: os.getenv("UI_FLOW_CONFIG_PATH")
    )
    ui_flow_timeout_ms: int = field(
        default_factory=lambda: int(os.getenv("UI_FLOW_TIMEOUT_MS", "20000"))
    )
    ui_flow_strict: bool = field(
        default_factory=lambda: os.getenv("UI_FLOW_STRICT", "false").lower() == "true"
    )
    product_eval_enabled: bool = field(
        default_factory=lambda: os.getenv("PRODUCT_EVAL_ENABLED", "false").lower() == "true"
    )
    product_eval_config_path: Optional[str] = field(
        default_factory=lambda: os.getenv("PRODUCT_EVAL_CONFIG_PATH")
    )
    product_eval_timeout_ms: int = field(
        default_factory=lambda: int(os.getenv("PRODUCT_EVAL_TIMEOUT_MS", "15000"))
    )
    product_eval_strict: bool = field(
        default_factory=lambda: os.getenv("PRODUCT_EVAL_STRICT", "false").lower() == "true"
    )
    http_retry_enabled: bool = field(
        default_factory=lambda: os.getenv("HTTP_RETRY_ENABLED", "true").lower() == "true"
    )
    http_retry_attempts: int = field(
        default_factory=lambda: int(os.getenv("HTTP_RETRY_ATTEMPTS", "3"))
    )
    http_retry_initial_wait_s: float = field(
        default_factory=lambda: float(os.getenv("HTTP_RETRY_INITIAL_WAIT_S", "1.0"))
    )
    http_retry_max_wait_s: float = field(
        default_factory=lambda: float(os.getenv("HTTP_RETRY_MAX_WAIT_S", "10.0"))
    )
    business_output_rubrics_enabled: bool = field(
        default_factory=lambda: os.getenv("BUSINESS_OUTPUT_RUBRICS_ENABLED", "true").lower() == "true"
    )
    business_output_rubrics_strict_mode: bool = field(
        default_factory=lambda: os.getenv("BUSINESS_OUTPUT_RUBRICS_STRICT_MODE", "false").lower() == "true"
    )
    business_output_rubrics_pass_threshold: float = field(
        default_factory=lambda: float(os.getenv("BUSINESS_OUTPUT_RUBRICS_PASS_THRESHOLD", "0.6"))
    )
    launch_readiness_scorecard_enabled: bool = field(
        default_factory=lambda: os.getenv("LAUNCH_READINESS_SCORECARD_ENABLED", "true").lower() == "true"
    )
    launch_readiness_scorecard_strict_mode: bool = field(
        default_factory=lambda: os.getenv("LAUNCH_READINESS_SCORECARD_STRICT_MODE", "false").lower() == "true"
    )
    launch_readiness_scorecard_pass_threshold: float = field(
        default_factory=lambda: float(os.getenv("LAUNCH_READINESS_SCORECARD_PASS_THRESHOLD", "0.7"))
    )
    fast_engineering_mode_enabled: bool = field(
        default_factory=lambda: os.getenv("FAST_ENGINEERING_MODE", "false").lower() == "true"
    )
    runner_dry_run: bool = field(
        default_factory=lambda: os.getenv("RUNNER_DRY_RUN", "false").lower() == "true"
    )
    # M4c: refuse `run-loop` from a non-main branch or a dirty tree. Workers
    # inherit the runner's working tree, and a half-finished branch is
    # indistinguishable to them from intended state. Off only for deliberate
    # local experiments — never in an unattended run.
    loop_start_preflight_enabled: bool = field(
        default_factory=lambda: os.getenv("LOOP_START_PREFLIGHT", "true").lower() == "true"
    )
    # M4c.0: verify production assumptions once, at loop start, before any task
    # is claimed. Reports only — it never halts on its own (the one halting
    # condition, dirty tree / wrong branch, belongs to LOOP_START_PREFLIGHT
    # above and is re-reported here for a single consolidated summary).
    startup_preflight_enabled: bool = field(
        default_factory=lambda: os.getenv("STARTUP_PREFLIGHT", "true").lower() == "true"
    )
    preflight_required_tables: tuple = field(
        default_factory=lambda: tuple(
            t.strip() for t in os.getenv("PREFLIGHT_REQUIRED_TABLES", "").split(",") if t.strip()
        )
    )
    worker_health_probe_enabled: bool = field(
        default_factory=lambda: os.getenv("WORKER_HEALTH_PROBE", "true").lower() == "true"
    )
    worker_health_live_ping_enabled: bool = field(
        default_factory=lambda: os.getenv("WORKER_HEALTH_LIVE_PING", "false").lower() == "true"
    )
    worker_health_live_ping_timeout_s: float = field(
        default_factory=lambda: float(os.getenv("WORKER_HEALTH_LIVE_PING_TIMEOUT_S", "10.0"))
    )
    stale_run_watchdog_enabled: bool = field(
        default_factory=lambda: os.getenv("STALE_RUN_WATCHDOG", "true").lower() == "true"
    )
    # M4c.0: 60 min killed sessions that were working correctly — observed
    # end-to-end task duration reached 41.1 min, and the worst legitimate
    # single attempt (45 min worker ceiling + 11.6 min PR checks + deploy +
    # backoff) is ~70 min. 120 min clears that and still bounds a dead loop.
    max_stale_task_minutes: int = field(
        default_factory=lambda: int(os.getenv("MAX_STALE_TASK_MINUTES", "120"))
    )
    # M4c.0: the old 30 min warning fired on legitimate 30.0 and 34.0 min gaps.
    stale_run_warn_minutes: int = field(
        default_factory=lambda: int(os.getenv("STALE_RUN_WARN_MINUTES", "75"))
    )
    # M4c.0: measured and retained. Retries are rare (30 task_retry_scheduled
    # events across the whole log), so there is no duration distribution to fit
    # — these bounds are governed by a budget instead: at MAX_TASK_ATTEMPTS=3
    # the waits are 30s then 60s and the 300s cap is never reached, and the
    # worst case (2700 + 300*2 = 3300s) fits inside the 7200s stale window.
    # Invariant 6 in tools/config_invariants.py enforces that budget.
    failure_retry_backoff_enabled: bool = field(
        default_factory=lambda: os.getenv("FAILURE_RETRY_BACKOFF", "true").lower() == "true"
    )
    failure_retry_backoff_base_s: float = field(
        default_factory=lambda: float(os.getenv("FAILURE_RETRY_BACKOFF_BASE_S", "30.0"))
    )
    failure_retry_backoff_multiplier: float = field(
        default_factory=lambda: float(os.getenv("FAILURE_RETRY_BACKOFF_MULTIPLIER", "2.0"))
    )
    failure_retry_backoff_max_s: float = field(
        default_factory=lambda: float(os.getenv("FAILURE_RETRY_BACKOFF_MAX_S", "300.0"))
    )
    live_batch_validation_report_enabled: bool = field(
        default_factory=lambda: os.getenv("LIVE_BATCH_VALIDATION_REPORT", "true").lower() == "true"
    )
    claude_subscription_cooldown_enabled: bool = field(
        default_factory=lambda: os.getenv("CLAUDE_SUBSCRIPTION_COOLDOWN", "true").lower() == "true"
    )
    claude_subscription_cooldown_wait_s: int = field(
        default_factory=lambda: int(os.getenv("CLAUDE_SUBSCRIPTION_COOLDOWN_WAIT_S", "3600"))
    )
    claude_subscription_cooldown_max_waits: int = field(
        default_factory=lambda: int(os.getenv("CLAUDE_SUBSCRIPTION_COOLDOWN_MAX_WAITS", "3"))
    )

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_claude(self) -> bool:
        """True if Claude can be used — either via subscription or API key."""
        return self.claude_auth_mode == "subscription" or self.has_anthropic

    @property
    def has_github(self) -> bool:
        return bool(self.github_token)

    @property
    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    @property
    def has_database(self) -> bool:
        """True if a direct Postgres connection is configured (DATABASE_URL and/or DIRECT_DATABASE_URL)."""
        return bool(self.database_url or self.direct_database_url)

    @property
    def has_vercel(self) -> bool:
        return bool(self.vercel_token)

    @property
    def has_posthog(self) -> bool:
        return bool(self.posthog_personal_api_key and self.posthog_project_id)

    @property
    def has_sentry(self) -> bool:
        return bool(self.sentry_auth_token and self.sentry_org and self.sentry_project)

    @property
    def has_slack(self) -> bool:
        return bool(self.slack_webhook_url)

    @property
    def has_slack_interactive_approvals(self) -> bool:
        """True when the approvals_daemon.py has everything it needs to run."""
        return bool(self.slack_bot_token and self.slack_app_token and self.slack_channel_id)

    @property
    def has_app_approvals(self) -> bool:
        """True when app_approvals_daemon.py has everything it needs to run."""
        return bool(self.app_approvals_enabled and self.has_supabase and self.runner_owner_user_id)

    def report(self) -> dict:
        return {
            "openai": self.has_openai,
            "anthropic": self.has_anthropic,
            "claude_auth_mode": self.claude_auth_mode,
            "github": self.has_github,
            "github_repo": self.github_repo,
            "supabase": self.has_supabase,
            "database": self.has_database,
            "has_direct_database_url": bool(self.direct_database_url),
            "vercel": self.has_vercel,
            "vercel_project_id": self.vercel_project_id,
            "posthog": self.has_posthog,
            "posthog_project_id": self.posthog_project_id,
            "posthog_host": self.posthog_host,
            "sentry": self.has_sentry,
            "sentry_org": self.sentry_org,
            "sentry_project": self.sentry_project,
            "slack": self.has_slack,
            "slack_notify": self.slack_notify,
            "slack_interactive_approvals": self.slack_interactive_approvals,
            "slack_interactive_approvals_configured": self.has_slack_interactive_approvals,
            "app_approvals_enabled": self.app_approvals_enabled,
            "app_approvals_configured": self.has_app_approvals,
            "repo_path": self.repo_path,
            "runner_mode": self.runner_mode,
            "max_loop_tasks": self.max_loop_tasks,
            "max_runtime_minutes": self.max_runtime_minutes,
            "auto_merge": self.auto_merge,
            "auto_cleanup_branches": self.auto_cleanup_branches,
            "merge_via_pr": self.merge_via_pr,
            "pr_checks_timeout_s": self.pr_checks_timeout_s,
            "pr_checks_poll_interval_s": self.pr_checks_poll_interval_s,
            "pr_checks_empty_grace_s": self.pr_checks_empty_grace_s,
            "pr_checks_non_blocking": self.pr_checks_non_blocking,
            "pr_checks_wake_attempts": self.pr_checks_wake_attempts,
            "pr_checks_wake_strategies": self.pr_checks_wake_strategies,
            "git_auto_resolve_trivial_conflicts": self.git_auto_resolve_trivial_conflicts,
            "git_trivial_conflict_suffixes": self.git_trivial_conflict_suffixes,
            "git_allow_force_with_lease": self.git_allow_force_with_lease,
            "git_prefer_rebase": self.git_prefer_rebase,
            "auto_deploy": self.auto_deploy,
            "auto_deploy_poll": self.auto_deploy_poll,
            "block_on_deploy_failure": self.block_on_deploy_failure,
            "rollback_revert_policy": self.rollback_revert_policy,
            "vercel_poll_timeout": self.vercel_poll_timeout,
            "vercel_poll_interval": self.vercel_poll_interval,
            "auto_apply_sql": self.auto_apply_sql,
            "require_sql_approval": self.require_sql_approval,
            "sql_environment": self.sql_environment,
            "sql_approval_policy": self.sql_approval_policy,
            "auto_apply_migrations": self.auto_apply_migrations,
            "resource_gate_enabled": self.resource_gate_enabled,
            "gate_block_scope": self.gate_block_scope,
            "failure_guard_enabled": self.failure_guard_enabled,
            "max_task_retries": self.max_task_retries,
            "max_consecutive_failures": self.max_consecutive_failures,
            "max_repeated_errors": self.max_repeated_errors,
            "repeated_error_window": self.repeated_error_window,
            "max_task_attempts": self.max_task_attempts,
            "worker_timeout_guard_enabled": self.worker_timeout_guard_enabled,
            "max_worker_timeouts": self.max_worker_timeouts,
            "worker_timeout_threshold": self.worker_timeout_threshold,
            "claude_cli_timeout_s": self.claude_cli_timeout_s,
            "cost_budget_guard_enabled": self.cost_budget_guard_enabled,
            "max_session_cost_dollars": self.max_session_cost_dollars,
            "max_task_cost_dollars": self.max_task_cost_dollars,
            "estimated_cost_per_task_dollars": self.estimated_cost_per_task_dollars,
            "strategic_gate_enabled": self.strategic_gate_enabled,
            "strategic_pause_interval": self.strategic_pause_interval,
            "codex_usage_limit_guard_enabled": self.codex_usage_limit_guard_enabled,
            "max_codex_usage_limit_errors": self.max_codex_usage_limit_errors,
            "model_routing_policy": self.model_routing_policy,
            "claude_model": self.claude_model,
            "chatgpt_model": self.chatgpt_model,
            "context_compression_max_tokens": self.context_compression_max_tokens,
            "context_compression_keep_recent": self.context_compression_keep_recent,
            "mission_compiler_enabled": self.mission_compiler_enabled,
            "seeded_mission_queue_enabled": self.seeded_mission_queue_enabled,
            "seeded_mission_queue_strict": self.seeded_mission_queue_strict,
            "business_execution_enabled": self.business_execution_enabled,
            "planner_quality_gate_v2_enabled": self.planner_quality_gate_v2_enabled,
            "planner_scope_guard_enabled": self.planner_scope_guard_enabled,
            "acceptance_criteria_gate_enabled": self.acceptance_criteria_gate_enabled,
            "acceptance_criteria_strict_mode": self.acceptance_criteria_strict_mode,
            "definition_of_done_gate_enabled": self.definition_of_done_gate_enabled,
            "definition_of_done_strict_mode": self.definition_of_done_strict_mode,
            "completion_evidence_gate_enabled": self.completion_evidence_gate_enabled,
            "claude_subagent_pack_enabled": self.claude_subagent_pack_enabled,
            "claude_hooks_safety_pack_enabled": self.claude_hooks_safety_pack_enabled,
            "claude_hooks_safety_pack_auto_install": self.claude_hooks_safety_pack_auto_install,
            "independent_code_review_enabled": self.independent_code_review_enabled,
            "independent_code_review_strict_mode": self.independent_code_review_strict_mode,
            "high_risk_claude_review_enabled": self.high_risk_claude_review_enabled,
            "high_risk_claude_review_strict_mode": self.high_risk_claude_review_strict_mode,
            "high_risk_claude_review_model": self.high_risk_claude_review_model,
            "codex_to_claude_escalation_enabled": self.codex_to_claude_escalation_enabled,
            "auto_repair_loop_enabled": self.auto_repair_loop_enabled,
            "max_auto_repair_attempts": self.max_auto_repair_attempts,
            "risk_based_merge_approval_enabled": self.risk_based_merge_approval_enabled,
            "merge_approval_policy": self.merge_approval_policy,
            "e2e_enabled": self.e2e_enabled,
            "e2e_base_url": self.e2e_base_url,
            "e2e_timeout_ms": self.e2e_timeout_ms,
            "e2e_headless": self.e2e_headless,
            "ui_flow_validation_enabled": self.ui_flow_validation_enabled,
            "ui_flow_config_path": self.ui_flow_config_path,
            "ui_flow_timeout_ms": self.ui_flow_timeout_ms,
            "ui_flow_strict": self.ui_flow_strict,
            "product_eval_enabled": self.product_eval_enabled,
            "product_eval_config_path": self.product_eval_config_path,
            "product_eval_timeout_ms": self.product_eval_timeout_ms,
            "product_eval_strict": self.product_eval_strict,
            "http_retry_enabled": self.http_retry_enabled,
            "http_retry_attempts": self.http_retry_attempts,
            "http_retry_initial_wait_s": self.http_retry_initial_wait_s,
            "http_retry_max_wait_s": self.http_retry_max_wait_s,
            "business_output_rubrics_enabled": self.business_output_rubrics_enabled,
            "business_output_rubrics_strict_mode": self.business_output_rubrics_strict_mode,
            "business_output_rubrics_pass_threshold": self.business_output_rubrics_pass_threshold,
            "launch_readiness_scorecard_enabled": self.launch_readiness_scorecard_enabled,
            "launch_readiness_scorecard_strict_mode": self.launch_readiness_scorecard_strict_mode,
            "launch_readiness_scorecard_pass_threshold": self.launch_readiness_scorecard_pass_threshold,
            "fast_engineering_mode_enabled": self.fast_engineering_mode_enabled,
            "runner_dry_run": self.runner_dry_run,
            "loop_start_preflight_enabled": self.loop_start_preflight_enabled,
            "startup_preflight_enabled": self.startup_preflight_enabled,
            "preflight_required_tables": self.preflight_required_tables,
            "worker_health_probe_enabled": self.worker_health_probe_enabled,
            "worker_health_live_ping_enabled": self.worker_health_live_ping_enabled,
            "worker_health_live_ping_timeout_s": self.worker_health_live_ping_timeout_s,
            "stale_run_watchdog_enabled": self.stale_run_watchdog_enabled,
            "max_stale_task_minutes": self.max_stale_task_minutes,
            "stale_run_warn_minutes": self.stale_run_warn_minutes,
            "failure_retry_backoff_enabled": self.failure_retry_backoff_enabled,
            "failure_retry_backoff_base_s": self.failure_retry_backoff_base_s,
            "failure_retry_backoff_multiplier": self.failure_retry_backoff_multiplier,
            "failure_retry_backoff_max_s": self.failure_retry_backoff_max_s,
            "live_batch_validation_report_enabled": self.live_batch_validation_report_enabled,
            "claude_subscription_cooldown_enabled": self.claude_subscription_cooldown_enabled,
            "claude_subscription_cooldown_wait_s": self.claude_subscription_cooldown_wait_s,
            "claude_subscription_cooldown_max_waits": self.claude_subscription_cooldown_max_waits,
        }

    def threshold_violations(self) -> list:
        """Ordering invariants between the nested timeout windows.

        Imported lazily: ``tools/`` modules import ``config``, so a top-level
        import here would close the cycle.
        """
        from tools.config_invariants import check_threshold_invariants

        return check_threshold_invariants(self.report())


_config: Optional[RunnerConfig] = None


def get_config() -> RunnerConfig:
    global _config
    if _config is None:
        _config = RunnerConfig()
    return _config
