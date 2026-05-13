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
  not_connected: "border-[#1C1C1C] bg-[#141414] text-[#888888]",
  approval_requested: "border-[#4F46E5]/35 bg-[#4F46E5]/10 text-[#A5B4FC]",
  approved: "border-[#22C55E]/25 bg-[#22C55E]/10 text-[#86EFAC]",
  human_required: "border-[#F59E0B]/35 bg-[#F59E0B]/10 text-[#FCD34D]",
  approved_by_founder: "border-[#22C55E]/25 bg-[#22C55E]/10 text-[#86EFAC]",
  connected_demo: "border-[#4F46E5]/35 bg-[#4F46E5]/10 text-[#A5B4FC]",
  rejected: "border-[#EF4444]/35 bg-[#EF4444]/10 text-[#FCA5A5]",
  blocked: "border-[#EF4444]/35 bg-[#EF4444]/10 text-[#FCA5A5]",
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
