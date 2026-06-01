import Link from "next/link";
import {
  DeploymentStatusBadge,
  deploymentStatusLabel,
} from "@/components/deployment/DeploymentStatusBadge";
import { StatusPill } from "@/components/ui/StatusPill";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { BusinessExecutionStatus } from "@/types/execution-ui";
import type { DeploymentStatus } from "@/types/deployment-ui";

type WorkspaceHeaderProps = {
  business: DashboardBusiness;
  executionStatus?: BusinessExecutionStatus | null;
  onBlueprintOpen?: () => void;
};

function healthVariant(health: string): "success" | "warning" | "danger" | "accent" {
  if (health === "complete" || health === "on_track") return "success";
  if (health === "needs_attention") return "warning";
  if (health === "blocked") return "danger";
  return "accent";
}

function healthLabel(health: string): string {
  if (health === "on_track") return "On track";
  if (health === "needs_attention") return "Needs attention";
  if (health === "blocked") return "Blocked";
  if (health === "complete") return "Complete";
  return health;
}

function phaseLabel(phase: string): string {
  return phase
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

function deploymentStatusFromBusiness(
  business: DashboardBusiness,
  executionStatus?: BusinessExecutionStatus | null
): DeploymentStatus {
  const deploymentMilestone = executionStatus?.milestones.find(
    (milestone) => milestone.id === "deployment"
  );

  if (business.vercelProject?.deploymentUrl) return "live";
  if (deploymentMilestone?.status === "blocked") return "failed";
  if (deploymentMilestone?.status === "in_progress") return "building";
  if (business.vercelProject) return "not_deployed";
  return "no_project";
}

const assetLink =
  "hidden items-center rounded-lg border border-border bg-elevated px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.16em] text-secondary transition-colors hover:border-accent/40 hover:text-accent md:inline-flex";

export function WorkspaceHeader({
  business,
  executionStatus,
  onBlueprintOpen,
}: WorkspaceHeaderProps) {
  const phase = executionStatus?.currentPhase ?? "blueprint";
  const health = executionStatus?.health ?? "on_track";
  const progress = executionStatus?.progressPercent ?? 0;
  const latestRun =
    executionStatus?.timeline?.[0]?.status ?? executionStatus?.timeline?.[0]?.category;
  const deploymentStatus = deploymentStatusFromBusiness(business, executionStatus);

  return (
    <div className="px-4 py-2.5 sm:px-6">
      <div className="flex items-center justify-between gap-3">
        {/* Left: identity */}
        <div className="flex min-w-0 items-center gap-2.5">
          <Link
            href="/dashboard"
            aria-label="Back to Mission Control"
            className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-border text-secondary transition-colors hover:border-accent/40 hover:text-foreground"
          >
            <span aria-hidden="true">&#8592;</span>
          </Link>
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold tracking-tight text-foreground sm:text-base">
              {business.name}
            </h1>
            <p className="mt-0.5 truncate font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
              {phaseLabel(phase)} &middot; {progress}%
            </p>
          </div>
          <div className="ml-1 hidden items-center gap-1.5 md:flex">
            <StatusPill label={healthLabel(health)} variant={healthVariant(health)} />
            {latestRun ? (
              <StatusPill label={`Run: ${phaseLabel(latestRun)}`} variant="accent" />
            ) : null}
            <DeploymentStatusBadge status={deploymentStatus} />
          </div>
        </div>

        {/* Right: asset shortcuts + blueprint */}
        <div className="flex shrink-0 items-center gap-1.5">
          {business.githubRepo ? (
            <a
              href={business.githubRepo.repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={assetLink}
            >
              GitHub
            </a>
          ) : null}
          {business.vercelProject?.dashboardUrl ? (
            <a
              href={business.vercelProject.dashboardUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={assetLink}
            >
              Vercel
            </a>
          ) : null}
          {business.vercelProject?.deploymentUrl ? (
            <a
              href={business.vercelProject.deploymentUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="hidden items-center rounded-lg border border-success/30 bg-success/10 px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.16em] text-success transition-colors hover:border-success/50 sm:inline-flex"
            >
              Live
            </a>
          ) : (
            <span className="hidden items-center rounded-lg border border-border bg-elevated px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.16em] text-muted lg:inline-flex">
              {deploymentStatusLabel(deploymentStatus)}
            </span>
          )}
          {onBlueprintOpen ? (
            <button
              type="button"
              onClick={onBlueprintOpen}
              className="inline-flex items-center rounded-lg border border-border bg-elevated px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.16em] text-secondary transition-colors hover:border-accent/40 hover:text-accent"
            >
              Blueprint
            </button>
          ) : null}
        </div>
      </div>

      {/* Progress line */}
      <div className="mt-2.5 h-0.5 w-full overflow-hidden rounded-full bg-border">
        <div
          className="h-full rounded-full bg-accent transition-all duration-700"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
