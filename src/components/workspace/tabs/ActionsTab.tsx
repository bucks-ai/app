"use client";

import { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { BusinessExecutionStatus } from "@/types/execution-ui";
import type { HumanActionDecision } from "@/types/human-action-ui";
import { updateHumanAction } from "@/lib/human-action-client";
import { ApprovalsPanel } from "@/components/workspace/tabs/ApprovalsPanel";
import {
  resolveActionTarget,
  type ActionTarget,
} from "@/components/workspace/action-target";
import { TABS, type TabKey } from "@/components/workspace/WorkspaceTabs";

type ActionsTabProps = {
  business: DashboardBusiness;
  executionStatus?: BusinessExecutionStatus | null;
  onTabChange?: (tab: TabKey) => void;
};

type UnifiedAction = {
  id: string;
  title: string;
  description: string;
  owner: "founder" | "bucks_ai";
  urgency: "critical" | "high" | "medium" | "low";
  category: "approval" | "blocker" | "next_action";
  dependency?: string;
  // Present only for approvals backed by a human_required_actions row — those
  // are the ones the founder can decide inline.
  humanActionId?: string;
  target?: ActionTarget | null;
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
      id: undefined,
      title,
      business: business.name,
      reason: "Founder approval required before execution continues.",
      status: "Needs review",
    }));

  for (const [i, action] of humanItems.entries()) {
    actions.push({
      id: action.id ?? `approval-${i}`,
      title: action.title,
      description: action.reason,
      owner: "founder",
      urgency: "critical",
      category: "approval",
      humanActionId: action.id,
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
      target: resolveActionTarget(blocker.href, business.id),
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
      target: resolveActionTarget(action.href, business.id),
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

const decisionLabel: Record<HumanActionDecision, string> = {
  approve: "Approve",
  dismiss: "Dismiss",
};

export function ActionsTab({
  business,
  executionStatus,
  onTabChange,
}: ActionsTabProps) {
  const router = useRouter();
  const [decidedIds, setDecidedIds] = useState<string[]>([]);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  const actions = buildUnifiedActions(business, executionStatus).filter(
    (action) => !action.humanActionId || !decidedIds.includes(action.humanActionId)
  );

  async function handleDecision(id: string, decision: HumanActionDecision) {
    setPendingId(id);
    setError(null);

    const result = await updateHumanAction(id, decision);
    setPendingId(null);

    if (!result.ok) {
      setError(result.error);
      return;
    }

    // Drop it locally straight away, then refresh so the sidebar badge, the
    // right rail counts, and the execution status all agree.
    setDecidedIds((current) => [...current, id]);
    router.refresh();
  }

  if (actions.length === 0) {
    return (
      <div>
        <ApprovalsPanel />
        {error ? <DecisionError message={error} /> : null}
        <div className="solid-surface mt-5 rounded-lg p-8 text-center">
          <p className="font-mono text-xs uppercase tracking-[0.24em] text-muted-foreground">
            No pending actions
          </p>
          <p className="mt-2 text-sm text-muted-foreground">
            All current actions are complete or no inputs are needed.
          </p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-2">
      <ApprovalsPanel />
      {error ? <DecisionError message={error} /> : null}
      {actions.map((action) => (
        <div
          key={action.id}
          className={`rounded-lg border bg-surface/90 p-4 ${
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
                  className={`rounded border px-1.5 py-0.5 font-mono text-[11px] uppercase tracking-widest ${
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
                <p className="mt-1.5 text-xs leading-5 text-foreground-secondary">
                  {action.description}
                </p>
              ) : null}
            </div>
            <span
              className={`shrink-0 rounded border px-2 py-1 font-mono text-[11px] uppercase tracking-widest ${
                ownerStyle[action.owner]
              }`}
            >
              {ownerLabel[action.owner]}
            </span>
          </div>

          <ActionControls
            action={action}
            pending={pendingId === action.humanActionId}
            onDecide={handleDecision}
            onTabChange={onTabChange}
          />
        </div>
      ))}
    </div>
  );
}

function DecisionError({ message }: { message: string }) {
  return (
    <div
      role="alert"
      className="rounded-xl bg-error/10 p-4 text-xs leading-5 text-error"
    >
      {message}
    </div>
  );
}

const controlClass =
  "inline-flex min-h-11 items-center rounded-lg border px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest transition-colors disabled:opacity-50";

function ActionControls({
  action,
  pending,
  onDecide,
  onTabChange,
}: {
  action: UnifiedAction;
  pending: boolean;
  onDecide: (id: string, decision: HumanActionDecision) => void;
  onTabChange?: (tab: TabKey) => void;
}) {
  if (action.humanActionId) {
    const id = action.humanActionId;
    return (
      <div className="mt-3 flex flex-wrap gap-2">
        <button
          type="button"
          onClick={() => onDecide(id, "approve")}
          disabled={pending}
          className={`${controlClass} border-accent/30 bg-accent/12 text-accent-on-tint hover:bg-accent/20`}
        >
          {pending ? "Saving..." : decisionLabel.approve}
        </button>
        <button
          type="button"
          onClick={() => onDecide(id, "dismiss")}
          disabled={pending}
          className={`${controlClass} border-error/30 bg-error/10 text-error hover:bg-error/20`}
        >
          {decisionLabel.dismiss}
        </button>
      </div>
    );
  }

  const target = action.target;
  if (!target) return null;

  if (target.kind === "tab") {
    // No handler means this tab is rendered outside the workspace shell, so
    // there is nothing to switch to — better no control than a dead one.
    if (!onTabChange) return null;
    const tab = target.tab;
    return (
      <div className="mt-3">
        <button
          type="button"
          onClick={() => onTabChange(tab)}
          className={`${controlClass} border-border bg-background text-foreground-secondary hover:border-accent/40 hover:text-foreground`}
        >
          Open {TABS.find((entry) => entry.key === tab)?.label ?? tab}
        </button>
      </div>
    );
  }

  if (target.kind === "internal") {
    return (
      <div className="mt-3">
        <Link
          href={target.href}
          className={`${controlClass} border-border bg-background text-foreground-secondary hover:border-accent/40 hover:text-foreground`}
        >
          Open
        </Link>
      </div>
    );
  }

  return (
    <div className="mt-3">
      <a
        href={target.href}
        target="_blank"
        rel="noreferrer"
        className={`${controlClass} border-border bg-background text-foreground-secondary hover:border-accent/40 hover:text-foreground`}
      >
        Open externally
      </a>
    </div>
  );
}
