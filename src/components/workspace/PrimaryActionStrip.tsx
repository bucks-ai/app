import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { BusinessExecutionStatus } from "@/types/execution-ui";

type TabKey =
  | "overview"
  | "actions"
  | "build"
  | "deploy"
  | "tools"
  | "activity"
  | "settings";

type PrimaryActionStripProps = {
  business: DashboardBusiness;
  executionStatus?: BusinessExecutionStatus | null;
  onTabChange: (tab: TabKey) => void;
};

type ResolvedAction = {
  label: string;
  description: string;
  tab: TabKey;
  urgency: "critical" | "high" | "medium";
};

function resolveNextAction(
  business: DashboardBusiness,
  executionStatus?: BusinessExecutionStatus | null
): ResolvedAction {
  const humanActions =
    business.humanActionItems ?? [];
  const blockers = executionStatus?.blockers ?? [];
  const nextActions = executionStatus?.nextActions ?? [];

  // Pending human approvals are highest urgency
  if (humanActions.length > 0) {
    const action = humanActions[0];
    const title = action.title.toLowerCase();
    const isGitHub = title.includes("github");
    const isVercel = title.includes("vercel");
    return {
      label: action.title,
      description: action.reason,
      tab: isVercel ? "deploy" : isGitHub ? "build" : "actions",
      urgency: "critical",
    };
  }

  // Active blockers
  if (blockers.length > 0) {
    const blocker = blockers[0];
    return {
      label: blocker.title,
      description: blocker.description ?? "Resolve this blocker to continue.",
      tab: "actions",
      urgency: "high",
    };
  }

  // Next actions from execution status
  const founderAction = nextActions.find((a) => a.actor === "founder");
  if (founderAction) {
    const title = founderAction.title.toLowerCase();
    const tab: TabKey = title.includes("github")
      ? "build"
      : title.includes("vercel") || title.includes("deploy")
        ? "deploy"
        : title.includes("tool") || title.includes("permission")
          ? "tools"
          : "actions";
    return {
      label: founderAction.title,
      description: founderAction.description ?? "Your input is needed.",
      tab,
      urgency: "high",
    };
  }

  // Check GitHub status
  const phase = executionStatus?.currentPhase;
  if (phase === "github" || phase === "scaffold") {
    return {
      label: "Create GitHub repository",
      description: "Repository creation is the next milestone.",
      tab: "build",
      urgency: "medium",
    };
  }

  if (phase === "vercel" || phase === "deployment") {
    return {
      label: "Set up Vercel deployment",
      description: "Connect the project for deployment.",
      tab: "deploy",
      urgency: "medium",
    };
  }

  if (phase === "permissions") {
    return {
      label: "Review tool permissions",
      description: "Approve external tool access before execution continues.",
      tab: "tools",
      urgency: "medium",
    };
  }

  // Autonomous next action
  const autoAction = nextActions.find((a) => a.actor === "bucks_ai");
  if (autoAction) {
    return {
      label: autoAction.title,
      description: autoAction.description ?? "bucks.ai is handling this.",
      tab: "activity",
      urgency: "medium",
    };
  }

  return {
    label: "Review execution status",
    description: "Check current progress and milestones.",
    tab: "overview",
    urgency: "medium",
  };
}

const urgencyStyles = {
  critical:
    "border-[#F59E0B]/40 bg-[#F59E0B]/8 hover:border-[#F59E0B]/60",
  high: "border-[#4F46E5]/40 bg-[#4F46E5]/8 hover:border-[#4F46E5]/60",
  medium: "border-[#1C1C1C] bg-[#141414] hover:border-[#4F46E5]/30",
};

const urgencyCtaStyles = {
  critical: "bg-[#F59E0B] text-[#0A0A0A] hover:bg-[#FBBF24]",
  high: "bg-[#4F46E5] text-[#F0F0F0] hover:bg-[#6366F1]",
  medium: "bg-[#1C1C1C] text-[#D4D4D4] hover:bg-[#242424]",
};

export function PrimaryActionStrip({
  business,
  executionStatus,
  onTabChange,
}: PrimaryActionStripProps) {
  const action = resolveNextAction(business, executionStatus);
  const blockerCount = executionStatus?.blockers?.length ?? 0;
  const pendingApprovals =
    (business.humanActionItems?.length ?? business.humanActions.length);
  const latestActivity = executionStatus?.timeline?.[0];

  return (
    <div className="border-b border-[#1C1C1C] bg-[#080808] px-4 py-2.5 sm:px-6">
      <div className="flex flex-wrap items-center gap-2.5">
        {/* Primary CTA */}
        <button
          type="button"
          onClick={() => onTabChange(action.tab)}
          className={`flex items-center gap-2.5 rounded border px-3 py-2 transition-colors ${urgencyStyles[action.urgency]}`}
        >
          <span className="max-w-xs truncate text-left text-sm font-medium text-[#F0F0F0]">
            {action.label}
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
