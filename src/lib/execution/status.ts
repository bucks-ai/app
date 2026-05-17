import {
  getAgentActivityLogs,
  getBusinessById,
  getHumanRequiredActions,
  getLatestBlueprintForBusiness,
} from "@/lib/projects";
import { getToolPermissionsForBusiness } from "@/lib/tool-permissions";
import { getLatestGitHubRepoForBusiness } from "@/lib/github/repo-metadata";
import { getLatestVercelProjectForBusiness } from "@/lib/vercel/project-metadata";
import { categorizeActivityLog } from "@/lib/execution/log-categories";
import type {
  AgentActivityLogRecord,
  BusinessBlueprintRecord,
  BusinessRecord,
  HumanRequiredActionRecord,
} from "@/types/database";
import type { ToolPermissionView } from "@/types/tool-permissions";
import type { GitHubRepoMetadata } from "@/lib/github/repo-metadata";
import type { VercelProjectMetadata } from "@/lib/vercel/project-metadata";
import type {
  BusinessExecutionStatus,
  ExecutionAsset,
  ExecutionBlocker,
  ExecutionMilestone,
  ExecutionMilestoneStatus,
  ExecutionNextAction,
  ExecutionPhase,
  ExecutionTimelineEvent,
} from "@/types/execution";

type Result<T> =
  | { data: T; error: null }
  | { data: null; error: string };

export interface ExecutionStatusInput {
  business: BusinessRecord;
  blueprint: BusinessBlueprintRecord | null;
  humanActions: HumanRequiredActionRecord[];
  activityLogs: AgentActivityLogRecord[];
  toolPermissions: ToolPermissionView[];
  githubRepo: GitHubRepoMetadata | null;
  vercelProject: VercelProjectMetadata | null;
}

const APPROVED_PERMISSION_STATUSES = new Set([
  "approved",
  "approved_by_founder",
  "connected_demo",
]);

const OPEN_HUMAN_ACTION_STATUSES = new Set([
  "pending",
  "open",
  "required",
  "needs_review",
  "needs_approval",
]);

function ok<T>(data: T): Result<T> {
  return { data, error: null };
}

function err<T>(message: string): Result<T> {
  return { data: null, error: message };
}

function latestLog(
  logs: AgentActivityLogRecord[],
  activityType: string
): AgentActivityLogRecord | null {
  return logs.find((log) => log.activity_type === activityType) ?? null;
}

function hasLog(logs: AgentActivityLogRecord[], activityType: string): boolean {
  return latestLog(logs, activityType) !== null;
}

function findToolPermission(
  permissions: ToolPermissionView[],
  toolId: string
): ToolPermissionView | null {
  return permissions.find((permission) => permission.tool_id === toolId) ?? null;
}

function isPermissionApproved(permission: ToolPermissionView | null): boolean {
  return Boolean(permission && APPROVED_PERMISSION_STATUSES.has(permission.status));
}

function isPermissionBlocked(permission: ToolPermissionView | null): boolean {
  return Boolean(
    permission &&
      (permission.status === "blocked" ||
        permission.status === "rejected" ||
        permission.setup_status === "blocked" ||
        permission.setup_status === "rejected")
  );
}

function isHumanActionOpen(action: HumanRequiredActionRecord): boolean {
  const normalized = action.status.toLowerCase();
  if (OPEN_HUMAN_ACTION_STATUSES.has(normalized)) return true;
  return !["complete", "completed", "resolved", "done", "closed"].includes(normalized);
}

function milestone(input: ExecutionMilestone): ExecutionMilestone {
  return input;
}

function permissionMilestoneStatus(
  permission: ToolPermissionView | null
): ExecutionMilestoneStatus {
  if (!permission) return "not_started";
  if (isPermissionApproved(permission)) return "complete";
  if (isPermissionBlocked(permission)) return "blocked";
  if (permission.status === "approval_requested" || permission.status === "human_required") {
    return "blocked";
  }
  return "in_progress";
}

