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
    tone: "border-accent/45 text-accent hover:border-accent-hover hover:text-foreground",
  },
  {
    action: "approve",
    label: "Approve",
    tone: "border-success/35 text-success hover:border-success/70 hover:text-foreground",
  },
  {
    action: "mark_human_required",
    label: "Mark human-required",
    tone: "border-warning/45 text-warning hover:border-warning/70 hover:text-foreground",
  },
  {
    action: "mark_demo_connected",
    label: "Mark demo connected",
    tone: "border-border text-secondary hover:border-accent/60 hover:text-foreground",
  },
  {
    action: "reject",
    label: "Reject",
    tone: "border-error/45 text-error hover:border-error/70 hover:text-foreground",
  },
  {
    action: "reset",
    label: "Reset",
    tone: "border-border text-secondary hover:border-secondary/60 hover:text-foreground",
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
            className={`min-h-10 rounded-md border bg-background px-3 py-2 text-left text-xs font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-45 ${tone} ${
              active ? "bg-elevated" : ""
            }`}
          >
            {isBusy ? "Updating..." : label}
          </button>
        );
      })}
    </div>
  );
}
