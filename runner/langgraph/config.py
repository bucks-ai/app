"""Configuration loader for bucks.ai Autonomous Development Runner."""
import os
from pathlib import Path
from dataclasses import dataclass, field
from typing import Optional

from dotenv import load_dotenv

_env_path = Path(__file__).parent / ".env"
load_dotenv(_env_path, override=False)


@dataclass
class RunnerConfig:
    openai_api_key: Optional[str] = field(default_factory=lambda: os.getenv("OPENAI_API_KEY"))
    anthropic_api_key: Optional[str] = field(default_factory=lambda: os.getenv("ANTHROPIC_API_KEY"))
    github_token: Optional[str] = field(default_factory=lambda: os.getenv("GITHUB_TOKEN"))
    supabase_url: Optional[str] = field(default_factory=lambda: os.getenv("SUPABASE_URL"))
    supabase_service_role_key: Optional[str] = field(
        default_factory=lambda: os.getenv("SUPABASE_SERVICE_ROLE_KEY")
    )
    vercel_token: Optional[str] = field(default_factory=lambda: os.getenv("VERCEL_TOKEN"))
    vercel_project_id: Optional[str] = field(
        default_factory=lambda: os.getenv("VERCEL_PROJECT_ID")
    )
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

    def report(self) -> dict:
        return {
            "openai": self.has_openai,
            "anthropic": self.has_anthropic,
            "github": self.has_github,
            "supabase": self.has_supabase,
            "vercel": self.has_vercel,
            "vercel_project_id": self.vercel_project_id,
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
        }


_config: Optional[RunnerConfig] = None


def get_config() -> RunnerConfig:
    global _config
    if _config is None:
        _config = RunnerConfig()
    return _config