export async function getBusinessExecutionStatus(
  businessId: string
): Promise<Result<BusinessExecutionStatus>> {
  const businessResult = await getBusinessById(businessId);
  if (businessResult.error || !businessResult.data) {
    return err(businessResult.error ?? "Business not found.");
  }

  const [
    blueprintResult,
    humanActionsResult,
    activityLogsResult,
    toolPermissionsResult,
    githubRepoResult,
    vercelProjectResult,
  ] = await Promise.all([
    getLatestBlueprintForBusiness(businessId),
    getHumanRequiredActions(businessId),
    getAgentActivityLogs(businessId),
    getToolPermissionsForBusiness(businessId),
    getLatestGitHubRepoForBusiness(businessId),
    getLatestVercelProjectForBusiness(businessId),
  ]);

  if (humanActionsResult.error || !humanActionsResult.data) {
    return err(humanActionsResult.error ?? "Could not load human-required actions.");
  }
  if (activityLogsResult.error || !activityLogsResult.data) {
    return err(activityLogsResult.error ?? "Could not load activity logs.");
  }
  if (toolPermissionsResult.error || !toolPermissionsResult.data) {
    return err(toolPermissionsResult.error ?? "Could not load tool permissions.");
  }

  const input: ExecutionStatusInput = {
    business: businessResult.data,
    blueprint: blueprintResult.data ?? null,
    humanActions: humanActionsResult.data,
    activityLogs: activityLogsResult.data,
    toolPermissions: toolPermissionsResult.data,
    githubRepo: githubRepoResult.data ?? null,
    vercelProject: vercelProjectResult.data ?? null,
  };

  const milestones = getExecutionMilestones(input);
  const timeline = getExecutionTimelineFromLogs(input.activityLogs);
  const blockers = getExecutionBlockers(input);

  return ok({
    businessId,
    businessName: input.business.idea_name,
    currentPhase: determineCurrentPhase(milestones),
    health: determineExecutionHealth(blockers, milestones),
    progressPercent: calculateProgressPercent(milestones),
    milestones,
    timeline,
    blockers,
    nextActions: getExecutionNextActions(input),
    assets: getExecutionAssets(input),
    generatedAt: new Date().toISOString(),
  });
}

