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
})


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
    vercel_token: Optional[str] = field(default_factory=lambda: os.getenv("VERCEL_TOKEN"))
    vercel_project_id: Optional[str] = field(
        default_factory=lambda: os.getenv("VERCEL_PROJECT_ID")
    )
    slack_webhook_url: Optional[str] = field(
        default_factory=lambda: os.getenv("SLACK_WEBHOOK_URL")
    )
    slack_notify: bool = field(
        default_factory=lambda: os.getenv("SLACK_NOTIFY", "true").lower() == "true"
    )
    slack_notify_events: frozenset = field(default_factory=_load_slack_events)
    repo_path: str = field(
        default_factory=lambda: os.getenv("BUCKS_AI_REPO_PATH", "/home/arnavt/bucks-ai")
    )
    runner_mode: str = field(
        default_factory=lambda: os.getenv("RUNNER_MODE", "browser_or_cli")
    )
    max_loop_tasks: int = field(
        default_factory=lambda: int(os.getenv("MAX_LOOP_TASKS", "10"))
    )
    max_runtime_minutes: int = field(
        default_factory=lambda: int(os.getenv("MAX_RUNTIME_MINUTES", "480"))
    )
    auto_merge: bool = field(
        default_factory=lambda: os.getenv("AUTO_MERGE", "true").lower() == "true"
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
    resource_gate_enabled: bool = field(
        default_factory=lambda: os.getenv("RESOURCE_GATE", "true").lower() == "true"
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
    worker_timeout_threshold: int = field(
        default_factory=lambda: int(os.getenv("WORKER_TIMEOUT_THRESHOLD", "570"))
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

    @property
    def has_openai(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_anthropic(self) -> bool:
        return bool(self.anthropic_api_key)

    @property
    def has_github(self) -> bool:
        return bool(self.github_token)

    @property
    def has_supabase(self) -> bool:
        return bool(self.supabase_url and self.supabase_service_role_key)

    @property
    def has_vercel(self) -> bool:
        return bool(self.vercel_token)

    @property
    def has_slack(self) -> bool:
        return bool(self.slack_webhook_url)

    def report(self) -> dict:
        return {
            "openai": self.has_openai,
            "anthropic": self.has_anthropic,
            "github": self.has_github,
            "github_repo": self.github_repo,
            "supabase": self.has_supabase,
            "vercel": self.has_vercel,
            "vercel_project_id": self.vercel_project_id,
            "slack": self.has_slack,
            "slack_notify": self.slack_notify,
            "repo_path": self.repo_path,
            "runner_mode": self.runner_mode,
            "max_loop_tasks": self.max_loop_tasks,
            "max_runtime_minutes": self.max_runtime_minutes,
            "auto_merge": self.auto_merge,
            "auto_deploy": self.auto_deploy,
            "auto_deploy_poll": self.auto_deploy_poll,
            "block_on_deploy_failure": self.block_on_deploy_failure,
            "vercel_poll_timeout": self.vercel_poll_timeout,
            "vercel_poll_interval": self.vercel_poll_interval,
            "auto_apply_sql": self.auto_apply_sql,
            "require_sql_approval": self.require_sql_approval,
            "resource_gate_enabled": self.resource_gate_enabled,
            "failure_guard_enabled": self.failure_guard_enabled,
            "max_task_retries": self.max_task_retries,
            "max_consecutive_failures": self.max_consecutive_failures,
            "max_repeated_errors": self.max_repeated_errors,
            "repeated_error_window": self.repeated_error_window,
            "max_task_attempts": self.max_task_attempts,
            "worker_timeout_guard_enabled": self.worker_timeout_guard_enabled,
            "max_worker_timeouts": self.max_worker_timeouts,
            "worker_timeout_threshold": self.worker_timeout_threshold,
            "cost_budget_guard_enabled": self.cost_budget_guard_enabled,
            "max_session_cost_dollars": self.max_session_cost_dollars,
            "max_task_cost_dollars": self.max_task_cost_dollars,
            "estimated_cost_per_task_dollars": self.estimated_cost_per_task_dollars,
            "strategic_gate_enabled": self.strategic_gate_enabled,
            "strategic_pause_interval": self.strategic_pause_interval,
            "codex_usage_limit_guard_enabled": self.codex_usage_limit_guard_enabled,
            "max_codex_usage_limit_errors": self.max_codex_usage_limit_errors,
        }


_config: Optional[RunnerConfig] = None


def get_config() -> RunnerConfig:
    global _config
    if _config is None:
        _config = RunnerConfig()
    return _config
