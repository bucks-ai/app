import Link from "next/link";
import { ActivityLog } from "@/components/dashboard/ActivityLog";
import { HumanActionQueue } from "@/components/dashboard/HumanActionQueue";
import { ToolPermissionSummary } from "@/components/dashboard/ToolPermissionSummary";
import type { DashboardBusiness, HumanAction } from "@/components/dashboard/mock-data";
import { ExecutionCommandCenter } from "@/components/execution/ExecutionCommandCenter";
import { GitHubRepoCard } from "@/components/github/GitHubRepoCard";
import { GitHubRepoGate } from "@/components/github/GitHubRepoGate";
import { PermissionControlRoom } from "@/components/tools/PermissionControlRoom";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";
import { DeploymentExecutionPanel } from "@/components/vercel/DeploymentExecutionPanel";
import type {
  BusinessExecutionStatus,
  ExecutionMilestone,
  ExecutionTimelineEvent,
} from "@/types/execution-ui";

type BusinessDetailProps = {
  business: DashboardBusiness;
};

function isApprovedGitHubPermission(business: DashboardBusiness) {
  const githubPermission = business.toolPermissions?.find(
    (permission) => permission.toolId === "github"
  );

  if (!githubPermission) return true;

  return (
    githubPermission.status === "approved" ||
    githubPermission.status === "approved_by_founder" ||
    githubPermission.status === "connected_demo" ||
    githubPermission.setupStatus === "ready_to_connect" ||
    githubPermission.setupStatus === "connected_demo"
  );
}

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

  return (
    <div className="space-y-8">
      <Link
        href="/dashboard"
        className="inline-flex text-sm font-medium text-[#A5B4FC] transition-colors hover:text-[#C7D2FE]"
      >
        &lt;- Back to Mission Control
      </Link>

      <OperatorPanel className="p-6 shadow-[0_30px_140px_rgba(0,0,0,0.38)] sm:p-10">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-3">
              <SectionLabel>{business.sourceLabel ?? "Saved build record"}</SectionLabel>
              <StatusPill label={business.status} variant={business.statusVariant} />
            </div>
            <h1 className="mt-5 text-4xl font-semibold tracking-tight text-[#F0F0F0] sm:text-5xl">
              {business.name}
            </h1>
            <p className="mt-4 text-base leading-8 text-[#888888]">{business.overview}</p>
          </div>
          <div className="grid min-w-64 gap-3 rounded-lg border border-[#1C1C1C] bg-[#080808] p-4">
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#444444]">
                Business type
              </p>
              <p className="mt-2 text-sm font-medium text-[#F0F0F0]">
                {business.businessType}
              </p>
            </div>
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#444444]">
                Goal
              </p>
              <p className="mt-2 text-sm leading-6 text-[#D4D4D4]">{business.goal}</p>
            </div>
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#444444]">
                Created
              </p>
              <p className="mt-2 text-sm leading-6 text-[#D4D4D4]">{business.created}</p>
            </div>
          </div>
        </div>
      </OperatorPanel>

      <ExecutionCommandCenter
        businessId={business.id}
        initialStatus={buildFallbackExecutionStatus(business, humanActions)}
      />

      <section className="grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
        <OperatorPanel id="execution-blueprint-summary" className="scroll-mt-28 p-6">
          <SectionLabel>Latest blueprint summary</SectionLabel>
          <p className="mt-4 text-sm leading-7 text-[#D4D4D4]">
            {business.blueprintSummary}
          </p>
        </OperatorPanel>

        <OperatorPanel id="execution-human-actions" className="scroll-mt-28 p-6" elevated>
          <SectionLabel tone="warning">Human-required actions</SectionLabel>
          <div className="mt-5">
            {humanActions.length > 0 ? (
              <HumanActionQueue actions={humanActions} />
            ) : (
              <p className="rounded-md border border-[#F59E0B]/25 bg-[#F59E0B]/10 p-4 text-sm leading-6 text-[#FDE68A]">
                No pending human-required actions are attached to this business.
              </p>
            )}
          </div>
        </OperatorPanel>
      </section>

      <section className="grid gap-6 xl:grid-cols-3">
        <OperatorPanel id="execution-next-actions" className="scroll-mt-28 p-6 xl:col-span-1">
          <SectionLabel>Next autonomous actions</SectionLabel>
          <ul className="mt-5 space-y-3">
            {business.nextActions.length > 0 ? (
              business.nextActions.map((action) => (
                <li
                  key={action}
                  className="rounded-md border border-[#1C1C1C] bg-[#080808] p-4 text-sm leading-6 text-[#D4D4D4]"
                >
                  {action}
                </li>
              ))
            ) : (
              <li className="rounded-md border border-[#1C1C1C] bg-[#080808] p-4 text-sm leading-6 text-[#888888]">
                No autonomous action queue was found in the latest blueprint.
              </li>
            )}
          </ul>
        </OperatorPanel>

        <OperatorPanel className="p-6 xl:col-span-1">
          <SectionLabel>Activity log</SectionLabel>
          <div className="mt-5">
            {business.activity.length > 0 ? (
              <ActivityLog items={business.activity} />
            ) : (
              <p className="rounded-md border border-[#1C1C1C] bg-[#080808] p-4 text-sm leading-6 text-[#888888]">
                Activity logs will appear as bucks.ai works on this project.
              </p>
            )}
          </div>
        </OperatorPanel>

        <OperatorPanel className="p-6 xl:col-span-1">
          <SectionLabel>Tool permissions</SectionLabel>
          <div className="mt-5">
            {business.permissions.length > 0 ? (
              <ToolPermissionSummary permissions={business.permissions} />
            ) : (
              <p className="rounded-md border border-[#1C1C1C] bg-[#080808] p-4 text-sm leading-6 text-[#888888]">
                No suggested tool permissions were found in the latest blueprint.
              </p>
            )}
          </div>
        </OperatorPanel>
      </section>

      <div id="tool-setup-queue" className="scroll-mt-28">
        <PermissionControlRoom businessId={business.id} businessName={business.name} />
      </div>

      <OperatorPanel
        id="repository-execution"
        className="scroll-mt-28 p-6 shadow-[0_30px_120px_rgba(0,0,0,0.34)] sm:p-8"
      >
        <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-3">
              <SectionLabel>Repository Execution</SectionLabel>
              <StatusPill label="Controlled external action" variant="warning" />
            </div>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight text-[#F0F0F0]">
              GitHub repository creation
            </h2>
            <p className="mt-3 text-sm leading-7 text-[#888888] sm:text-base">
              Create a private GitHub repo only after GitHub is approved in the
              setup queue. This is the first real external asset bucks.ai can
              create for a saved business.
            </p>
          </div>
        </div>

        <div className="mt-6">
          {isApprovedGitHubPermission(business) ? (
            <GitHubRepoCard
              businessId={business.id}
              businessName={business.name}
              oneLineIdea={business.oneLineIdea ?? business.overview}
              existingRepo={business.githubRepo ?? null}
            />
          ) : (
            <GitHubRepoGate />
          )}
        </div>
      </OperatorPanel>

      <DeploymentExecutionPanel
        businessId={business.id}
        businessName={business.name}
        oneLineIdea={business.oneLineIdea ?? business.overview}
        activityLogs={business.activityLogs}
        toolPermissions={business.toolPermissions}
        existingGitHubRepo={business.githubRepo ?? null}
        existingVercelProject={business.vercelProject ?? null}
      />
    </div>
  );
}