export function getExecutionMilestones(
  input: ExecutionStatusInput
): ExecutionMilestone[] {
  const {
    business,
    blueprint,
    activityLogs,
    toolPermissions,
    githubRepo,
    vercelProject,
  } = input;
  const githubPermission = findToolPermission(toolPermissions, "github");
  const vercelPermission = findToolPermission(toolPermissions, "vercel");
  const toolPermissionsSeededLog = latestLog(activityLogs, "tool_permissions_seeded");
  const scaffoldLog = latestLog(activityLogs, "github_next_scaffold_prepared");
  const hasDeploymentUrl = Boolean(vercelProject?.vercelDeploymentUrl);

  return [
    milestone({
      id: "idea_captured",
      label: "Idea captured",
      description: "The founder's business idea has been saved.",
      status: "complete",
      completedAt: business.created_at,
      metadata: { businessStatus: business.status },
    }),
    milestone({
      id: "blueprint_generated",
      label: "Blueprint generated",
      description: "A launch blueprint exists for this business.",
      status: blueprint ? "complete" : "blocked",
      completedAt: blueprint?.created_at,
      blockedReason: blueprint ? undefined : "No saved blueprint was found.",
    }),
    milestone({
      id: "tool_permissions_seeded",
      label: "Tool permissions seeded",
      description: "The permission setup queue has been created.",
      status:
        toolPermissions.length > 0 || toolPermissionsSeededLog
          ? "complete"
          : blueprint
            ? "not_started"
            : "blocked",
      completedAt: toolPermissionsSeededLog?.created_at,
      blockedReason: blueprint ? undefined : "Blueprint is required before seeding tools.",
      metadata: { permissionCount: toolPermissions.length },
    }),
    milestone({
      id: "github_approved",
      label: "GitHub approved",
      description: "The founder approved GitHub access for repository creation.",
      status: permissionMilestoneStatus(githubPermission),
      completedAt: isPermissionApproved(githubPermission)
        ? githubPermission?.updated_at
        : undefined,
      blockedReason:
        githubPermission && !isPermissionApproved(githubPermission)
          ? `GitHub permission status is ${githubPermission.status}.`
          : undefined,
      metadata: githubPermission
        ? { status: githubPermission.status, setupStatus: githubPermission.setup_status }
        : undefined,
    }),
    milestone({
      id: "github_repo_created",
      label: "GitHub repo created",
      description: "A source repository exists for the business.",
      status: githubRepo ? "complete" : isPermissionApproved(githubPermission) ? "not_started" : "blocked",
      completedAt: githubRepo?.createdAt,
      blockedReason: githubRepo
        ? undefined
        : isPermissionApproved(githubPermission)
          ? undefined
          : "GitHub must be approved before a repo can be created.",
      metadata: githubRepo
        ? {
            repoUrl: githubRepo.githubRepoUrl,
            fullName: githubRepo.githubRepoFullName,
          }
        : undefined,
    }),
    milestone({
      id: "deployable_scaffold_prepared",
      label: "Deployable scaffold prepared",
      description: "The GitHub repo has been prepared as a deployable Next.js app.",
      status: scaffoldLog ? "complete" : githubRepo ? "not_started" : "blocked",
      completedAt: scaffoldLog?.created_at,
      blockedReason: githubRepo ? undefined : "A GitHub repo is required first.",
      metadata: scaffoldLog?.metadata,
    }),
    milestone({
      id: "vercel_approved",
      label: "Vercel approved",
      description: "The founder approved Vercel access for project creation.",
      status: permissionMilestoneStatus(vercelPermission),
      completedAt: isPermissionApproved(vercelPermission)
        ? vercelPermission?.updated_at
        : undefined,
      blockedReason:
        vercelPermission && !isPermissionApproved(vercelPermission)
          ? `Vercel permission status is ${vercelPermission.status}.`
          : undefined,
      metadata: vercelPermission
        ? { status: vercelPermission.status, setupStatus: vercelPermission.setup_status }
        : undefined,
    }),
    milestone({
      id: "vercel_project_created",
      label: "Vercel project created",
      description: "A Vercel project exists and is linked to the GitHub repo.",
      status: vercelProject
        ? "complete"
        : githubRepo && isPermissionApproved(vercelPermission)
          ? "not_started"
          : "blocked",
      completedAt: vercelProject?.createdAt,
      blockedReason: vercelProject
        ? undefined
        : !githubRepo
          ? "A GitHub repo is required before creating a Vercel project."
          : isPermissionApproved(vercelPermission)
            ? undefined
            : "Vercel must be approved before project creation.",
      metadata: vercelProject
        ? {
            projectId: vercelProject.vercelProjectId,
            dashboardUrl: vercelProject.vercelDashboardUrl,
          }
        : undefined,
    }),
    milestone({
      id: "deployment_available",
      label: "Deployment available",
      description: "A live deployment URL is available for validation.",
      status: hasDeploymentUrl ? "complete" : vercelProject ? "warning" : "not_started",
      completedAt: vercelProject?.createdAt,
      blockedReason:
        vercelProject && !hasDeploymentUrl
          ? "Vercel project exists, but no deployment URL has been recorded yet."
          : undefined,
      metadata: hasDeploymentUrl
        ? { deploymentUrl: vercelProject?.vercelDeploymentUrl }
        : undefined,
    }),
    milestone({
      id: "ready_for_validation",
      label: "Ready for validation",
      description: "The founder can start validating the generated business.",
      status: hasDeploymentUrl ? "complete" : vercelProject ? "warning" : "not_started",
      completedAt: hasDeploymentUrl ? vercelProject?.createdAt : undefined,
      blockedReason: hasDeploymentUrl
        ? undefined
        : "A deployment URL should be available before customer validation.",
    }),
  ];
}

