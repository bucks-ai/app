import type { RiskLevel, ToolCategory } from "@/types/tools";

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
  | "not_connected"
  | "approval_requested"
  | "approved"
  | "human_required"
  | "approved_by_founder"
  | "connected_demo"
  | "rejected"
  | "blocked";

export type ToolPermissionAction =
  | "request_approval"
  | "approve"
  | "mark_human_required"
  | "mark_demo_connected"
  | "reject"
  | "reset";

export type ToolPermissionView = {
  id: string;
  businessId: string | null;
  toolId: string;
  toolName: string;
  category?: ToolCategory;
  purpose: string;
  typicalUse?: string;
  riskLevel: Lowercase<RiskLevel>;
  status: ToolPermissionStatus;
  setupStatus: ToolSetupStatus;
  permissions: string[];
  humanOnlyReasons: string[];
  requiresTermsAcceptance?: boolean;
  requiresIdentityVerification?: boolean;
  requiresPaymentSetup?: boolean;
  canAiSetupFully?: boolean;
  updatedAt?: string;
};

export type BusinessPermissionOption = {
  id: string;
  name: string;
  status?: string;
  createdLabel?: string;
};

export type ToolPermissionsResponse = {
  permissions: ToolPermissionView[];
};

export type SeedToolPermissionsResponse = {
  permissions: ToolPermissionView[];
};

export type UpdateToolPermissionResponse = {
  permission: ToolPermissionView;
};
