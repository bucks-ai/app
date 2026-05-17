"use client";

import { useEffect, useMemo, useState } from "react";
import type { DashboardToolPermission } from "@/components/dashboard/mock-data";
import { fetchVercelProjectStatus } from "@/lib/vercel-client";
import type {
  DeploymentActivityLog,
  VercelProjectResult,
} from "@/types/vercel-ui";
import type { GitHubRepoResult } from "@/types/github-ui";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";
import { ScaffoldPrepCard } from "@/components/vercel/ScaffoldPrepCard";
import { VercelDeployGate } from "@/components/vercel/VercelDeployGate";
import { VercelProjectCard } from "@/components/vercel/VercelProjectCard";

type DeploymentExecutionPanelProps = {
  businessId: string;
  businessName: string;
  oneLineIdea?: string | null;
  activityLogs?: DeploymentActivityLog[];
  toolPermissions?: DashboardToolPermission[];
  existingGitHubRepo?: GitHubRepoResult | null;
  existingVercelProject?: VercelProjectResult | null;
};

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function isApprovedVercelPermission(toolPermissions?: DashboardToolPermission[]) {
  const vercelPermission = toolPermissions?.find(
    (permission) => permission.toolId === "vercel"
  );

  if (!vercelPermission) return true;

  return (
    vercelPermission.status === "approved" ||
    vercelPermission.status === "approved_by_founder" ||
    vercelPermission.status === "connected_demo" ||
    vercelPermission.setupStatus === "connected_demo"
  );
}

function projectFromMetadata(
  metadata: Record<string, unknown>
): VercelProjectResult | null {
  const projectName =
    asString(metadata.projectName) ??
    asString(metadata.project_name) ??
    asString(metadata.vercelProjectName) ??
    asString(metadata.name);
  const dashboardUrl =
    asString(metadata.dashboardUrl) ??
    asString(metadata.dashboard_url) ??
    asString(metadata.vercelDashboardUrl) ??
    asString(metadata.vercel_dashboard_url);

  if (!projectName || !dashboardUrl) return null;

  return {
    projectId:
      asString(metadata.projectId) ??
      asString(metadata.project_id) ??
      asString(metadata.vercelProjectId) ??
      undefined,
    projectName,
    dashboardUrl,
    deploymentUrl:
      asString(metadata.deploymentUrl) ??
      asString(metadata.deployment_url) ??
      asString(metadata.vercelDeploymentUrl) ??
      asString(metadata.vercel_deployment_url),
    repoFullName:
      asString(metadata.repoFullName) ??
      asString(metadata.repo_full_name) ??
      asString(metadata.githubRepoFullName) ??
      asString(metadata.github_repo_full_name),
  };
}

function repoExistsFromLogs(activityLogs?: DeploymentActivityLog[]) {
  return activityLogs?.some((log) => log.activityType === "github_repo_created") ?? false;
}

function latestVercelProject(activityLogs?: DeploymentActivityLog[]) {
  const log = activityLogs?.find((item) => item.activityType === "vercel_project_created");
  return log ? projectFromMetadata(log.metadata) : null;
}

export function DeploymentExecutionPanel({
  businessId,
  businessName,
  oneLineIdea,
  activityLogs,
  toolPermissions,
  existingGitHubRepo,
  existingVercelProject,
}: DeploymentExecutionPanelProps) {
  const hasGitHubRepo = !!existingGitHubRepo || repoExistsFromLogs(activityLogs);
  const hasVercelApproval = isApprovedVercelPermission(toolPermissions);
  const activityProject = useMemo(() => latestVercelProject(activityLogs), [activityLogs]);
  const [statusProject, setStatusProject] = useState<VercelProjectResult | null>(null);

  useEffect(() => {
    let ignore = false;

    async function loadStatus() {
      if (!hasGitHubRepo || !hasVercelApproval || existingVercelProject || activityProject) {
        return;
      }

      const result = await fetchVercelProjectStatus(businessId);
      if (!ignore && result.ok && result.data) {
        setStatusProject(result.data);
      }
    }

    void loadStatus();

    return () => {
      ignore = true;
    };
  }, [activityProject, businessId, existingVercelProject, hasGitHubRepo, hasVercelApproval]);

  const activeProject = existingVercelProject ?? activityProject ?? statusProject;

  return (
    <OperatorPanel
      id="deployment-execution"
      className="scroll-mt-28 p-6 shadow-[0_30px_120px_rgba(0,0,0,0.34)] sm:p-8"
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl">
          <div className="flex flex-wrap items-center gap-3">
            <SectionLabel>Deployment Execution</SectionLabel>
            <StatusPill label="Vercel approval gated" variant="warning" />
          </div>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight text-[#F0F0F0]">
            Vercel project creation
          </h2>
          <p className="mt-3 text-sm leading-7 text-[#888888] sm:text-base">
            Prepare a deployable starter and create a Vercel project after the
            GitHub repo exists and Vercel is approved in the Tool Setup Queue.
          </p>
        </div>
      </div>

      <div className="mt-6">
        {!hasGitHubRepo ? (
          <VercelDeployGate
            title="Create a GitHub repo first."
            description="Vercel needs a source repository before bucks.ai can prepare a starter app or create the deployment project."
            actionLabel="Go to Repository Execution"
            actionHref="#repository-execution"
          />
        ) : null}

        {hasGitHubRepo && !hasVercelApproval ? (
          <VercelDeployGate
            title="Approve Vercel in Tool Setup Queue first."
            description="The deployment step is blocked until the founder approves Vercel for this saved business."
            actionLabel="Go to Tool Setup Queue"
            actionHref="#tool-setup-queue"
          />
        ) : null}

        {hasGitHubRepo && hasVercelApproval ? (
          <div className="grid gap-5 xl:grid-cols-[0.85fr_1.15fr]">
            {!activeProject ? <ScaffoldPrepCard businessId={businessId} /> : null}
            <div className={!activeProject ? "" : "xl:col-span-2"}>
              <VercelProjectCard
                businessId={businessId}
                businessName={businessName}
                oneLineIdea={oneLineIdea}
                existingProject={activeProject}
              />
            </div>
          </div>
        ) : null}
      </div>
    </OperatorPanel>
  );
}
