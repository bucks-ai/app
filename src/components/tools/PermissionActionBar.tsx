"use client";

import type {
  ToolPermissionAction,
  ToolPermissionStatus,
} from "@/types/tool-permission-ui";

type PermissionActionBarProps = {
  status: ToolPermissionStatus;
  disabled?: boolean;
  busyAction?: ToolPermissionAction | null;
  onAction: (action: ToolPermissionAction) => void;
};

const actions: { action: ToolPermissionAction; label: string; tone: string }[] = [
  {
    action: "request_approval",
    label: "Request approval",
    tone: "border-[#4F46E5]/45 text-[#C7D2FE] hover:border-[#6366F1] hover:text-[#F0F0F0]",
  },
  {
    action: "approve",
    label: "Approve",
    tone: "border-[#22C55E]/35 text-[#BBF7D0] hover:border-[#22C55E]/70 hover:text-[#F0F0F0]",
  },
  {
    action: "mark_human_required",
    label: "Mark human-required",
    tone: "border-[#F59E0B]/45 text-[#FDE68A] hover:border-[#F59E0B]/70 hover:text-[#F0F0F0]",
  },
  {
    action: "mark_demo_connected",
    label: "Mark demo connected",
    tone: "border-[#1C1C1C] text-[#D4D4D4] hover:border-[#4F46E5]/60 hover:text-[#F0F0F0]",
  },
  {
    action: "reject",
    label: "Reject",
    tone: "border-[#EF4444]/45 text-[#FCA5A5] hover:border-[#EF4444]/70 hover:text-[#F0F0F0]",
  },
  {
    action: "reset",
    label: "Reset",
    tone: "border-[#1C1C1C] text-[#888888] hover:border-[#888888]/60 hover:text-[#F0F0F0]",
  },
];

function isActionActive(status: ToolPermissionStatus, action: ToolPermissionAction) {
  if (status === "approval_requested" && action === "request_approval") return true;
  if (
    (status === "approved" || status === "approved_by_founder") &&
    action === "approve"
  ) {
    return true;
  }
  if (status === "human_required" && action === "mark_human_required") return true;
  if (status === "connected_demo" && action === "mark_demo_connected") return true;
  if (status === "rejected" && action === "reject") return true;
  if (status === "not_connected" && action === "reset") return true;
  return false;
}

export function PermissionActionBar({
  status,
  disabled = false,
  busyAction = null,
  onAction,
}: PermissionActionBarProps) {
  return (
    <div className="flex flex-wrap gap-2">
      {actions.map(({ action, label, tone }) => {
        const active = isActionActive(status, action);
        const isBusy = busyAction === action;

        return (
          <button
            key={action}
            type="button"
            disabled={disabled || !!busyAction}
            onClick={() => onAction(action)}
            className={`min-h-10 rounded-md border bg-[#080808] px-3 py-2 text-left text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-45 ${tone} ${
              active ? "bg-[#141414]" : ""
            }`}
          >
            {isBusy ? "Updating..." : label}
          </button>
        );
      })}
    </div>
  );
}
