// Agent Runs v1 — TypeScript types.
// An agent run is a durable record of a single unit of work performed
// (or inferred to have been performed) by a bucks.ai agent for a business.
//
// Agent runs are the history layer on top of Agent Registry v1.
// Future tasks (Operating Team UI, retry engine, evaluator layer) extend from here.

import type { AgentTemplateId, AgentNodeId } from "@/types/agents";

// ---------------------------------------------------------------------------
// Status
// ---------------------------------------------------------------------------

export type AgentRunStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "blocked"
  | "skipped"
  | "waiting_for_approval";

// ---------------------------------------------------------------------------
// Source — how the run record came to exist
// ---------------------------------------------------------------------------

export type AgentRunSource =
  | "system_inferred"        // inferred from live system state
  | "user_triggered"         // founder explicitly triggered
  | "activity_log_backfill"  // back-filled from agent_activity_logs
  | "workflow"               // created by a workflow engine (future)
  | "manual_note";           // manually recorded by operator

// ---------------------------------------------------------------------------
// Trigger — what event caused the run
// ---------------------------------------------------------------------------

export type AgentRunTrigger =
  | "blueprint_generated"
  | "repo_created"
  | "scaffold_prepared"
  | "vercel_project_created"
  | "deployment_status_refreshed"
  | "validation_workspace_seeded"
  | "research_workspace_generated"
  | "tool_permission_approved"
  | "next_action_resolved"
  | "manual";

// ---------------------------------------------------------------------------
// Outcome — higher-level result classification
// ---------------------------------------------------------------------------

export type AgentRunOutcome =
  | "success"
  | "partial_success"
  | "failure"
  | "skipped"
  | "needs_review";

// ---------------------------------------------------------------------------
// Artifact — a file, URL, or object produced by the run
// ---------------------------------------------------------------------------

export interface AgentRunArtifact {
  type: string;         // e.g. "github_repo", "vercel_project", "blueprint"
  label: string;
  url?: string;
  metadata?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Error — structured error info attached to a failed run
// ---------------------------------------------------------------------------

export interface AgentRunError {
  code: string;
  message: string;
  detail?: string;
  retriable?: boolean;
}

// ---------------------------------------------------------------------------
// Core record — mirrors the agent_runs table
// ---------------------------------------------------------------------------

export interface AgentRunRecord {
  id: string;
  business_id: string;
  user_id: string;
  agent_id: AgentTemplateId;
  node_id: AgentNodeId;
  title: string;
  summary: string | null;
  status: AgentRunStatus;
  source: AgentRunSource;
  trigger: AgentRunTrigger | null;
  input: Record<string, unknown>;
  output: Record<string, unknown>;
  artifacts: AgentRunArtifact[];
  error: AgentRunError | null;
  related_activity_log_ids: string[];
  started_at: string | null;
  completed_at: string | null;
  created_at: string;
  updated_at: string;
}

// ---------------------------------------------------------------------------
// Summary — aggregate view of all runs for a business
// ---------------------------------------------------------------------------

export interface AgentRunSummary {
  businessId: string;
  totalRuns: number;
  completedRuns: number;
  failedRuns: number;
  runningRuns: number;
  blockedRuns: number;
  waitingRuns: number;
  lastRunAt: string | null;
  agentsCovered: AgentTemplateId[];
  generatedAt: string;
}

// ---------------------------------------------------------------------------
// Timeline item — lightweight view for a run history list
// ---------------------------------------------------------------------------

export interface AgentRunTimelineItem {
  id: string;
  agentId: AgentTemplateId;
  nodeId: AgentNodeId;
  title: string;
  status: AgentRunStatus;
  source: AgentRunSource;
  trigger: AgentRunTrigger | null;
  startedAt: string | null;
  completedAt: string | null;
  createdAt: string;
  hasSummary: boolean;
  hasError: boolean;
}

// ---------------------------------------------------------------------------
// Create / update inputs
// ---------------------------------------------------------------------------

export interface AgentRunCreateInput {
  business_id: string;
  user_id: string;
  agent_id: AgentTemplateId;
  node_id: AgentNodeId;
  title: string;
  summary?: string | null;
  status?: AgentRunStatus;
  source: AgentRunSource;
  trigger?: AgentRunTrigger | null;
  input?: Record<string, unknown>;
  output?: Record<string, unknown>;
  artifacts?: AgentRunArtifact[];
  error?: AgentRunError | null;
  related_activity_log_ids?: string[];
  started_at?: string | null;
  completed_at?: string | null;
}

export interface AgentRunUpdateInput {
  id: string;
  title?: string;
  summary?: string | null;
  status?: AgentRunStatus;
  output?: Record<string, unknown>;
  artifacts?: AgentRunArtifact[];
  error?: AgentRunError | null;
  related_activity_log_ids?: string[];
  started_at?: string | null;
  completed_at?: string | null;
}

// ---------------------------------------------------------------------------
// API response shapes
// ---------------------------------------------------------------------------

export interface AgentRunListResponse {
  summary: AgentRunSummary;
  runs: AgentRunRecord[];
}
