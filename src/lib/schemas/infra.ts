// Zod schemas for the agents and infrastructure mutating routes:
// src/app/api/businesses/[id]/agent-runs/infer, src/app/api/businesses/[id]/execute,
// src/app/api/github/**, src/app/api/vercel/**, src/app/api/tool-permissions/**,
// src/app/api/approvals/**.

import { z } from "zod";

const requiredBusinessId = z.string().trim().min(1, "businessId is required.");

// ---------------------------------------------------------------------------
// POST /api/businesses/[id]/agent-runs/infer
// This route takes no JSON body; the business id arrives via the path param,
// so that's what gets validated here.
// ---------------------------------------------------------------------------

export const agentRunsInferParamsSchema = z.object({
  id: requiredBusinessId,
});

export type AgentRunsInferParams = z.infer<typeof agentRunsInferParamsSchema>;

// ---------------------------------------------------------------------------
// POST /api/github/create-repo
// ---------------------------------------------------------------------------

export const createGitHubRepoBodySchema = z.object({
  businessId: requiredBusinessId,
  repoName: z.string().trim().min(1).optional(),
  visibility: z.enum(["public", "private"]).optional(),
  includeStarterFiles: z.boolean().optional(),
});

export type CreateGitHubRepoBody = z.infer<typeof createGitHubRepoBodySchema>;

// ---------------------------------------------------------------------------
// POST /api/github/prepare-next-scaffold
// ---------------------------------------------------------------------------

export const prepareNextScaffoldBodySchema = z.object({
  businessId: requiredBusinessId,
});

export type PrepareNextScaffoldBody = z.infer<typeof prepareNextScaffoldBodySchema>;

// ---------------------------------------------------------------------------
// POST /api/vercel/create-project
// ---------------------------------------------------------------------------

export const createVercelProjectBodySchema = z.object({
  businessId: requiredBusinessId,
  projectName: z.string().trim().min(1).optional(),
  prepareScaffold: z.boolean().optional(),
  createDeployment: z.boolean().optional(),
});

export type CreateVercelProjectBody = z.infer<typeof createVercelProjectBodySchema>;

// ---------------------------------------------------------------------------
// POST /api/vercel/refresh-deployment-status
// ---------------------------------------------------------------------------

export const refreshVercelDeploymentStatusBodySchema = z.object({
  businessId: requiredBusinessId,
});

export type RefreshVercelDeploymentStatusBody = z.infer<
  typeof refreshVercelDeploymentStatusBodySchema
>;

// ---------------------------------------------------------------------------
// POST /api/tool-permissions
// ---------------------------------------------------------------------------

export const seedToolPermissionsBodySchema = z.object({
  businessId: requiredBusinessId,
});

export type SeedToolPermissionsBody = z.infer<typeof seedToolPermissionsBodySchema>;

// ---------------------------------------------------------------------------
// PATCH /api/tool-permissions/[id]
// ---------------------------------------------------------------------------

export const toolPermissionActionSchema = z.enum([
  "request_approval",
  "approve",
  "mark_human_required",
  "mark_connected_demo",
  "reject",
  "block",
  "reset",
]);

export const updateToolPermissionBodySchema = z.object({
  action: toolPermissionActionSchema,
});

export type UpdateToolPermissionBody = z.infer<typeof updateToolPermissionBodySchema>;

// ---------------------------------------------------------------------------
// PATCH /api/approvals/[id]
// ---------------------------------------------------------------------------

export const approvalActionSchema = z.enum(["approve", "reject"]);

export const updateApprovalBodySchema = z.object({
  action: approvalActionSchema,
});

export type UpdateApprovalBody = z.infer<typeof updateApprovalBodySchema>;

// ---------------------------------------------------------------------------
// POST /api/businesses/[id]/execute
// This route takes no JSON body; the business id arrives via the path param.
// ---------------------------------------------------------------------------

export const executeBusinessParamsSchema = z.object({
  id: requiredBusinessId,
});

export type ExecuteBusinessParams = z.infer<typeof executeBusinessParamsSchema>;

// ---------------------------------------------------------------------------
// GET/PATCH /api/businesses/[id]/sandbox
// ---------------------------------------------------------------------------

export const businessSandboxParamsSchema = z.object({
  id: requiredBusinessId,
});

export type BusinessSandboxParams = z.infer<typeof businessSandboxParamsSchema>;

// Secret NAME / repo NAME fields only — business_sandbox never stores a
// secret value, so this schema never accepts one either. At least one field
// is required per request; partial updates are merged onto the existing row
// (src/lib/sandbox.ts::upsertSandboxConfig).
export const setBusinessSandboxBodySchema = z
  .object({
    repo_full_name: z.string().trim().min(1).max(200).optional(),
    vercel_project_id: z.string().trim().min(1).max(200).optional(),
    github_token_secret_name: z.string().trim().min(1).max(200).optional(),
    vercel_token_secret_name: z.string().trim().min(1).max(200).optional(),
  })
  .refine((body) => Object.keys(body).length > 0, {
    message: "At least one sandbox field is required.",
  });

export type SetBusinessSandboxBody = z.infer<typeof setBusinessSandboxBodySchema>;
