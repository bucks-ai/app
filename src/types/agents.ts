// Agent Registry v1 — TypeScript types.
// Node = broad company/system function.
// Agent = specialist worker inside a node.
//
// This module is the type foundation for bucks.ai's operating team registry.
// Future tasks (Agent Runs v1, Operating Team UI) will extend from here.

// ---------------------------------------------------------------------------
// Node and agent IDs
// ---------------------------------------------------------------------------

export type AgentNodeId =
  | "strategy"
  | "deployment"
  | "validation"
  | "research"
  | "safety"
  | "orchestration";

export type AgentTemplateId =
  // Strategy Node
  | "idea_intake"
  | "blueprint"
  | "opportunity_framing"
  // Deployment Node
  | "repository"
  | "scaffold"
  | "deployment_status"
  // Validation Node
  | "persona"
  | "hypothesis"
  | "feedback_analysis"
  // Research Node
  | "market_research"
  | "customer_segment"
  | "competitor"
  | "monetization"
  | "distribution"
  | "risk"
  | "opportunity_scoring"
  // Safety / Permissions Node
  | "tool_permission"
  | "risk_review"
  // Orchestration Node
  | "task_router"
  | "next_action"
  | "run_monitor";

// ---------------------------------------------------------------------------
// Status / risk / autonomy enums
// ---------------------------------------------------------------------------

export type AgentStatus =
  | "unavailable"
  | "ready"
  | "active"
  | "blocked"
  | "waiting_for_approval"
  | "completed"
  | "monitoring";

export type AgentRiskLevel = "low" | "medium" | "high" | "human_controlled";

export type AgentAutonomyLevel =
  | "observe"
  | "suggest"
  | "draft"
  | "execute_with_approval"
  | "execute_when_approved";

// ---------------------------------------------------------------------------
// Tool access
// ---------------------------------------------------------------------------

export type AgentToolCategory =
  | "blueprint_read"
  | "blueprint_write"
  | "validation_read"
  | "validation_write"
  | "research_read"
  | "research_write"
  | "github_read"
  | "github_write"
  | "vercel_read"
  | "vercel_write"
  | "tool_permission_read"
  | "tool_permission_write"
  | "activity_log_read"
  | "activity_log_write"
  | "human_action_read"
  | "human_action_write"
  | "external_web"
  | "outreach"
  | "llm_generate";

export interface AgentToolAccess {
  allowed: AgentToolCategory[];
  blocked: AgentToolCategory[];
}

// ---------------------------------------------------------------------------
// Capabilities and approval requirements
// ---------------------------------------------------------------------------

export interface AgentCapability {
  id: string;
  label: string;
  description: string;
}

export interface AgentApprovalRequirement {
  action: string;
  reason: string;
  approver: "founder" | "bucks_ai_operator" | "system";
}

// ---------------------------------------------------------------------------
// Agent template (static definition)
// ---------------------------------------------------------------------------

export interface AgentTemplate {
  id: AgentTemplateId;
  name: string;
  node: AgentNodeId;
  description: string;
  purpose: string;
  capabilities: AgentCapability[];
  toolAccess: AgentToolAccess;
  approvalRequirements: AgentApprovalRequirement[];
  riskLevel: AgentRiskLevel;
  autonomyLevel: AgentAutonomyLevel;
  /** The MVP feature or workflow that currently backs this agent. Null if not yet backed. */
  mvpBackingFeature: string | null;
}

// ---------------------------------------------------------------------------
// Business-aware agent status (resolved at runtime per business)
// ---------------------------------------------------------------------------

export interface AgentBusinessStatus {
  agentId: AgentTemplateId;
  status: AgentStatus;
  statusReason: string;
  lastActivityAt: string | null;
  completedAt: string | null;
}

// ---------------------------------------------------------------------------
// Composed registry views
// ---------------------------------------------------------------------------

export interface AgentRegistryEntry {
  template: AgentTemplate;
  businessStatus: AgentBusinessStatus;
}

export interface AgentNodeSummary {
  nodeId: AgentNodeId;
  nodeLabel: string;
  nodeDescription: string;
  agents: AgentRegistryEntry[];
  activeCount: number;
  completedCount: number;
  blockedCount: number;
  readyCount: number;
  monitoringCount: number;
}

export interface AgentRegistrySummary {
  businessId: string;
  totalAgents: number;
  activeCount: number;
  completedCount: number;
  blockedCount: number;
  readyCount: number;
  monitoringCount: number;
  unavailableCount: number;
  waitingCount: number;
  generatedAt: string;
}

export interface AgentRegistryView {
  summary: AgentRegistrySummary;
  nodes: AgentNodeSummary[];
  agents: AgentRegistryEntry[];
}
