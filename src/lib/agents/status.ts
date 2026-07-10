// Business-aware agent status resolver.
//
// Resolves the runtime status of every agent in the registry for a given
// business by reading existing data sources — no new tables required.
//
// Status inference uses activity logs as the primary signal so this module
// works even when validation/research schemas have not yet been applied.
//
// Agent Runs v1 enhancement:
// When the agent_runs table is available, the latest run per agent is used to
// surface the "active" and "waiting_for_approval" statuses that cannot be
// inferred from activity logs alone. If the table is missing the resolver
// falls back to the existing activity-log-based logic transparently.

import {
  getBusinessById,
  getLatestBlueprintForBusiness,
  getAgentActivityLogs,
  getHumanRequiredActions,
} from "@/lib/projects";
import { getToolPermissionsForBusiness } from "@/lib/tool-permissions";
import { getLatestGitHubRepoForBusiness } from "@/lib/github/repo-metadata";
import { getLatestVercelProjectForBusiness } from "@/lib/vercel/project-metadata";
import {
  AGENT_NODE_ORDER,
  getAllAgentTemplates,
  getAgentNodeLabel,
  getAgentNodeDescription,
} from "@/lib/agents/registry";
import type {
  AgentTemplate,
  AgentTemplateId,
  AgentBusinessStatus,
  AgentNodeSummary,
  AgentRegistryEntry,
  AgentRegistryView,
  AgentRegistrySummary,
  AgentStatus,
} from "@/types/agents";
import type {
  AgentActivityLogRecord,
  AgentRunDatabaseRecord,
  BusinessBlueprintRecord,
  HumanRequiredActionRecord,
} from "@/types/database";
import type { ToolPermissionView } from "@/types/tool-permissions";
import type { GitHubRepoMetadata } from "@/lib/github/repo-metadata";
import type { VercelProjectMetadata } from "@/lib/vercel/project-metadata";
import { getAgentRunsForBusiness } from "@/lib/agents/runs";

// ---------------------------------------------------------------------------
// Result wrapper
// ---------------------------------------------------------------------------

type Result<T> =
  | { data: T; error: null; code?: undefined }
  | { data: null; error: string; code: string };

function ok<T>(data: T): Result<T> {
  return { data, error: null };
}

function err<T>(message: string, code = "unknown_error"): Result<T> {
  return { data: null, error: message, code };
}

function agentRunTimestamp(run: Pick<
  AgentRunDatabaseRecord,
  "completed_at" | "started_at" | "updated_at" | "created_at"
>): number {
  const value = run.completed_at ?? run.started_at ?? run.updated_at ?? run.created_at;
  const timestamp = new Date(value).getTime();
  return Number.isNaN(timestamp) ? 0 : timestamp;
}

// ---------------------------------------------------------------------------
// Business context — everything the resolver needs
// ---------------------------------------------------------------------------

interface AgentStatusContext {
  blueprint: BusinessBlueprintRecord | null;
  toolPermissions: ToolPermissionView[];
  activityLogs: AgentActivityLogRecord[];
  humanActions: HumanRequiredActionRecord[];
  githubRepo: GitHubRepoMetadata | null;
  vercelProject: VercelProjectMetadata | null;
  // Keyed by agent_id — null if no run exists for that agent.
  // Undefined means agent_runs table was not available; fall back to existing logic.
  latestRunByAgent?: Record<string, { status: string } | null>;
}

// ---------------------------------------------------------------------------
// Activity log helpers
// ---------------------------------------------------------------------------

function hasLog(logs: AgentActivityLogRecord[], activityType: string): boolean {
  return logs.some((log) => log.activity_type === activityType);
}

function latestLogAt(
  logs: AgentActivityLogRecord[],
  activityType: string
): string | null {
  const log = logs.find((l) => l.activity_type === activityType);
  return log?.created_at ?? null;
}

function findToolPermission(
  permissions: ToolPermissionView[],
  toolId: string
): ToolPermissionView | null {
  return permissions.find((p) => p.tool_id === toolId) ?? null;
}

const APPROVED_STATUSES = new Set(["approved", "approved_by_founder", "connected_demo"]);

function isPermissionApproved(p: ToolPermissionView | null): boolean {
  return Boolean(p && APPROVED_STATUSES.has(p.status));
}

// ---------------------------------------------------------------------------
// Per-agent status resolution
// ---------------------------------------------------------------------------

