import { BusinessWorkspace } from "@/components/workspace/BusinessWorkspace";
import type { DashboardBusiness, HumanAction } from "@/components/dashboard/mock-data";
import type {
  BusinessExecutionStatus,
  ExecutionMilestone,
  ExecutionTimelineEvent,
} from "@/types/execution-ui";

type BusinessDetailProps = {
  business: DashboardBusiness;
};

function permissionIsReady(status?: string | null) {
  return (
    status === "approved" ||
    status === "approved_by_founder" ||
    status === "connected_demo" ||
    status === "ready_to_connect"
  );
}

function buildFallbackMilestones(business: DashboardBusiness): ExecutionMilestone[] {
  const permissionsReady =
    business.toolPermissions && business.toolPermissions.length > 0
      ? business.toolPermissions.some(
          (permission) =>
            permissionIsReady(permission.status) ||
            permissionIsReady(permission.setupStatus)
        )
      : business.permissions.length > 0;
  const blockedPermissions =
    business.toolPermissions?.some(
      (permission) => permission.status === "blocked" || permission.status === "rejected"
    ) ?? false;
  const hasRepo = Boolean(business.githubRepo);
  const hasVercelProject = Boolean(business.vercelProject);
  const hasDeployment = Boolean(business.vercelProject?.deploymentUrl);

  return [
    {
      id: "idea_captured",
      label: "Idea captured",
      status: "complete",
      description: "Saved business record exists.",
    },
    {
      id: "blueprint",
      label: "Blueprint",
      status: business.blueprintSummary ? "complete" : "pending",
      description: business.blueprintSummary
        ? "Latest blueprint summary is available."
        : "No blueprint summary is recorded yet.",
    },
    {
      id: "permissions",
      label: "Permissions",
      status: blockedPermissions ? "blocked" : permissionsReady ? "complete" : "in_progress",
      description: "Tool setup queue controls external access.",
      href: "#tool-setup-queue",
    },
    {
      id: "github",
      label: "GitHub",
      status: hasRepo ? "complete" : "pending",
      description: hasRepo
        ? "Repository asset is recorded."
        : "Repository creation is available after GitHub approval.",
      href: "#repository-execution",
    },
    {
      id: "scaffold",
      label: "Scaffold",
      status: hasRepo ? "in_progress" : "pending",
      description: "Starter scaffold is prepared after repository setup.",
      href: "#deployment-execution",
    },
    {
      id: "vercel",
      label: "Vercel",
      status: hasVercelProject ? "complete" : "pending",
      description: hasVercelProject
        ? "Vercel project asset is recorded."
        : "Vercel project creation waits for source and approval.",
      href: "#deployment-execution",
    },
    {
      id: "deployment",
      label: "Deployment",
      status: hasDeployment ? "complete" : "pending",
      description: hasDeployment
        ? "Deployment URL is recorded."
        : "Deployment URL will appear after a successful deployment.",
      href: "#deployment-execution",
    },
    {
      id: "validation",
      label: "Validation",
      status: hasDeployment ? "in_progress" : "pending",
      description: "Validation begins after a deployment target exists.",
    },
  ];
}

function buildFallbackTimeline(business: DashboardBusiness): ExecutionTimelineEvent[] {
  if (business.activityLogs && business.activityLogs.length > 0) {
    return business.activityLogs.map((log, index) => ({
      id: `${log.activityType}-${log.createdAt}-${index}`,
      category: log.activityType,
      title: log.message,
      message: log.message,
      actor: log.activityType,
      status: "log",
      createdAt: log.createdAt,
      metadata: log.metadata,
    }));
  }

  return business.activity.map((item, index) => ({
    id: `${item.time}-${item.actor}-${index}`,
    category: item.statusLabel ?? item.tone ?? "activity",
    title: item.event,
    message: item.event,
    actor: item.actor,
    status: item.statusLabel ?? item.tone ?? "log",
    createdAt: new Date().toISOString(),
    metadata: { time: item.time },
  }));
}

