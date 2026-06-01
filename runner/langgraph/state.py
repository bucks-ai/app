"""State models for bucks.ai Autonomous Development Runner."""
from typing import Any, Optional
from datetime import datetime
from pydantic import BaseModel, Field


class RunnerTask(BaseModel):
    id: str
    title: str
    type: str = "general"
    preferred_worker: Optional[str] = None
    branch: Optional[str] = None
    status: str = "queued"
    summary: Optional[str] = None
    error: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class WorkerResult(BaseModel):
    worker: str
    mode: str
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    prompt_written: bool = False
    prompt_path: Optional[str] = None
    response_path: Optional[str] = None


class ToolResult(BaseModel):
    tool: str
    success: bool
    output: Optional[str] = None
    error: Optional[str] = None
    data: Optional[dict] = None


class SqlScanResult(BaseModel):
    ok: bool
    warnings: list[str] = Field(default_factory=list)
    blocked_terms: list[str] = Field(default_factory=list)


class RunnerEvent(BaseModel):
    event_type: str
    timestamp: str = Field(default_factory=lambda: datetime.utcnow().isoformat())
    task_id: Optional[str] = None
    payload: dict = Field(default_factory=dict)


class RunnerState(BaseModel):
    status: str = "idle"
    current_task_id: Optional[str] = None
    current_worker: Optional[str] = None
    current_branch: Optional[str] = None
    last_completed_step: Optional[str] = None
    last_commit: Optional[str] = None
    loop_count: int = 0
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    error: Optional[str] = None

    # LangGraph state carries full runtime context
    current_task: Optional[dict] = None
    worker_result: Optional[dict] = None
    worker_summary: Optional[dict] = None
    check_passed: Optional[bool] = None
    sql_scan: Optional[dict] = None
    messages: list[dict] = Field(default_factory=list)
    stop_reason: Optional[str] = None