export function resolveAgentStatusForBusiness(
  agent: AgentTemplate,
  ctx: AgentStatusContext
): AgentBusinessStatus {
  const {
    blueprint,
    toolPermissions,
    activityLogs,
    humanActions,
    githubRepo,
    vercelProject,
  } = ctx;

  const hasBlueprint = Boolean(blueprint);
  const hasAnyLogs = activityLogs.length > 0;
  const hasAnyPermissions = toolPermissions.length > 0;
  const hasOpenHumanActions = humanActions.length > 0;

  const githubPermission = findToolPermission(toolPermissions, "github");
  const vercelPermission = findToolPermission(toolPermissions, "vercel");

  const researchGenerated = hasLog(activityLogs, "research_workspace_generated");
  const researchReportCreated = hasLog(activityLogs, "research_report_created");
  const validationSeeded = hasLog(activityLogs, "validation_workspace_seeded");
  const scaffoldPrepared = hasLog(activityLogs, "github_next_scaffold_prepared");
  const feedbackAdded = hasLog(activityLogs, "validation_feedback_added");

  let status: AgentStatus;
  let statusReason: string;
  let lastActivityAt: string | null = null;
  let completedAt: string | null = null;

  switch (agent.id as AgentTemplateId) {
    // -----------------------------------------------------------------------
    // Strategy Node
    // -----------------------------------------------------------------------

    case "idea_intake":
      status = "completed";
      statusReason = "Business idea has been captured.";
      completedAt = blueprint?.created_at ?? null;
      break;

    case "blueprint":
      if (hasBlueprint) {
        status = "completed";
        statusReason = "Launch blueprint has been generated and saved.";
        completedAt = blueprint!.created_at;
      } else {
        status = "ready";
        statusReason = "Ready to generate a launch blueprint from intake data.";
      }
      break;

    case "opportunity_framing":
      if (researchGenerated) {
        status = "completed";
        statusReason = "Research workspace exists; opportunity thesis can be framed.";
        completedAt = latestLogAt(activityLogs, "research_workspace_generated");
      } else if (hasBlueprint) {
        status = "ready";
        statusReason = "Blueprint exists; run research mode to frame the opportunity thesis.";
      } else {
        status = "unavailable";
        statusReason = "Requires a blueprint before opportunity framing can begin.";
      }
      break;

    // -----------------------------------------------------------------------
    // Deployment Node
    // -----------------------------------------------------------------------

    case "repository":
      if (githubRepo) {
        status = "completed";
        statusReason = "GitHub repository has been created.";
        completedAt = githubRepo.createdAt;
        lastActivityAt = githubRepo.createdAt;
      } else if (!githubPermission) {
        status = "unavailable";
        statusReason = "No GitHub tool permission exists; tool queue must be seeded first.";
      } else if (isPermissionApproved(githubPermission)) {
        status = "ready";
        statusReason = "GitHub is approved; ready to create the repository.";
      } else {
        status = "waiting_for_approval";
        statusReason = `GitHub permission is pending (${githubPermission.status}); awaiting founder approval.`;
      }
      break;

    case "scaffold":
      if (scaffoldPrepared) {
        status = "completed";
        statusReason = "Deployable Next.js scaffold has been pushed to the repository.";
        completedAt = latestLogAt(activityLogs, "github_next_scaffold_prepared");
        lastActivityAt = completedAt;
      } else if (!githubRepo) {
        status = "blocked";
        statusReason = "GitHub repository must be created before the scaffold can be prepared.";
      } else {
        status = "ready";
        statusReason = "GitHub repo exists; ready to prepare the deployable scaffold.";
      }
      break;

    case "deployment_status":
      if (vercelProject) {
        status = "monitoring";
        statusReason = "Vercel project exists; monitoring deployment health.";
        lastActivityAt = vercelProject.createdAt;
      } else if (githubRepo && isPermissionApproved(vercelPermission)) {
        status = "ready";
        statusReason = "Vercel is approved and the repo is ready; waiting for Vercel project creation.";
      } else if (!githubRepo) {
        status = "blocked";
        statusReason = "GitHub repository must exist before deployment monitoring can begin.";
      } else {
        status = "blocked";
        statusReason = "Vercel permission must be approved before deployment monitoring begins.";
      }
      break;

    // -----------------------------------------------------------------------
    // Validation Node
    // -----------------------------------------------------------------------

    case "persona":
      if (validationSeeded) {
        status = "completed";
        statusReason = "Validation workspace seeded; personas have been created.";
        completedAt = latestLogAt(activityLogs, "validation_workspace_seeded");
      } else if (hasBlueprint) {
        status = "ready";
        statusReason = "Blueprint exists; ready to seed personas from customer segments.";
      } else {
        status = "unavailable";
        statusReason = "Requires a blueprint before personas can be generated.";
      }
      break;

    case "hypothesis":
      if (validationSeeded) {
        status = "completed";
        statusReason = "Validation workspace seeded; hypotheses have been created.";
        completedAt = latestLogAt(activityLogs, "validation_workspace_seeded");
      } else if (hasBlueprint) {
        status = "ready";
        statusReason = "Blueprint exists; ready to generate validation hypotheses.";
      } else {
        status = "unavailable";
        statusReason = "Requires a blueprint before hypotheses can be generated.";
      }
      break;

    case "feedback_analysis":
      if (feedbackAdded) {
        status = "completed";
        statusReason = "Customer feedback notes have been recorded and can be analysed.";
        completedAt = latestLogAt(activityLogs, "validation_feedback_added");
        lastActivityAt = completedAt;
      } else if (validationSeeded) {
        status = "ready";
        statusReason = "Validation workspace is active; ready to analyse feedback as it is collected.";
      } else {
        status = "unavailable";
        statusReason = "Requires a seeded validation workspace before feedback analysis can begin.";
      }
      break;

    // -----------------------------------------------------------------------
    // Research Node
    // -----------------------------------------------------------------------

    case "market_research":
      if (researchGenerated) {
        status = "completed";
        statusReason = "Research workspace has been generated.";
        completedAt = latestLogAt(activityLogs, "research_workspace_generated");
        lastActivityAt = completedAt;
      } else if (hasBlueprint) {
        status = "ready";
        statusReason = "Blueprint exists; ready to generate the research workspace.";
      } else {
        status = "unavailable";
        statusReason = "Requires a blueprint before market research can be generated.";
      }
      break;

    case "customer_segment":
      if (researchGenerated) {
        status = "completed";
        statusReason = "Customer segments were seeded with the research workspace.";
        completedAt = latestLogAt(activityLogs, "research_workspace_generated");
      } else if (hasBlueprint) {
        status = "ready";
        statusReason = "Ready to identify and score customer segments once research is generated.";
      } else {
        status = "unavailable";
        statusReason = "Requires a blueprint before segment analysis can begin.";
      }
      break;

    case "competitor":
      if (researchGenerated) {
        status = "completed";
        statusReason = "Competitor landscape was mapped with the research workspace.";
        completedAt = latestLogAt(activityLogs, "research_workspace_generated");
      } else if (hasBlueprint) {
        status = "ready";
        statusReason = "Ready to map competitors once research is generated.";
      } else {
        status = "unavailable";
        statusReason = "Requires a blueprint before competitor mapping can begin.";
      }
      break;

    case "monetization":
      if (researchGenerated) {
        status = "completed";
        statusReason = "Monetisation models were seeded with the research workspace.";
        completedAt = latestLogAt(activityLogs, "research_workspace_generated");
      } else if (hasBlueprint) {
        status = "ready";
        statusReason = "Ready to model monetisation once research is generated.";
      } else {
        status = "unavailable";
        statusReason = "Requires a blueprint before monetisation modelling can begin.";
      }
      break;

    case "distribution":
      if (researchGenerated) {
        status = "completed";
        statusReason = "Distribution channels were mapped with the research workspace.";
        completedAt = latestLogAt(activityLogs, "research_workspace_generated");
      } else if (hasBlueprint) {
        status = "ready";
        statusReason = "Ready to map distribution channels once research is generated.";
      } else {
        status = "unavailable";
        statusReason = "Requires a blueprint before distribution analysis can begin.";
      }
      break;

    case "risk":
      if (researchGenerated) {
        status = "completed";
        statusReason = "Business risks were identified with the research workspace.";
        completedAt = latestLogAt(activityLogs, "research_workspace_generated");
      } else if (hasBlueprint) {
        status = "ready";
        statusReason = "Ready to identify and score risks once research is generated.";
      } else {
        status = "unavailable";
        statusReason = "Requires a blueprint before risk identification can begin.";
      }
      break;

    case "opportunity_scoring":
      if (researchReportCreated) {
        status = "completed";
        statusReason = "Research report with opportunity score has been created.";
        completedAt = latestLogAt(activityLogs, "research_report_created");
        lastActivityAt = completedAt;
      } else if (researchGenerated) {
        status = "ready";
        statusReason = "Research workspace exists; ready to compute an opportunity score.";
      } else {
        status = "unavailable";
        statusReason = "Requires a research workspace before opportunity scoring can begin.";
      }
      break;

    // -----------------------------------------------------------------------
    // Safety Node
    // -----------------------------------------------------------------------

    case "tool_permission":
      if (hasAnyPermissions) {
        status = "monitoring";
        statusReason = "Tool permission queue is active; monitoring approval status.";
        lastActivityAt =
          toolPermissions.reduce<string | null>((latest, p) => {
            if (!latest || p.updated_at > latest) return p.updated_at;
            return latest;
          }, null);
      } else if (hasBlueprint) {
        status = "ready";
        statusReason = "Blueprint exists; ready to seed the tool permission queue.";
      } else {
        status = "unavailable";
        statusReason = "Requires a blueprint before the tool permission queue can be seeded.";
      }
      break;

    case "risk_review":
      if (hasOpenHumanActions) {
        status = "monitoring";
        statusReason = `${humanActions.length} open human-required action${humanActions.length === 1 ? "" : "s"} pending review.`;
        lastActivityAt = humanActions[0]?.created_at ?? null;
      } else {
        status = "ready";
        statusReason = "No open human-required actions; monitoring for high-risk operations.";
      }
      break;

    // -----------------------------------------------------------------------
    // Orchestration Node
    // -----------------------------------------------------------------------

    case "task_router":
      if (hasAnyLogs) {
        status = "monitoring";
        statusReason = "Execution is active; routing tasks across nodes.";
        lastActivityAt = activityLogs[0]?.created_at ?? null;
      } else {
        status = "ready";
        statusReason = "Ready to route tasks once execution begins.";
      }
      break;

    case "next_action":
      if (hasAnyLogs) {
        status = "monitoring";
        statusReason = "Monitoring execution state and deriving next recommended action.";
        lastActivityAt = activityLogs[0]?.created_at ?? null;
      } else {
        status = "ready";
        statusReason = "Ready to derive next actions once execution begins.";
      }
      break;

    case "run_monitor":
      if (hasAnyLogs) {
        status = "monitoring";
        statusReason = "Activity logs are present; monitoring runs for anomalies.";
        lastActivityAt = activityLogs[0]?.created_at ?? null;
      } else {
        status = "ready";
        statusReason = "Ready to monitor runs once activity logs exist.";
      }
      break;

    default: {
      const _exhaustive: never = agent.id as never;
      void _exhaustive;
      status = "unavailable";
      statusReason = "Unknown agent.";
    }
  }

  // Agent Runs v1 enhancement — override status when a run signals active execution
  // or a pending approval that activity logs cannot capture.
  const latestRun = ctx.latestRunByAgent?.[agent.id];
  if (latestRun) {
    if (latestRun.status === "running") {
      status = "active";
      statusReason = "Agent is currently executing.";
    } else if (latestRun.status === "waiting_for_approval") {
      status = "waiting_for_approval";
      statusReason = "Awaiting founder approval to proceed.";
    }
  }

  return {
    agentId: agent.id,
    status,
    statusReason,
    lastActivityAt,
    completedAt,
  };
}

