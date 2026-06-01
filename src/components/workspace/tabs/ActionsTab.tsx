import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { BusinessExecutionStatus } from "@/types/execution-ui";

type ActionsTabProps = {
  business: DashboardBusiness;
  executionStatus?: BusinessExecutionStatus | null;
};

type UnifiedAction = {
  id: string;
  title: string;
  description: string;
  owner: "founder" | "bucks_ai";
  urgency: "critical" | "high" | "medium" | "low";
  category: "approval" | "blocker" | "next_action";
  dependency?: string;
};

function buildUnifiedActions(
  business: DashboardBusiness,
  executionStatus?: BusinessExecutionStatus | null
): UnifiedAction[] {
  const actions: UnifiedAction[] = [];

  // Human-required approvals (highest urgency)
  const humanItems =
    business.humanActionItems ??
    business.humanActions.map((title) => ({
      title,
      business: business.name,
      reason: "Founder approval required before execution continues.",
      status: "Needs review",
    }));

  for (const [i, action] of humanItems.entries()) {
    actions.push({
      id: `approval-${i}`,
      title: action.title,
      description: action.reason,
      owner: "founder",
      urgency: "critical",
      category: "approval",
    });
  }

  // Blockers
  for (const blocker of executionStatus?.blockers ?? []) {
    actions.push({
      id: `blocker-${blocker.id}`,
      title: blocker.title,
      description: blocker.description ?? "Resolve this blocker to continue.",
      owner: blocker.owner,
      urgency: "high",
      category: "blocker",
    });
  }

  // Next actions (founder first)
  for (const action of executionStatus?.nextActions ?? []) {
    actions.push({
      id: `next-${action.id}`,
      title: action.title,
      description: action.description ?? "",
      owner: action.actor,
      urgency: action.priority === "high" ? "high" : action.priority === "low" ? "low" : "medium",
      category: "next_action",
    });
  }

  return actions;
}

const categoryBadge: Record<string, string> = {
  approval: "border-warning/30 bg-warning/10 text-warning",
  blocker: "border-error/30 bg-error/10 text-error",
  next_action: "border-accent/30 bg-accent/10 text-accent",
};

const categoryLabel: Record<string, string> = {
  approval: "Approval needed",
  blocker: "Blocker",
  next_action: "Next action",
};

const ownerLabel: Record<string, string> = {
  founder: "Needs you",
  bucks_ai: "bucks.ai",
};

const ownerStyle: Record<string, string> = {
  founder: "border-warning/25 bg-warning/10 text-warning",
  bucks_ai: "border-accent/25 bg-accent/10 text-accent",
};

export function ActionsTab({ business, executionStatus }: ActionsTabProps) {
  const actions = buildUnifiedActions(business, executionStatus);

  if (actions.length === 0) {
    return (
      <div className="rounded-lg border border-border bg-surface p-8 text-center">
        <p className="font-mono text-xs uppercase tracking-[0.24em] text-muted">
          No pending actions
        </p>
        <p className="mt-2 text-sm text-muted">
          All current actions are complete or no inputs are needed.
        </p>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      {actions.map((action) => (
        <div
          key={action.id}
          className={`rounded-lg border bg-surface p-4 ${
            action.category === "approval"
              ? "border-warning/20"
              : action.category === "blocker"
                ? "border-error/20"
                : "border-border"
          }`}
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span
                  className={`rounded border px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest ${
                    categoryBadge[action.category]
                  }`}
                >
                  {categoryLabel[action.category]}
                </span>
                <h3 className="text-sm font-medium text-foreground">
                  {action.title}
                </h3>
              </div>
              {action.description ? (
                <p className="mt-1.5 text-xs leading-5 text-secondary">
                  {action.description}
                </p>
              ) : null}
            </div>
            <span
              className={`shrink-0 rounded border px-2 py-1 font-mono text-[10px] uppercase tracking-widest ${
                ownerStyle[action.owner]
              }`}
            >
              {ownerLabel[action.owner]}
            </span>
          </div>
        </div>
      ))}
    </div>
  );
}
