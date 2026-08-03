import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import {
  DeploymentStatusBadge,
  deploymentStatusLabel,
} from "@/components/deployment/DeploymentStatusBadge";
import type { BusinessExecutionStatus } from "@/types/execution-ui";
import type { DeploymentStatus } from "@/types/deployment-ui";
import { AssetQuickLinks } from "@/components/workspace/AssetQuickLinks";

type TabKey =
  | "overview"
  | "research"
  | "actions"
  | "build"
  | "deploy"
  | "validation"
  | "team"
  | "tools"
  | "activity"
  | "settings";

type WorkspaceRightRailProps = {
  business: DashboardBusiness;
  executionStatus?: BusinessExecutionStatus | null;
  onTabChange: (tab: TabKey) => void;
};

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

export function WorkspaceRightRail({
  business,
  executionStatus,
  onTabChange,
}: WorkspaceRightRailProps) {
  const blockers = executionStatus?.blockers ?? [];
  const pendingApprovals = business.humanActionItems ?? [];
  const deploymentStatus = deploymentStatusFromBusiness(business, executionStatus);
  const progress = executionStatus?.progressPercent ?? 0;

  return (
    <aside className="space-y-3">
      {/* Progress snapshot */}
      <div className="solid-surface rounded-xl p-4">
        <div className="flex items-center justify-between gap-3">
          <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-accent">
            Progress
          </p>
          <span className="font-mono text-[11px] uppercase tracking-widest text-foreground-secondary">
            {progress}%
          </span>
        </div>
        <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-border">
          <div
            className="h-full rounded-full bg-accent transition-all duration-700"
            style={{ width: `${progress}%` }}
          />
        </div>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            type="button"
            onClick={() => onTabChange("actions")}
            className="interactive-surface min-h-20 rounded-lg border border-warning/20 bg-warning/8 px-2.5 py-2 text-left transition-colors hover:border-warning/40"
          >
            <span className="block font-mono text-[11px] uppercase tracking-widest text-warning">
              Approvals
            </span>
            <span className="mt-1 block text-lg font-semibold text-foreground">
              {pendingApprovals.length}
            </span>
          </button>
          <button
            type="button"
            onClick={() => onTabChange("actions")}
            className="interactive-surface min-h-20 rounded-lg border border-error/20 bg-error/8 px-2.5 py-2 text-left transition-colors hover:border-error/40"
          >
            <span className="block font-mono text-[11px] uppercase tracking-widest text-error">
              Blockers
            </span>
            <span className="mt-1 block text-lg font-semibold text-foreground">
              {blockers.length}
            </span>
          </button>
        </div>
      </div>

      {/* Key blockers */}
      {blockers.length > 0 ? (
        <div className="solid-surface rounded-xl p-4">
          <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-error">
            Key blockers
          </p>
          <div className="mt-3 space-y-2">
            {blockers.slice(0, 3).map((blocker) => (
              <div
                key={blocker.id}
                className="rounded-lg border border-error/20 bg-error/5 px-3 py-2"
              >
                <p className="text-xs font-medium text-foreground">{blocker.title}</p>
                {blocker.description ? (
                  <p className="mt-0.5 line-clamp-2 text-xs leading-5 text-foreground-secondary">
                    {blocker.description}
                  </p>
                ) : null}
              </div>
            ))}
            {blockers.length > 3 ? (
              <button
                type="button"
                onClick={() => onTabChange("actions")}
                className="w-full text-left font-mono text-[11px] uppercase tracking-widest text-muted-foreground transition-colors hover:text-foreground-secondary"
              >
                +{blockers.length - 3} more in Actions
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* Deploy + assets */}
      <div className="solid-surface rounded-xl p-4">
        <div className="flex items-center justify-between gap-2">
          <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-accent">
            Deploy &amp; assets
          </p>
          <DeploymentStatusBadge status={deploymentStatus} />
        </div>
        <button
          type="button"
          onClick={() => onTabChange("deploy")}
          className="mt-3 min-h-11 w-full rounded-lg border border-border bg-background px-3 py-2 text-left text-xs font-semibold text-foreground-secondary transition-colors hover:border-accent/40 hover:text-foreground"
        >
          {deploymentStatusLabel(deploymentStatus)}
        </button>
        <div className="mt-3">
          <AssetQuickLinks
            business={business}
            executionStatus={executionStatus}
            compact
          />
        </div>
      </div>
    </aside>
  );
}