export async function getExecutionTimelineForBusiness(
  businessId: string
): Promise<Result<ExecutionTimelineEvent[]>> {
  const logsResult = await getAgentActivityLogs(businessId);
  if (logsResult.error || !logsResult.data) {
    return err(logsResult.error ?? "Could not load activity logs.");
  }

  return ok(getExecutionTimelineFromLogs(logsResult.data));
}

function getExecutionTimelineFromLogs(
  logs: AgentActivityLogRecord[]
): ExecutionTimelineEvent[] {
  return logs.map((log) => ({
    id: log.id,
    activityType: log.activity_type,
    message: log.message,
    createdAt: log.created_at,
    status: String(log.metadata?.status ?? log.metadata?.new_status ?? "logged"),
    metadata: log.metadata ?? {},
    category: categorizeActivityLog(log.activity_type),
  }));
}

export function getExecutionBlockers(input: ExecutionStatusInput): ExecutionBlocker[] {
  const blockers: ExecutionBlocker[] = [];
  const { blueprint, humanActions, toolPermissions, githubRepo, vercelProject } = input;
  const githubPermission = findToolPermission(toolPermissions, "github");
  const vercelPermission = findToolPermission(toolPermissions, "vercel");
  const openHumanActions = humanActions.filter(isHumanActionOpen);
  const blockedPermissions = toolPermissions.filter((permission) =>
    ["blocked", "rejected"].includes(permission.status)
  );

  if (!blueprint) {
    blockers.push({
      id: "no_blueprint",
      type: "blueprint",
      label: "Blueprint missing",
      description: "This business does not have a saved execution blueprint yet.",
      severity: "high",
      recommendedAction: "Generate and save a blueprint from intake.",
    });
  }

  if (githubPermission && !isPermissionApproved(githubPermission) && !githubRepo) {
    blockers.push({
      id: "github_not_approved",
      type: "permission",
      label: "GitHub not approved",
      description: `GitHub permission is ${githubPermission.status}.`,
      severity: "high",
      recommendedAction: "Approve GitHub in the tool permission queue.",
      relatedToolId: "github",
    });
  }

  if (isPermissionApproved(githubPermission) && !githubRepo) {
    blockers.push({
      id: "github_repo_missing",
      type: "repository",
      label: "GitHub repo missing",
      description: "GitHub is approved, but no repository has been created.",
      severity: "medium",
      recommendedAction: "Create the GitHub repository for this business.",
      relatedToolId: "github",
    });
  }

  if (githubRepo && vercelPermission && !isPermissionApproved(vercelPermission)) {
    blockers.push({
      id: "vercel_not_approved",
      type: "permission",
      label: "Vercel not approved",
      description: `Vercel permission is ${vercelPermission.status}.`,
      severity: "high",
      recommendedAction: "Approve Vercel in the tool permission queue.",
      relatedToolId: "vercel",
    });
  }

  if (githubRepo && isPermissionApproved(vercelPermission) && !vercelProject) {
    blockers.push({
      id: "vercel_project_missing",
      type: "deployment",
      label: "Vercel project missing",
      description: "Vercel is approved, but no project has been created.",
      severity: "medium",
      recommendedAction: "Create the Vercel project for this business.",
      relatedToolId: "vercel",
    });
  }

  if (openHumanActions.length > 0) {
    blockers.push({
      id: "human_actions_pending",
      type: "human_required_action",
      label: "Human-required actions pending",
      description: `${openHumanActions.length} founder action${openHumanActions.length === 1 ? "" : "s"} still need review.`,
      severity: "medium",
      recommendedAction: "Review and resolve the human-required action queue.",
    });
  }

  for (const permission of blockedPermissions) {
    blockers.push({
      id: `tool_permission_${permission.tool_id}_${permission.status}`,
      type: "tool_permission",
      label: `${permission.tool_name} permission ${permission.status}`,
      description: `${permission.tool_name} is marked ${permission.status}.`,
      severity: permission.risk_level === "critical" ? "high" : "medium",
      recommendedAction: `Review the ${permission.tool_name} permission decision.`,
      relatedToolId: permission.tool_id,
    });
  }

  if (vercelProject && !vercelProject.vercelDeploymentUrl) {
    blockers.push({
      id: "deployment_status_unknown",
      type: "deployment",
      label: "Deployment status unknown",
      description: "A Vercel project exists, but no deployment URL is recorded.",
      severity: "low",
      recommendedAction: "Check the Vercel project status and trigger or wait for deployment.",
      relatedToolId: "vercel",
    });
  }

  return blockers;
}

