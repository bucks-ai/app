import type { AgentAutonomyLevel, AgentRiskLevel, AgentStatus } from "@/types/agents";
import type { AgentRunStatus } from "@/types/agent-runs";
import { humanizeAgentValue } from "@/components/agents/agent-view-model";

type BadgeKind = "status" | "run" | "risk" | "autonomy";

type AgentStatusBadgeProps = {
  kind?: BadgeKind;
  value: AgentStatus | AgentRunStatus | AgentRiskLevel | AgentAutonomyLevel;
};

function badgeStyles(kind: BadgeKind, value: string) {
  if (kind === "run") {
    switch (value) {
      case "completed":
        return "border-success/20 bg-success/6 text-success";
      case "failed":
        return "border-error/30 bg-error/10 text-error";
      case "blocked":
      case "waiting_for_approval":
        return "border-warning/30 bg-warning/10 text-warning";
      case "running":
        return "border-accent/35 bg-accent/12 text-accent";
      case "queued":
        return "border-border bg-background text-secondary";
      case "skipped":
        return "border-warning/25 bg-warning/8 text-warning";
      default:
        return "border-border bg-background text-secondary";
    }
  }

  if (kind === "risk") {
    if (value === "high" || value === "human_controlled") {
      return "border-error/30 bg-error/10 text-error";
    }
    if (value === "medium") {
      return "border-warning/30 bg-warning/10 text-warning";
    }
    return "border-success/25 bg-success/8 text-success";
  }

  if (kind === "autonomy") {
    if (value.includes("execute")) {
      return "border-warning/30 bg-warning/10 text-warning";
    }
    if (value === "draft" || value === "suggest") {
      return "border-accent/30 bg-accent/10 text-accent";
    }
    return "border-border bg-background text-secondary";
  }

  switch (value) {
    case "completed":
      return "border-success/25 bg-success/8 text-success";
    case "active":
    case "running":
      return "border-accent/35 bg-accent/12 text-accent";
    case "ready":
    case "queued":
      return "border-accent/25 bg-accent/8 text-accent";
    case "monitoring":
      return "border-success/25 bg-success/8 text-success";
    case "blocked":
    case "failed":
      return "border-error/30 bg-error/10 text-error";
    case "waiting_for_approval":
    case "skipped":
      return "border-warning/30 bg-warning/10 text-warning";
    default:
      return "border-border bg-background text-secondary";
  }
}

export function AgentStatusBadge({ kind = "status", value }: AgentStatusBadgeProps) {
  return (
    <span
      className={`inline-flex max-w-full items-center rounded border px-2 py-1 font-mono text-[10px] uppercase tracking-widest ${badgeStyles(kind, value)}`}
    >
      <span className="truncate">{humanizeAgentValue(value)}</span>
    </span>
  );
}
