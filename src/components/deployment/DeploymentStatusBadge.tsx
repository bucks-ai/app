import { StatusPill } from "@/components/ui/StatusPill";
import type { DeploymentStatus } from "@/types/deployment-ui";

type DeploymentStatusBadgeProps = {
  status: DeploymentStatus;
};

export function deploymentStatusLabel(status: DeploymentStatus) {
  if (status === "no_project" || status === "not_deployed") return "Not deployed";
  if (status === "queued") return "Queued";
  if (status === "building") return "Building";
  if (status === "ready" || status === "live") return "Live";
  if (status === "failed") return "Failed";
  if (status === "manual_action_required") return "Manual action needed";
  return "Unknown";
}

export function deploymentStatusVariant(status: DeploymentStatus) {
  if (status === "ready" || status === "live") return "success" as const;
  if (status === "failed") return "danger" as const;
  if (status === "queued" || status === "manual_action_required") return "warning" as const;
  if (status === "building") return "accent" as const;
  return "neutral" as const;
}

export function DeploymentStatusBadge({ status }: DeploymentStatusBadgeProps) {
  return (
    <StatusPill
      label={deploymentStatusLabel(status)}
      variant={deploymentStatusVariant(status)}
    />
  );
}
