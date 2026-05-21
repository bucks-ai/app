export type ExecutionPhase =
  | "intake"
  | "blueprint"
  | "permissions"
  | "repository"
  | "scaffold"
  | "deployment"
  | "validation"
  | "operating";

export type ExecutionMilestoneStatus =
  | "complete"
  | "in_progress"
  | "blocked"
  | "not_started"
  | "warning";

export interface ExecutionMilestone {
  id: string;
  label: string;
  description: string;
  status: ExecutionMilestoneStatus;
  completedAt?: string;
  blockedReason?: string;
  metadata?: Record<string, unknown>;
}

export interface ExecutionTimelineEvent {
  id: string;
  activityType: string;
  message: string;
  createdAt: string;
  status: string;
  metadata: Record<string, unknown>;
  category:
    | "blueprint"
    | "permissions"
    | "github"
    | "vercel"
    | "human"
    | "validation"
    | "system"
    | "other";
}

export interface ExecutionBlocker {
  id: string;
  type: string;
  label: string;
  description: string;
  severity: "high" | "medium" | "low";
  recommendedAction: string;
  relatedToolId?: string;
}

export interface ExecutionNextAction {
  id: string;
  label: string;
  description: string;
  actor: "founder" | "bucks_ai";
  priority: "high" | "medium" | "low";
  href?: string;
  actionType?: string;
}

export interface ExecutionAsset {
  id: string;
  type:
    | "github_repo"
    | "vercel_project"
    | "deployment"
    | "blueprint"
    | "tool_permission";
  label: string;
  url?: string;
  status: string;
  metadata?: Record<string, unknown>;
}

export interface BusinessExecutionStatus {
  businessId: string;
  businessName: string;
  currentPhase: ExecutionPhase;
  health: "ready" | "blocked" | "in_progress" | "needs_attention";
  progressPercent: number;
  milestones: ExecutionMilestone[];
  timeline: ExecutionTimelineEvent[];
  blockers: ExecutionBlocker[];
  nextActions: ExecutionNextAction[];
  assets: ExecutionAsset[];
  generatedAt: string;
}
