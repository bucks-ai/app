import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { BusinessExecutionStatus } from "@/types/execution-ui";
import {
  resolvePrimaryNextAction,
  type WorkspaceAgentState,
  type WorkspaceActionTarget,
} from "@/components/workspace/next-action";

type PrimaryActionStripProps = {
  business: DashboardBusiness;
  executionStatus?: BusinessExecutionStatus | null;
  agentState?: WorkspaceAgentState;
  onTabChange: (tab: WorkspaceActionTarget) => void;
};

const urgencyStyles = {
  critical:
    "border-[#F59E0B]/40 bg-[#F59E0B]/8 hover:border-[#F59E0B]/60",
  high: "border-[#4F46E5]/40 bg-[#4F46E5]/8 hover:border-[#4F46E5]/60",
  medium: "border-[#1C1C1C] bg-[#141414] hover:border-[#4F46E5]/30",
  low: "border-[#1C1C1C] bg-[#0F0F0F] hover:border-[#4F46E5]/30",
};

const urgencyCtaStyles = {
  critical: "bg-[#F59E0B] text-[#0A0A0A] hover:bg-[#FBBF24]",
  high: "bg-[#4F46E5] text-[#F0F0F0] hover:bg-[#6366F1]",
  medium: "bg-[#1C1C1C] text-[#D4D4D4] hover:bg-[#242424]",
  low: "bg-[#1C1C1C] text-[#888] hover:bg-[#242424]",
};

export function PrimaryActionStrip({
  business,
  executionStatus,
  agentState,
  onTabChange,
}: PrimaryActionStripProps) {
  const action = resolvePrimaryNextAction(business, executionStatus, agentState);
  const blockerCount = executionStatus?.blockers?.length ?? 0;
  const pendingApprovals =
    business.humanActionItems?.length ?? business.humanActions.length;
  const latestActivity = executionStatus?.timeline?.[0];

  return (
    <div className="border-b border-[#1C1C1C] bg-[#080808]/95 px-4 py-2.5 backdrop-blur sm:px-6">
      <div className="flex flex-wrap items-center gap-2.5 lg:flex-nowrap">
        {/* Primary CTA */}
        <button
          type="button"
          onClick={() => onTabChange(action.target)}
          className={`flex min-w-0 flex-1 items-center justify-between gap-3 rounded border px-3 py-2 text-left transition-colors sm:flex-none sm:justify-start ${urgencyStyles[action.urgency]}`}
        >
          <span className="min-w-0">
            <span className="block truncate text-sm font-semibold text-[#F0F0F0]">
              {action.label}
            </span>
            <span className="hidden max-w-sm truncate text-xs text-[#777] md:block">
              {action.description}
            </span>
          </span>
          <span
            className={`shrink-0 rounded px-2 py-0.5 text-xs font-semibold transition-colors ${urgencyCtaStyles[action.urgency]}`}
          >
            {action.urgency === "critical"
              ? "Needs you"
              : action.urgency === "high"
                ? "Act now"
                : "View"}
          </span>
        </button>

        {/* Secondary pills */}
        {pendingApprovals > 0 ? (
          <button
            type="button"
            onClick={() => onTabChange("actions")}
            className="flex items-center gap-1.5 rounded border border-[#F59E0B]/25 bg-[#F59E0B]/10 px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-widest text-[#FCD34D] transition-colors hover:border-[#F59E0B]/40"
          >
            {pendingApprovals} approval{pendingApprovals !== 1 ? "s" : ""}
          </button>
        ) : null}

        {blockerCount > 0 ? (
          <button
            type="button"
            onClick={() => onTabChange("actions")}
            className="flex items-center gap-1.5 rounded border border-[#EF4444]/25 bg-[#EF4444]/10 px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-widest text-[#FCA5A5] transition-colors hover:border-[#EF4444]/40"
          >
            {blockerCount} blocker{blockerCount !== 1 ? "s" : ""}
          </button>
        ) : null}

        {latestActivity ? (
          <button
            type="button"
            onClick={() => onTabChange("activity")}
            className="hidden items-center gap-1.5 rounded border border-[#1C1C1C] bg-[#0F0F0F] px-2.5 py-1.5 xl:flex"
          >
            <span className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
              Latest:
            </span>
            <span className="max-w-48 truncate text-xs text-[#888]">
              {latestActivity.title}
            </span>
          </button>
        ) : null}
      </div>
    </div>
  );
}