export function getExecutionNextActions(
  input: ExecutionStatusInput
): ExecutionNextAction[] {
  const { business, blueprint, humanActions, toolPermissions, githubRepo, vercelProject } = input;
  const hrefBase = `/dashboard/businesses/${business.id}`;
  const githubPermission = findToolPermission(toolPermissions, "github");
  const vercelPermission = findToolPermission(toolPermissions, "vercel");
  const openHumanActions = humanActions.filter(isHumanActionOpen);
  const actions: ExecutionNextAction[] = [];

  if (!blueprint) {
    actions.push({
      id: "generate_blueprint",
      label: "Generate blueprint",
      description: "Create and save the launch blueprint for this business.",
      actor: "founder",
      priority: "high",
      href: "/intake",
      actionType: "generate_blueprint",
    });
  }

  if (openHumanActions.length > 0) {
    actions.push({
      id: "review_pending_human_actions",
      label: "Review pending human actions",
      description: "Resolve the founder-controlled approvals and legal/payment steps.",
      actor: "founder",
      priority: "high",
      href: `${hrefBase}#human-actions`,
      actionType: "review_human_actions",
    });
  }

  if (githubPermission && !isPermissionApproved(githubPermission)) {
    actions.push({
      id: "approve_github",
      label: "Approve GitHub",
      description: "Authorize bucks.ai to create a repository for this business.",
      actor: "founder",
      priority: "high",
      href: `${hrefBase}#tools`,
      actionType: "approve_tool_permission",
    });
  }

  if (isPermissionApproved(githubPermission) && !githubRepo) {
    actions.push({
      id: "create_github_repo",
      label: "Create GitHub repo",
      description: "Create the source repository that will hold generated application code.",
      actor: "bucks_ai",
      priority: "high",
      href: `${hrefBase}#repository-execution`,
      actionType: "create_github_repo",
    });
  }

  if (githubRepo && !hasLog(input.activityLogs, "github_next_scaffold_prepared")) {
    actions.push({
      id: "prepare_deployable_scaffold",
      label: "Prepare deployable scaffold",
      description: "Write the deployable Next.js scaffold into the GitHub repo.",
      actor: "bucks_ai",
      priority: "medium",
      href: `${hrefBase}#deployment-execution`,
      actionType: "prepare_next_scaffold",
    });
  }

  if (githubRepo && vercelPermission && !isPermissionApproved(vercelPermission)) {
    actions.push({
      id: "approve_vercel",
      label: "Approve Vercel",
      description: "Authorize bucks.ai to create the Vercel project.",
      actor: "founder",
      priority: "high",
      href: `${hrefBase}#tools`,
      actionType: "approve_tool_permission",
    });
  }

  if (githubRepo && isPermissionApproved(vercelPermission) && !vercelProject) {
    actions.push({
      id: "create_vercel_project",
      label: "Create Vercel project",
      description: "Create and link the Vercel project for the business repo.",
      actor: "bucks_ai",
      priority: "medium",
      href: `${hrefBase}#deployment-execution`,
      actionType: "create_vercel_project",
    });
  }

  if (vercelProject?.vercelDeploymentUrl) {
    actions.push({
      id: "start_customer_validation",
      label: "Start customer validation",
      description: "Use the live deployment to begin founder-led validation.",
      actor: "founder",
      priority: "medium",
      href: vercelProject.vercelDeploymentUrl,
      actionType: "start_validation",
    });
  }

  return actions;
}

