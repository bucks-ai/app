import type {
  ToolPermissionStatus,
  ToolSetupStatus,
} from "@/types/tool-permission-ui";

type PermissionStatusPillProps = {
  status: ToolPermissionStatus | ToolSetupStatus;
  label?: string;
  className?: string;
};

const statusClasses: Record<ToolPermissionStatus | ToolSetupStatus, string> = {
  not_connected: "border-border bg-elevated text-secondary",
  approval_requested: "border-accent/35 bg-accent/10 text-accent",
  approved: "border-success/25 bg-success/10 text-success",
  human_required: "border-warning/35 bg-warning/10 text-warning",
  approved_by_founder: "border-success/25 bg-success/10 text-success",
  connected_demo: "border-accent/35 bg-accent/10 text-accent",
  rejected: "border-error/35 bg-error/10 text-error",
  blocked: "border-error/35 bg-error/10 text-error",
};

function formatStatus(status: ToolPermissionStatus | ToolSetupStatus) {
  return status
    .split("_")
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

export function PermissionStatusPill({
  status,
  label,
  className = "",
}: PermissionStatusPillProps) {
  return (
    <span
      className={`inline-flex w-fit max-w-full items-center rounded-md border px-2.5 py-1 font-mono text-[11px] font-medium uppercase tracking-[0.18em] ${statusClasses[status]} ${className}`}
    >
      <span className="truncate">{label ?? formatStatus(status)}</span>
    </span>
  );
}