function buildFallbackExecutionStatus(
  business: DashboardBusiness,
  humanActions: HumanAction[]
): BusinessExecutionStatus {
  const milestones = buildFallbackMilestones(business);
  const completedMilestones = milestones.filter(
    (milestone) => milestone.status === "complete"
  ).length;
  const blockers = humanActions.map((action, index) => ({
    id: `human-action-${index}`,
    title: action.title,
    description: action.reason,
    severity: "warning" as const,
    owner: "founder" as const,
    href: "#execution-human-actions",
  }));
  const currentMilestone =
    milestones.find((milestone) => milestone.status === "in_progress") ??
    milestones.find((milestone) => milestone.status === "pending") ??
    milestones[milestones.length - 1];
  const nextActions = [
    ...humanActions.slice(0, 3).map((action, index) => ({
      id: `founder-action-${index}`,
      title: action.title,
      description: action.reason,
      actor: "founder" as const,
      href: "#execution-human-actions",
      priority: "high" as const,
    })),
    ...business.nextActions.slice(0, 4).map((action, index) => ({
      id: `bucks-action-${index}`,
      title: action,
      actor: "bucks_ai" as const,
      href: "#execution-next-actions",
      priority: "medium" as const,
    })),
  ];
  const assets = [
    {
      id: "blueprint",
      label: "Latest blueprint summary",
      type: "blueprint" as const,
      url: "#execution-blueprint-summary",
      status: business.blueprintSummary ? "recorded" : "pending",
      description: "Summary from the saved launch blueprint.",
    },
    {
      id: "tool-permissions",
      label: "Tool Permission Setup Queue",
      type: "tool_permissions" as const,
      url: "#tool-setup-queue",
      status: business.permissions.length > 0 ? "recorded" : "pending",
      description: "Founder-controlled permission layer.",
    },
    ...(business.githubRepo
      ? [
          {
            id: "github-repo",
            label: business.githubRepo.fullName,
            type: "github_repo" as const,
            url: business.githubRepo.repoUrl,
            status: business.githubRepo.private ? "private" : "public",
            description: "Recorded GitHub repository.",
          },
        ]
      : []),
    ...(business.vercelProject
      ? [
          {
            id: "vercel-project",
            label: business.vercelProject.projectName,
            type: "vercel_project" as const,
            url: business.vercelProject.dashboardUrl,
            status: "recorded",
            description: "Recorded Vercel project.",
          },
        ]
      : []),
    ...(business.vercelProject?.deploymentUrl
      ? [
          {
            id: "deployment-url",
            label: business.vercelProject.deploymentUrl,
            type: "deployment_url" as const,
            url: business.vercelProject.deploymentUrl,
            status: "live",
            description: "Recorded deployment URL.",
          },
        ]
      : []),
  ];

  return {
    businessId: business.id,
    currentPhase: currentMilestone.id,
    health:
      blockers.length > 0
        ? "needs_attention"
        : completedMilestones === milestones.length
          ? "complete"
          : "on_track",
    progressPercent: Math.round((completedMilestones / milestones.length) * 100),
    milestones,
    blockers,
    nextActions,
    assets,
    timeline: buildFallbackTimeline(business),
    updatedAt: new Date().toISOString(),
  };
}

export function BusinessDetail({ business }: BusinessDetailProps) {
  const humanActions =
    business.humanActionItems ??
    business.humanActions.map((action) => ({
      title: action,
      business: business.name,
      reason: "This action requires founder approval before autonomous execution.",
      status: "Needs review",
    }));

  const businessWithNormalizedActions = {
    ...business,
    humanActionItems: humanActions,
  };

  const initialStatus = buildFallbackExecutionStatus(business, humanActions);

  return (
    <BusinessWorkspace
      business={businessWithNormalizedActions}
      initialExecutionStatus={initialStatus}
    />
  );
}
