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
    "border-warning/40 bg-warning/10 hover:border-warning/60",
  high: "border-accent/40 bg-accent/10 hover:border-accent/60",
  medium: "border-border bg-surface hover:border-accent/35",
  low: "border-border bg-surface hover:border-accent/35",
};

const urgencyCtaStyles = {
  critical: "bg-warning text-background hover:opacity-90",
  high: "bg-accent text-accent-contrast hover:bg-accent-hover",
  medium: "bg-elevated text-secondary hover:bg-border",
  low: "bg-elevated text-secondary hover:bg-border",
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
    <div className="px-4 py-2.5 sm:px-6">
      <div className="flex flex-col gap-2.5 lg:flex-row lg:items-center">
        <button
          type="button"
          onClick={() => onTabChange(action.target)}
          className={`flex min-w-0 flex-1 items-center justify-between gap-3 rounded-lg border px-3.5 py-2.5 text-left transition-colors ${urgencyStyles[action.urgency]}`}
        >
          <span className="flex min-w-0 items-center gap-3">
            <span className="hidden rounded-md border border-warning/25 bg-background/65 px-2 py-1 font-mono text-[10px] uppercase tracking-widest text-warning sm:inline-flex">
              Next
            </span>
            <span className="min-w-0">
              <span className="block truncate text-sm font-semibold text-foreground">
                {action.label}
              </span>
              <span className="hidden max-w-xl truncate text-xs text-muted md:block">
                {action.description}
              </span>
            </span>
          </span>
          <span
            className={`shrink-0 rounded-md px-2.5 py-1 text-xs font-semibold transition-colors ${urgencyCtaStyles[action.urgency]}`}
          >
            {action.urgency === "critical"
              ? "Needs you"
              : action.urgency === "high"
                ? "Act now"
                : "Open"}
          </span>
        </button>

        <div className="flex min-w-0 flex-wrap items-center gap-2">
          {pendingApprovals > 0 ? (
            <button
              type="button"
              onClick={() => onTabChange("actions")}
              className="flex items-center gap-1.5 rounded-md border border-warning/25 bg-warning/10 px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-widest text-warning transition-colors hover:border-warning/40"
            >
              {pendingApprovals} approval{pendingApprovals !== 1 ? "s" : ""}
            </button>
          ) : null}

          {blockerCount > 0 ? (
            <button
              type="button"
              onClick={() => onTabChange("actions")}
              className="flex items-center gap-1.5 rounded-md border border-error/25 bg-error/10 px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-widest text-error transition-colors hover:border-error/40"
            >
              {blockerCount} blocker{blockerCount !== 1 ? "s" : ""}
            </button>
          ) : null}

          {latestActivity ? (
            <button
              type="button"
              onClick={() => onTabChange("activity")}
              className="hidden min-w-0 items-center gap-1.5 rounded-md border border-border bg-surface px-2.5 py-1.5 xl:flex"
            >
              <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
                Latest
              </span>
              <span className="max-w-48 truncate text-xs text-secondary">
                {latestActivity.title}
              </span>
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
