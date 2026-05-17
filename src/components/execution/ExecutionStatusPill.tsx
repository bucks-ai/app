import { StatusPill } from "@/components/ui/StatusPill";
import type { ExecutionHealth, ExecutionMilestoneStatus } from "@/types/execution-ui";

type ExecutionStatusPillProps = {
  label: string;
  status?:
    | ExecutionHealth
    | ExecutionMilestoneStatus
    | "founder"
    | "bucks_ai"
    | "warning"
    | "critical"
    | "success";
};

function variantForStatus(status: ExecutionStatusPillProps["status"]) {
  if (status === "complete" || status === "success") return "success";
  if (status === "blocked" || status === "critical") return "danger";
  if (
    status === "needs_attention" ||
    status === "warning" ||
    status === "founder" ||
    status === "in_progress"
  ) {
    return "warning";
  }
  if (status === "on_track" || status === "bucks_ai") return "accent";
  return "neutral";
}

export function ExecutionStatusPill({ label, status }: ExecutionStatusPillProps) {
  return <StatusPill label={label} variant={variantForStatus(status)} />;
}