// ---------------------------------------------------------------------------
// Node summary builder
// ---------------------------------------------------------------------------

function buildNodeSummary(
  nodeId: (typeof AGENT_NODE_ORDER)[number],
  entries: AgentRegistryEntry[]
): AgentNodeSummary {
  const nodeEntries = entries.filter((e) => e.template.node === nodeId);
  return {
    nodeId,
    nodeLabel: getAgentNodeLabel(nodeId),
    nodeDescription: getAgentNodeDescription(nodeId),
    agents: nodeEntries,
    activeCount: nodeEntries.filter((e) => e.businessStatus.status === "active").length,
    completedCount: nodeEntries.filter((e) => e.businessStatus.status === "completed").length,
    blockedCount: nodeEntries.filter(
      (e) =>
        e.businessStatus.status === "blocked" ||
        e.businessStatus.status === "waiting_for_approval"
    ).length,
    readyCount: nodeEntries.filter((e) => e.businessStatus.status === "ready").length,
    monitoringCount: nodeEntries.filter((e) => e.businessStatus.status === "monitoring").length,
  };
}

// ---------------------------------------------------------------------------
// Registry summary builder
// ---------------------------------------------------------------------------

function buildRegistrySummary(
  businessId: string,
  entries: AgentRegistryEntry[]
): AgentRegistrySummary {
  return {
    businessId,
    totalAgents: entries.length,
    activeCount: entries.filter((e) => e.businessStatus.status === "active").length,
    completedCount: entries.filter((e) => e.businessStatus.status === "completed").length,
    blockedCount: entries.filter((e) => e.businessStatus.status === "blocked").length,
    readyCount: entries.filter((e) => e.businessStatus.status === "ready").length,
    monitoringCount: entries.filter((e) => e.businessStatus.status === "monitoring").length,
    unavailableCount: entries.filter((e) => e.businessStatus.status === "unavailable").length,
    waitingCount: entries.filter(
      (e) => e.businessStatus.status === "waiting_for_approval"
    ).length,
    generatedAt: new Date().toISOString(),
  };
}

