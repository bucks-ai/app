export type ExecutionPhase =
  | "idea_captured"
  | "blueprint"
  | "permissions"
  | "github"
  | "scaffold"
  | "vercel"
  | "deployment"
  | "validation"
  | "blocked"
  | "completed";

export type ExecutionHealth = "on_track" | "needs_attention" | "blocked" | "complete";

export type ExecutionMilestoneStatus =
  | "pending"
  | "in_progress"
  | "complete"
  | "blocked"
  | "skipped";

export type ExecutionMilestone = {
  id: ExecutionPhase;
  label: string;
  status: ExecutionMilestoneStatus;
  description?: string | null;
  completedAt?: string | null;
  href?: string | null;
};

export type ExecutionTimelineEvent = {
  id: string;
  category: string;
  title: string;
  message?: string | null;
  actor?: string | null;
  status?: string | null;
  createdAt: string;
  metadata?: Record<string, unknown> | null;
};

export type ExecutionBlocker = {
  id: string;
  title: string;
  description?: string | null;
  severity: "warning" | "blocked" | "critical";
  owner: "founder" | "bucks_ai";
  href?: string | null;
};

export type ExecutionNextAction = {
  id: string;
  title: string;
  description?: string | null;
  actor: "founder" | "bucks_ai";
  href?: string | null;
  priority?: "low" | "medium" | "high";
};

export type ExecutionAsset = {
  id: string;
  label: string;
  type:
    | "github_repo"
    | "vercel_project"
    | "deployment_url"
    | "blueprint"
    | "tool_permissions"
    | "other";
  url?: string | null;
  status?: string | null;
  description?: string | null;
};

export type BusinessExecutionStatus = {
  businessId: string;
  currentPhase: ExecutionPhase;
  health: ExecutionHealth;
  progressPercent: number;
  milestones: ExecutionMilestone[];
  blockers: ExecutionBlocker[];
  nextActions: ExecutionNextAction[];
  assets: ExecutionAsset[];
  timeline: ExecutionTimelineEvent[];
  updatedAt?: string | null;
};

export type ExecutionStatusResponse =
  | {
      ok: true;
      data: BusinessExecutionStatus;
      warning?: string;
    }
  | {
      ok: false;
      code: string;
      error: string;
    };

export type ExecutionTimelineResponse =
  | {
      ok: true;
      data: ExecutionTimelineEvent[];
      warning?: string;
    }
  | {
      ok: false;
      code: string;
      error: string;
    };
