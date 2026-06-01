import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import {
  DeploymentStatusBadge,
  deploymentStatusLabel,
} from "@/components/deployment/DeploymentStatusBadge";
import type { BusinessExecutionStatus } from "@/types/execution-ui";
import type { DeploymentStatus } from "@/types/deployment-ui";
import { AssetQuickLinks } from "@/components/workspace/AssetQuickLinks";
import { CompactActivityCenter } from "@/components/workspace/CompactActivityCenter";
import { CompactToolQueue } from "@/components/workspace/CompactToolQueue";
import { resolvePrimaryNextAction } from "@/components/workspace/next-action";
import { ResearchRailCard } from "@/components/research/ResearchRailCard";
import { ValidationRailCard } from "@/components/validation/ValidationRailCard";
import { OperatingTeamRailCard } from "@/components/agents/OperatingTeamRailCard";
import type { WorkspaceAgentState } from "@/components/workspace/next-action";

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
  const nextActions = executionStatus?.nextActions ?? [];
  const blockers = executionStatus?.blockers ?? [];
  const pendingApprovals =
    business.humanActionItems ?? [];
  const primaryAction = resolvePrimaryNextAction(business, executionStatus, agentState);
  const deploymentStatus = deploymentStatusFromBusiness(business, executionStatus);

  return (
    <aside className="space-y-4">
      <div className="rounded-lg border border-[#F59E0B]/25 bg-[#0F0F0F] p-4">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#FCD34D]">
          Required next
        </p>
        <button
          type="button"
          onClick={() => onTabChange(primaryAction.target)}
          className="mt-3 w-full rounded border border-[#F59E0B]/20 bg-[#F59E0B]/8 px-3 py-2.5 text-left transition-colors hover:border-[#F59E0B]/40"
        >
          <p className="text-xs font-semibold text-[#F0F0F0]">
            {primaryAction.label}
          </p>
          <p className="mt-1 text-xs leading-5 text-[#FDE68A]">
            {primaryAction.description}
          </p>
        </button>
      </div>

      <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
        <div className="flex items-center justify-between gap-2">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
            Deploy
          </p>
          <DeploymentStatusBadge status={deploymentStatus} />
        </div>
        <button
          type="button"
          onClick={() => onTabChange("deploy")}
          className="mt-3 w-full rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2 text-left text-xs font-semibold text-[#D4D4D4] transition-colors hover:border-[#4F46E5]/45"
        >
          {deploymentStatusLabel(deploymentStatus)}
        </button>
      </div>

      <ValidationRailCard
        businessId={business.id}
        onOpenValidation={() => onTabChange("validation")}
      />

      <ResearchRailCard
        businessId={business.id}
        onOpenResearch={() => onTabChange("research")}
      />

      <OperatingTeamRailCard
        businessId={business.id}
        onOpenTeam={() => onTabChange("team")}
      />

      {/* Next action */}
      {nextActions.length > 0 ? (
        <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
            Next action
          </p>
          <div className="mt-3 space-y-2">
            {nextActions.slice(0, 3).map((action) => (
              <div
                key={action.id}
                className="flex items-start justify-between gap-2 rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2.5"
              >
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-[#F0F0F0]">
                    {action.title}
                  </p>
                  <p className="mt-0.5 font-mono text-[10px] uppercase tracking-widest text-[#444]">
                    {action.actor === "founder" ? "Needs you" : "bucks.ai"}
                  </p>
                </div>
                {action.actor === "founder" ? (
                  <span className="shrink-0 rounded border border-[#F59E0B]/30 bg-[#F59E0B]/10 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest text-[#FCD34D]">
                    You
                  </span>
                ) : (
                  <span className="shrink-0 rounded border border-[#4F46E5]/30 bg-[#4F46E5]/10 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest text-[#A5B4FC]">
                    Auto
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Blockers */}
      {blockers.length > 0 ? (
        <div className="rounded-lg border border-[#EF4444]/20 bg-[#0F0F0F] p-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#FCA5A5]">
            Blockers
          </p>
          <div className="mt-3 space-y-2">
            {blockers.slice(0, 3).map((blocker) => (
              <div
                key={blocker.id}
                className="rounded border border-[#EF4444]/20 bg-[#EF4444]/5 px-3 py-2"
              >
                <p className="text-xs font-medium text-[#F0F0F0]">
                  {blocker.title}
                </p>
                {blocker.description ? (
                  <p className="mt-0.5 text-xs leading-5 text-[#888]">
                    {blocker.description}
                  </p>
                ) : null}
              </div>
            ))}
            {blockers.length > 3 ? (
              <button
                type="button"
                onClick={() => onTabChange("actions")}
                className="w-full text-left font-mono text-[10px] uppercase tracking-widest text-[#444] transition-colors hover:text-[#888]"
              >
                +{blockers.length - 3} more
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* Pending approvals */}
      {pendingApprovals.length > 0 ? (
        <div className="rounded-lg border border-[#F59E0B]/20 bg-[#0F0F0F] p-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#FCD34D]">
            Pending approvals
          </p>
          <div className="mt-3 space-y-2">
            {pendingApprovals.slice(0, 3).map((action) => (
              <button
                key={`${action.business}-${action.title}`}
                type="button"
                onClick={() => onTabChange("actions")}
                className="w-full rounded border border-[#F59E0B]/20 bg-[#F59E0B]/5 px-3 py-2 text-left transition-colors hover:border-[#F59E0B]/40"
              >
                <p className="text-xs font-medium text-[#F0F0F0]">
                  {action.title}
                </p>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
        <div className="flex items-center justify-between">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
            Tool queue
          </p>
          <button
            type="button"
            onClick={() => onTabChange("tools")}
            className="font-mono text-[10px] uppercase tracking-widest text-[#444] transition-colors hover:text-[#888]"
          >
            All
          </button>
        </div>
        <div className="mt-3">
          <CompactToolQueue
            business={business}
            maxRows={3}
            onOpenTools={() => onTabChange("tools")}
          />
        </div>
      </div>

      {/* Key assets */}
      <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
          Assets
        </p>
        <div className="mt-3">
          <AssetQuickLinks
            business={business}
            executionStatus={executionStatus}
            compact
          />
        </div>
      </div>

      {/* Recent activity */}
      <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
        <div className="flex items-center justify-between">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
            Recent activity
          </p>
          <button
            type="button"
            onClick={() => onTabChange("activity")}
            className="font-mono text-[10px] uppercase tracking-widest text-[#444] transition-colors hover:text-[#888]"
          >
            All
          </button>
        </div>
        <div className="mt-3">
          <CompactActivityCenter
            business={business}
            executionStatus={executionStatus}
            maxRows={3}
            compact
          />
        </div>
      </div>
    </aside>
  );
}
