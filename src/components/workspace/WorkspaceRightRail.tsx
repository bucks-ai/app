import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import {
  DeploymentStatusBadge,
  deploymentStatusLabel,
} from "@/components/deployment/DeploymentStatusBadge";
import type { BusinessExecutionStatus } from "@/types/execution-ui";
import type { DeploymentStatus } from "@/types/deployment-ui";
import { AssetQuickLinks } from "@/components/workspace/AssetQuickLinks";
import {
  resolvePrimaryNextAction,
  type WorkspaceAgentState,
} from "@/components/workspace/next-action";

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
  agentState?: WorkspaceAgentState;
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
  agentState,
  onTabChange,
}: WorkspaceRightRailProps) {
  const blockers = executionStatus?.blockers ?? [];
  const pendingApprovals = business.humanActionItems ?? [];
  const primaryAction = resolvePrimaryNextAction(business, executionStatus, agentState);
  const deploymentStatus = deploymentStatusFromBusiness(business, executionStatus);
  const progress = executionStatus?.progressPercent ?? 0;

  return (
    <aside className="space-y-3">
      {/* Next action */}
      <button
        type="button"
        onClick={() => onTabChange(primaryAction.target)}
        className="block w-full rounded-xl border border-warning/30 bg-warning/10 p-4 text-left shadow-[var(--shadow-soft)] transition-colors hover:border-warning/50"
      >
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-warning">
          Next action
        </p>
        <p className="mt-2 text-sm font-semibold text-foreground">
          {primaryAction.label}
        </p>
        <p className="mt-1 line-clamp-2 text-xs leading-5 text-secondary">
          {primaryAction.description}
        </p>
      </button>

      {/* Progress snapshot */}
      <div className="rounded-xl border border-border bg-surface p-4 shadow-[var(--shadow-soft)]">
        <div className="flex items-center justify-between gap-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
            Progress
          </p>
          <span className="font-mono text-[10px] uppercase tracking-widest text-secondary">
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
            className="rounded-lg border border-warning/20 bg-warning/8 px-2.5 py-2 text-left transition-colors hover:border-warning/40"
          >
            <span className="block font-mono text-[10px] uppercase tracking-widest text-warning">
              Approvals
            </span>
            <span className="mt-1 block text-lg font-semibold text-foreground">
              {pendingApprovals.length}
            </span>
          </button>
          <button
            type="button"
            onClick={() => onTabChange("actions")}
            className="rounded-lg border border-error/20 bg-error/8 px-2.5 py-2 text-left transition-colors hover:border-error/40"
          >
            <span className="block font-mono text-[10px] uppercase tracking-widest text-error">
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
        <div className="rounded-xl border border-border bg-surface p-4 shadow-[var(--shadow-soft)]">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-error">
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
                  <p className="mt-0.5 line-clamp-2 text-xs leading-5 text-secondary">
                    {blocker.description}
                  </p>
                ) : null}
              </div>
            ))}
            {blockers.length > 3 ? (
              <button
                type="button"
                onClick={() => onTabChange("actions")}
                className="w-full text-left font-mono text-[10px] uppercase tracking-widest text-muted transition-colors hover:text-secondary"
              >
                +{blockers.length - 3} more in Actions
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* Deploy + assets */}
      <div className="rounded-xl border border-border bg-surface p-4 shadow-[var(--shadow-soft)]">
        <div className="flex items-center justify-between gap-2">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
            Deploy &amp; assets
          </p>
          <DeploymentStatusBadge status={deploymentStatus} />
        </div>
        <button
          type="button"
          onClick={() => onTabChange("deploy")}
          className="mt-3 w-full rounded-lg border border-border bg-background px-3 py-2 text-left text-xs font-semibold text-secondary transition-colors hover:border-accent/40 hover:text-foreground"
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
