import type { ApprovalRecord } from "@/types/database";

export type ApprovalAction = "approve" | "reject";
export type ApprovalsEmptyState = "none" | "approvals_schema_missing";

export const APPROVALS_SCHEMA_SQL_FILE = "supabase/m4a-approvals-queue.sql";

export type ApprovalsResponse = {
  approvals: ApprovalRecord[];
  emptyState?: ApprovalsEmptyState;
  sqlFile?: string;
};

export type UpdateApprovalResponse = ApprovalRecord;
