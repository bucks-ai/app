// Types for the Tool Permission Setup Flow.
// Status values map directly to the tool_permissions table columns.

import type { ToolPermissionRecord } from "@/types/database";

// ---------------------------------------------------------------------------
// Status enums
// ---------------------------------------------------------------------------

export type ToolPermissionStatus =
  | "not_connected"
  | "approval_requested"
  | "approved"
  | "human_required"
  | "approved_by_founder"
  | "connected_demo"
  | "rejected"
  | "blocked";

export type ToolSetupStatus =
  | "not_started"
  | "awaiting_founder_approval"
  | "awaiting_human_legal_step"
  | "awaiting_identity_or_payment"
  | "ready_to_connect"
  | "connected_demo"
  | "rejected"
  | "blocked";

// ---------------------------------------------------------------------------
// Actions — the allowed state transitions
// ---------------------------------------------------------------------------

export type ToolPermissionAction =
  | "request_approval"
  | "approve"
  | "mark_human_required"
  | "mark_connected_demo"
  | "reject"
  | "block"
  | "reset";

// ---------------------------------------------------------------------------
// Action → status mapping
// ---------------------------------------------------------------------------

export const ACTION_STATUS_MAP: Record<
  ToolPermissionAction,
  { status: ToolPermissionStatus; setup_status: ToolSetupStatus }
> = {
  request_approval: {
    status: "approval_requested",
    setup_status: "awaiting_founder_approval",
  },
  approve: {
    status: "approved",
    setup_status: "ready_to_connect",
  },
  mark_human_required: {
    status: "human_required",
    setup_status: "awaiting_human_legal_step",
  },
  mark_connected_demo: {
    status: "connected_demo",
    setup_status: "connected_demo",
  },
  reject: {
    status: "rejected",
    setup_status: "rejected",
  },
  block: {
    status: "blocked",
    setup_status: "blocked",
  },
  reset: {
    status: "not_connected",
    setup_status: "not_started",
  },
};

// ---------------------------------------------------------------------------
// View / response shapes
// ---------------------------------------------------------------------------

export type ToolPermissionView = ToolPermissionRecord & {
  status: ToolPermissionStatus;
  setup_status: ToolSetupStatus;
};

// ---------------------------------------------------------------------------
// Input types
// ---------------------------------------------------------------------------

export interface ToolPermissionUpdateInput {
  id: string;
  action: ToolPermissionAction;
  userId: string;
}

// ---------------------------------------------------------------------------
// Seed result
// ---------------------------------------------------------------------------

export interface ToolPermissionSeedResult {
  seeded: number;
  skipped: number;
  records: ToolPermissionView[];
}
