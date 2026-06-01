"use client";

import { CommandMenuHint } from "@/components/workspace/CommandMenuHint";
import { TABS, type TabKey } from "@/components/workspace/WorkspaceTabs";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { BusinessExecutionStatus } from "@/types/execution-ui";

type WorkspaceSidebarProps = {
  activeTab: TabKey;
  business: DashboardBusiness;
  executionStatus?: BusinessExecutionStatus | null;
  badgeCounts?: Partial<Record<TabKey, number>>;
  onTabChange: (tab: TabKey) => void;
};

const tabMeta: Record<
  TabKey,
  {
    description: string;
    group: "Plan" | "Build" | "Operate";
    marker: string;
  }
> = {
  overview: {
    description: "Control center",
    group: "Plan",
    marker: "01",
  },
  research: {
    description: "Market and risk map",
    group: "Plan",
    marker: "02",
  },
  actions: {
    description: "Approvals and blockers",
    group: "Plan",
    marker: "03",
  },
  build: {
    description: "GitHub and scaffold",
    group: "Build",
    marker: "04",
  },
  deploy: {
    description: "Vercel and live app",
    group: "Build",
    marker: "05",
  },
  validation: {
    description: "Leads and feedback",
    group: "Operate",
    marker: "06",
  },
  team: {
    description: "Agent registry",
    group: "Operate",
    marker: "07",
  },
  tools: {
    description: "Permissions",
    group: "Operate",
    marker: "08",
  },
  activity: {
    description: "Runs and logs",
    group: "Operate",
    marker: "09",
  },
  settings: {
    description: "Boundaries",
    group: "Operate",
    marker: "10",
  },
};

function phaseLabel(phase?: string | null) {
  if (!phase) return "Blueprint";

  return phase
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function WorkspaceSidebar({
  activeTab,
  business,
  executionStatus,
  badgeCounts,
  onTabChange,
}: WorkspaceSidebarProps) {
  const progress = executionStatus?.progressPercent ?? 0;
  const phase = phaseLabel(executionStatus?.currentPhase);
  const groups: Array<"Plan" | "Build" | "Operate"> = ["Plan", "Build", "Operate"];

  return (
    <aside className="hidden w-72 shrink-0 border-r border-border lg:block">
      <div className="sticky top-[69px] flex max-h-[calc(100vh-69px)] flex-col gap-4 overflow-y-auto px-3 py-4">
        <div className="rounded-xl border border-border bg-elevated p-3.5">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
            Workspace
          </p>
          <h2 className="mt-1.5 truncate text-sm font-semibold text-foreground">
            {business.name}
          </h2>
          <p className="mt-1 truncate font-mono text-[10px] uppercase tracking-widest text-muted">
            {phase} &middot; {progress}%
          </p>
        </div>

        <nav aria-label="Workspace sections" className="space-y-4">
          {groups.map((group) => (
            <div key={group}>
              <p className="px-2 font-mono text-[10px] uppercase tracking-[0.22em] text-muted">
                {group}
              </p>
              <div className="mt-2 space-y-1">
                {TABS.filter((tab) => tabMeta[tab.key].group === group).map((tab) => {
                  const isActive = activeTab === tab.key;
                  const count = badgeCounts?.[tab.key] ?? 0;
                  const meta = tabMeta[tab.key];

                  return (
                    <button
                      key={tab.key}
                      type="button"
                      onClick={() => onTabChange(tab.key)}
                      className={`flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left transition-colors ${
                        isActive
                          ? "border-accent/45 bg-accent/12 text-foreground"
                          : "border-transparent text-secondary hover:border-border hover:bg-elevated hover:text-foreground"
                      }`}
                    >
                      <span
                        className={`flex h-7 w-8 shrink-0 items-center justify-center rounded-md border font-mono text-[10px] ${
                          isActive
                            ? "border-accent/40 bg-accent/15 text-accent"
                            : "border-border bg-background text-muted"
                        }`}
                      >
                        {meta.marker}
                      </span>
                      <span className="min-w-0 flex-1">
                        <span className="flex items-center gap-2">
                          <span className="truncate text-sm font-semibold">{tab.label}</span>
                          {count > 0 ? (
                            <span className="rounded-full bg-warning/20 px-1.5 py-0.5 font-mono text-[10px] text-warning">
                              {count}
                            </span>
                          ) : null}
                        </span>
                        <span className="mt-0.5 block truncate text-xs text-muted">
                          {meta.description}
                        </span>
                      </span>
                    </button>
                  );
                })}
              </div>
            </div>
          ))}
        </nav>

        <div className="mt-auto">
          <CommandMenuHint onTabChange={onTabChange} />
        </div>
      </div>
    </aside>
  );
}