export function getExecutionAssets(input: ExecutionStatusInput): ExecutionAsset[] {
  const assets: ExecutionAsset[] = [];

  if (input.blueprint) {
    assets.push({
      id: input.blueprint.id,
      type: "blueprint",
      label: "Latest blueprint",
      status: "available",
      metadata: {
        createdAt: input.blueprint.created_at,
      },
    });
  }

  for (const permission of input.toolPermissions) {
    assets.push({
      id: permission.id,
      type: "tool_permission",
      label: permission.tool_name,
      status: permission.status,
      metadata: {
        toolId: permission.tool_id,
        setupStatus: permission.setup_status,
        riskLevel: permission.risk_level,
      },
    });
  }

  if (input.githubRepo) {
    assets.push({
      id: input.githubRepo.activityLogId,
      type: "github_repo",
      label: input.githubRepo.githubRepoFullName,
      url: input.githubRepo.githubRepoUrl,
      status: "created",
      metadata: {
        repoId: input.githubRepo.githubRepoId,
        cloneUrl: input.githubRepo.githubCloneUrl,
        createdAt: input.githubRepo.createdAt,
      },
    });
  }

  if (input.vercelProject) {
    assets.push({
      id: input.vercelProject.activityLogId,
      type: "vercel_project",
      label: input.vercelProject.vercelProjectName,
      url: input.vercelProject.vercelDashboardUrl,
      status: "created",
      metadata: {
        projectId: input.vercelProject.vercelProjectId,
        gitRepoFullName: input.vercelProject.gitRepoFullName,
        productionBranch: input.vercelProject.productionBranch,
      },
    });
  }

  if (input.vercelProject?.vercelDeploymentUrl) {
    assets.push({
      id: `${input.vercelProject.activityLogId}:deployment`,
      type: "deployment",
      label: "Latest deployment",
      url: input.vercelProject.vercelDeploymentUrl,
      status: "available",
      metadata: {
        projectId: input.vercelProject.vercelProjectId,
        createdAt: input.vercelProject.createdAt,
      },
    });
  }

  return assets;
}

export function calculateProgressPercent(
  milestones: ExecutionMilestone[]
): number {
  if (milestones.length === 0) return 0;
  const completeWeight = milestones.reduce((total, item) => {
    if (item.status === "complete") return total + 1;
    if (item.status === "warning") return total + 0.75;
    if (item.status === "in_progress") return total + 0.5;
    return total;
  }, 0);

  return Math.round((completeWeight / milestones.length) * 100);
}

export function determineCurrentPhase(
  milestones: ExecutionMilestone[]
): ExecutionPhase {
  const phaseByMilestone: Record<string, ExecutionPhase> = {
    idea_captured: "intake",
    blueprint_generated: "blueprint",
    tool_permissions_seeded: "permissions",
    github_approved: "permissions",
    github_repo_created: "repository",
    deployable_scaffold_prepared: "scaffold",
    vercel_approved: "permissions",
    vercel_project_created: "deployment",
    deployment_available: "deployment",
    ready_for_validation: "validation",
  };

  const firstIncomplete = milestones.find(
    (item) => item.status !== "complete" && item.status !== "warning"
  );
  if (!firstIncomplete) return "operating";

  return phaseByMilestone[firstIncomplete.id] ?? "operating";
}

export function determineExecutionHealth(
  blockers: ExecutionBlocker[],
  milestones: ExecutionMilestone[]
): BusinessExecutionStatus["health"] {
  if (blockers.some((blocker) => blocker.severity === "high")) return "blocked";
  if (blockers.length > 0 || milestones.some((item) => item.status === "warning")) {
    return "needs_attention";
  }
  if (milestones.every((item) => item.status === "complete")) return "ready";
  return "in_progress";
}
