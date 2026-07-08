"use client";

import { useState, type FocusEvent } from "react";
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
  className?: string;
};

const urgencyStyles = {
  critical:
    "border-warning/35 bg-warning/10 shadow-[0_18px_70px_rgba(246,189,22,0.10)]",
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

const urgencyLabel = {
  critical: "Needs you",
  high: "Act now",
  medium: "Next up",
  low: "Queued",
};

export function PrimaryActionStrip({
  business,
  executionStatus,
  agentState,
  onTabChange,
  className = "",
}: PrimaryActionStripProps) {
  const [pinnedOpen, setPinnedOpen] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [focused, setFocused] = useState(false);
  const action = resolvePrimaryNextAction(business, executionStatus, agentState);
  const blockerCount = executionStatus?.blockers?.length ?? 0;
  const pendingApprovals =
    business.humanActionItems?.length ?? business.humanActions.length;
  const latestActivity = executionStatus?.timeline?.[0];
  const expanded = pinnedOpen || hovered || focused;

  function handleBlur(event: FocusEvent<HTMLDivElement>) {
    if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
      setFocused(false);
    }
  }

  return (
    <div className={`relative w-full ${className}`}>
      <div
        className="relative"
        onMouseEnter={() => setHovered(true)}
        onMouseLeave={() => setHovered(false)}
        onFocusCapture={() => setFocused(true)}
        onBlurCapture={handleBlur}
      >
        <div
          className={`flex min-h-9 min-w-0 items-center gap-2 rounded-lg border px-2 py-1.5 transition-[border-color,background-color,box-shadow] duration-200 ${urgencyStyles[action.urgency]}`}
        >
          <button
            type="button"
            onClick={() => setPinnedOpen((value) => !value)}
            aria-expanded={expanded}
            className="flex min-w-0 flex-1 items-center gap-2 rounded-md px-1.5 py-0.5 text-left outline-none transition-colors focus-visible:ring-2 focus-visible:ring-accent/60 motion-reduce:transition-none"
          >
            <span className="hidden rounded-md border border-warning/25 bg-background/60 px-2 py-0.5 font-mono text-[10px] uppercase tracking-widest text-warning sm:inline-flex">
              Next
            </span>
            <span className="min-w-0 flex-1">
              <span className="flex min-w-0 items-center gap-2">
                <span className="truncate text-xs font-semibold text-foreground">
                  {action.label}
                </span>
                <span className="hidden shrink-0 rounded-md border border-border bg-background/55 px-2 py-0.5 font-mono text-[9px] uppercase tracking-widest text-warning 2xl:inline-flex">
                  {urgencyLabel[action.urgency]}
                </span>
              </span>
              <span className="block truncate text-[10px] leading-3 text-muted">
                Hover or press for details
              </span>
            </span>
            <span
              aria-hidden="true"
              className={`shrink-0 text-xs text-muted transition-transform duration-200 motion-reduce:transition-none ${
                expanded ? "rotate-180" : ""
              }`}
            >
              &#8964;
            </span>
          </button>

          <div className="flex shrink-0 items-center gap-1.5">
            {pendingApprovals > 0 ? (
              <button
                type="button"
                onClick={() => onTabChange("actions")}
                className="hidden items-center rounded-md border border-warning/25 bg-warning/10 px-2 py-1 font-mono text-[9px] uppercase tracking-widest text-warning transition-colors hover:border-warning/45 2xl:inline-flex"
              >
                {pendingApprovals} approval{pendingApprovals !== 1 ? "s" : ""}
              </button>
            ) : null}
            <button
              type="button"
              onClick={() => onTabChange(action.target)}
              className={`rounded-md px-2.5 py-1.5 text-xs font-semibold transition-colors ${urgencyCtaStyles[action.urgency]}`}
            >
              Open
            </button>
          </div>
        </div>

        <div
          aria-hidden={!expanded}
          className={`absolute right-0 top-[calc(100%+0.5rem)] z-50 w-[min(42rem,calc(100vw-2rem))] rounded-xl border border-border bg-surface/95 p-3 shadow-[0_24px_90px_rgba(0,0,0,0.55)] backdrop-blur transition-[opacity,transform] duration-200 motion-reduce:transition-none ${
            expanded
              ? "pointer-events-auto translate-y-0 opacity-100"
              : "pointer-events-none -translate-y-1 opacity-0"
          }`}
        >
          <div className="grid gap-3 xl:grid-cols-[minmax(0,1fr)_auto] xl:items-center">
            <button
              type="button"
              onClick={() => onTabChange(action.target)}
              tabIndex={expanded ? 0 : -1}
              className={`flex min-w-0 items-center justify-between gap-3 rounded-lg border px-3.5 py-3 text-left transition-colors ${urgencyStyles[action.urgency]}`}
            >
              <span className="flex min-w-0 items-center gap-3">
                <span className="hidden rounded-md border border-warning/25 bg-background/65 px-2 py-1 font-mono text-[10px] uppercase tracking-widest text-warning sm:inline-flex">
                  {urgencyLabel[action.urgency]}
                </span>
                <span className="min-w-0">
                  <span className="block truncate text-sm font-semibold text-foreground">
                    {action.label}
                  </span>
                  <span className="block max-w-3xl truncate text-xs text-muted">
                    {action.description}
                  </span>
                </span>
              </span>
              <span
                className={`shrink-0 rounded-md px-2.5 py-1 text-xs font-semibold transition-colors ${urgencyCtaStyles[action.urgency]}`}
              >
                Open {action.target}
              </span>
            </button>

            <div className="flex min-w-0 flex-wrap items-center gap-2">
              {pendingApprovals > 0 ? (
                <button
                  type="button"
                  onClick={() => onTabChange("actions")}
                  tabIndex={expanded ? 0 : -1}
                  className="flex items-center gap-1.5 rounded-md border border-warning/25 bg-warning/10 px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-widest text-warning transition-colors hover:border-warning/40"
                >
                  {pendingApprovals} approval{pendingApprovals !== 1 ? "s" : ""}
                </button>
              ) : null}

              {blockerCount > 0 ? (
                <button
                  type="button"
                  onClick={() => onTabChange("actions")}
                  tabIndex={expanded ? 0 : -1}
                  className="flex items-center gap-1.5 rounded-md border border-error/25 bg-error/10 px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-widest text-error transition-colors hover:border-error/40"
                >
                  {blockerCount} blocker{blockerCount !== 1 ? "s" : ""}
                </button>
              ) : null}

              {latestActivity ? (
                <button
                  type="button"
                  onClick={() => onTabChange("activity")}
                  tabIndex={expanded ? 0 : -1}
                  className="flex min-w-0 items-center gap-1.5 rounded-md border border-border bg-background px-2.5 py-1.5"
                >
                  <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
                    Latest
                  </span>
                  <span className="max-w-56 truncate text-xs text-secondary">
                    {latestActivity.title}
                  </span>
                </button>
              ) : null}

              {pinnedOpen ? (
                <button
                  type="button"
                  onClick={() => setPinnedOpen(false)}
                  tabIndex={expanded ? 0 : -1}
                  className="rounded-md border border-border bg-background px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-widest text-muted transition-colors hover:text-secondary"
                >
                  Collapse
                </button>
              ) : null}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