// ---------------------------------------------------------------------------
// Public API
// ---------------------------------------------------------------------------

export async function getAgentRegistryForBusiness(
  businessId: string
): Promise<Result<AgentRegistryView>> {
  const businessResult = await getBusinessById(businessId);
  if (businessResult.error || !businessResult.data) {
    return err(businessResult.error ?? "Business not found.", "business_not_found");
  }

  const [
    blueprintResult,
    toolPermissionsResult,
    activityLogsResult,
    humanActionsResult,
    githubRepoResult,
    vercelProjectResult,
    agentRunsResult,
  ] = await Promise.all([
    getLatestBlueprintForBusiness(businessId),
    getToolPermissionsForBusiness(businessId),
    getAgentActivityLogs(businessId),
    getHumanRequiredActions(businessId),
    getLatestGitHubRepoForBusiness(businessId),
    getLatestVercelProjectForBusiness(businessId),
    getAgentRunsForBusiness(businessId),
  ]);

  if (toolPermissionsResult.error || !toolPermissionsResult.data) {
    return err(
      toolPermissionsResult.error ?? "Could not load tool permissions.",
      "agent_registry_unavailable"
    );
  }
  if (activityLogsResult.error || !activityLogsResult.data) {
    return err(
      activityLogsResult.error ?? "Could not load activity logs.",
      "agent_registry_unavailable"
    );
  }
  if (humanActionsResult.error || !humanActionsResult.data) {
    return err(
      humanActionsResult.error ?? "Could not load human-required actions.",
      "agent_registry_unavailable"
    );
  }

  // Build a per-agent latest-run map when agent_runs is available.
  // If the table is missing, leave undefined so the resolver falls back gracefully.
  let latestRunByAgent: Record<string, { status: string; timestamp: number } | null> | undefined;
  if (agentRunsResult.data && agentRunsResult.code !== "agent_runs_schema_missing") {
    latestRunByAgent = {};
    for (const run of agentRunsResult.data) {
      const current = latestRunByAgent[run.agent_id];
      const timestamp = agentRunTimestamp(run);
      if (!current || timestamp > current.timestamp) {
        latestRunByAgent[run.agent_id] = { status: run.status, timestamp };
      }
    }
  }

  const ctx: AgentStatusContext = {
    blueprint: blueprintResult.data ?? null,
    toolPermissions: toolPermissionsResult.data,
    activityLogs: activityLogsResult.data,
    humanActions: humanActionsResult.data,
    githubRepo: githubRepoResult.data ?? null,
    vercelProject: vercelProjectResult.data ?? null,
    latestRunByAgent,
  };

  const templates = getAllAgentTemplates();
  const entries: AgentRegistryEntry[] = templates.map((template) => ({
    template,
    businessStatus: resolveAgentStatusForBusiness(template, ctx),
  }));

  const nodes: AgentNodeSummary[] = AGENT_NODE_ORDER.map((nodeId) =>
    buildNodeSummary(nodeId, entries)
  );

  const summary = buildRegistrySummary(businessId, entries);

  return ok({ summary, nodes, agents: entries });
}

export async function getAgentRegistrySummaryForBusiness(
  businessId: string
): Promise<Result<AgentRegistrySummary>> {
  const result = await getAgentRegistryForBusiness(businessId);
  if (result.error || !result.data) {
    return err(result.error ?? "Could not build agent registry.", result.code ?? "agent_registry_unavailable");
  }
  return ok(result.data.summary);
}

export async function getAgentNodeSummariesForBusiness(
  businessId: string
): Promise<Result<AgentNodeSummary[]>> {
  const result = await getAgentRegistryForBusiness(businessId);
  if (result.error || !result.data) {
    return err(result.error ?? "Could not build agent registry.", result.code ?? "agent_registry_unavailable");
  }
  return ok(result.data.nodes);
}

// Re-export for convenience
export { resolveAgentStatusForBusiness as resolveStatus };
