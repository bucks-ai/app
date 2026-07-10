import type { ApprovalRecord } from "@/types/database";

export type ApprovalAction = "approve" | "reject";

export type ApprovalsResponse = {
  approvals: ApprovalRecord[];
};

export type UpdateApprovalResponse = ApprovalRecord;
