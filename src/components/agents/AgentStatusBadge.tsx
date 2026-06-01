import type { AgentAutonomyLevel, AgentRiskLevel, AgentStatus } from "@/types/agents";
import type { AgentRunStatus } from "@/types/agent-runs";
import { humanizeAgentValue } from "@/components/agents/agent-view-model";

type BadgeKind = "status" | "run" | "risk" | "autonomy";

type AgentStatusBadgeProps = {
  kind?: BadgeKind;
  value: AgentStatus | AgentRunStatus | AgentRiskLevel | AgentAutonomyLevel;
};

function badgeStyles(kind: BadgeKind, value: string) {
  if (kind === "risk") {
    if (value === "high" || value === "human_controlled") {
      return "border-[#EF4444]/30 bg-[#EF4444]/10 text-[#FCA5A5]";
    }
    if (value === "medium") {
      return "border-[#F59E0B]/30 bg-[#F59E0B]/10 text-[#FCD34D]";
    }
    return "border-[#22C55E]/25 bg-[#22C55E]/8 text-[#86EFAC]";
  }

  if (kind === "autonomy") {
    if (value.includes("execute")) {
      return "border-[#F59E0B]/30 bg-[#F59E0B]/10 text-[#FCD34D]";
    }
    if (value === "draft" || value === "suggest") {
      return "border-[#4F46E5]/30 bg-[#4F46E5]/10 text-[#A5B4FC]";
    }
    return "border-[#1C1C1C] bg-[#080808] text-[#888]";
  }

  switch (value) {
    case "completed":
      return "border-[#22C55E]/25 bg-[#22C55E]/8 text-[#86EFAC]";
    case "active":
    case "running":
      return "border-[#4F46E5]/35 bg-[#4F46E5]/12 text-[#C7D2FE]";
    case "ready":
    case "queued":
      return "border-[#4F46E5]/25 bg-[#4F46E5]/8 text-[#A5B4FC]";
    case "monitoring":
      return "border-[#14B8A6]/25 bg-[#14B8A6]/8 text-[#99F6E4]";
    case "blocked":
    case "failed":
      return "border-[#EF4444]/30 bg-[#EF4444]/10 text-[#FCA5A5]";
    case "waiting_for_approval":
    case "skipped":
      return "border-[#F59E0B]/30 bg-[#F59E0B]/10 text-[#FCD34D]";
    default:
      return "border-[#1C1C1C] bg-[#080808] text-[#888]";
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
