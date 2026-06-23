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
    api_cost: Optional[float] = None
    tokens_used: Optional[int] = None


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
    consecutive_failures: int = 0
    started_at: Optional[str] = None
    updated_at: Optional[str] = None
    error: Optional[str] = None

    # LangGraph state carries full runtime context
    current_task: Optional[dict] = None
    worker_result: Optional[dict] = None
    worker_summary: Optional[dict] = None
    worker_summary_digest: Optional[str] = None
    context_compression: Optional[dict] = None
    check_passed: Optional[bool] = None
    deploy_result: Optional[dict] = None
    deploy_ready: Optional[bool] = None
    rollback_revert_status: Optional[str] = None
    rollback_revert_plan: Optional[dict] = None
    sql_scan: Optional[dict] = None
    sql_approval_status: Optional[str] = None  # pending | approved | rejected | None
    resource_request_status: Optional[str] = None  # pending | fulfilled | None
    retry_pending: Optional[bool] = None  # a failed task was requeued for retry this loop
    error_history: list[dict] = Field(default_factory=list)  # recent {error, task_id} records
    task_attempt_counts: dict = Field(default_factory=dict)   # task_id → run count this session
    worker_elapsed_seconds: Optional[float] = None  # wall-clock seconds of the last dispatch
    worker_timeout_count: int = 0                   # cumulative timeouts this session
    codex_usage_limit_count: int = 0               # cumulative Codex usage-limit errors this session
    session_cost: float = 0.0                       # cumulative API cost ($) this session
    messages: list[dict] = Field(default_factory=list)
    stop_reason: Optional[str] = None
    strategic_gate_status: Optional[str] = None     # pending | None
    strategic_tasks_since_gate: int = 0             # task loops since last strategic gate
    strategic_gate_at_loop: Optional[int] = None    # loop_count when the gate last triggered
    resolved_model: Optional[str] = None            # model resolved by model_routing_policy
    mission_name: Optional[str] = None              # name of the compiled mission, if any
    mission_compiled: Optional[bool] = None         # True when a mission was compiled this session
    acceptance_criteria_status: Optional[str] = None  # passed | warned | failed | None
    definition_of_done_status: Optional[str] = None  # passed | warned | failed | None
    code_review_status: Optional[str] = None  # passed | warned | failed | None
    high_risk_review_status: Optional[str] = None  # passed | warned | skipped | failed | None
    codex_escalation_status: Optional[str] = None  # attempted | succeeded | failed | skipped | None
    auto_repair_attempt: int = 0                   # repair attempts made this task loop
    auto_repair_status: Optional[str] = None       # attempted | succeeded | failed | None
    check_output: Optional[str] = None             # last check.sh stdout (used by auto_repair_if_needed)
    merge_approval_status: Optional[str] = None   # approved | pending | skipped | None
    merge_risk_level: Optional[str] = None         # low | medium | high | None
    e2e_result: Optional[dict] = None              # result dict from playwright_harness.run_e2e_suite
    ui_flow_result: Optional[dict] = None          # result dict from ui_flow_validator.run_ui_flow_validation
    product_eval_result: Optional[dict] = None     # result dict from product_eval_harness.run_product_eval_suite
    launch_readiness_result: Optional[dict] = None  # result dict from launch_readiness_scorecard
    last_task_completed_at: Optional[str] = None    # ISO-8601 UTC timestamp of the last completed task loop
    stale_run_warning_sent: bool = False             # True once the stale-run Slack warning has fired this episode
    live_batch_validation_result: Optional[dict] = None  # result dict from live_batch_validation_report
