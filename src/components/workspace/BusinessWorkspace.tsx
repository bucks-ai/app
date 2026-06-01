"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { BusinessExecutionStatus } from "@/types/execution-ui";
import {
  fetchBusinessExecutionStatus,
  fetchExecutionTimeline,
} from "@/lib/execution-client";
import { fetchAgentRegistry, fetchAgentRuns } from "@/lib/agents-client";
import { WorkspaceHeader } from "@/components/workspace/WorkspaceHeader";
import { PrimaryActionStrip } from "@/components/workspace/PrimaryActionStrip";
import { WorkspaceTabs } from "@/components/workspace/WorkspaceTabs";
import type { TabKey } from "@/components/workspace/WorkspaceTabs";
import { WorkspaceSidebar } from "@/components/workspace/WorkspaceSidebar";
import { WorkspaceRightRail } from "@/components/workspace/WorkspaceRightRail";
import { WorkspaceDrawer } from "@/components/workspace/WorkspaceDrawer";
import {
  resolvePrimaryNextAction,
  type WorkspaceAgentState,
} from "@/components/workspace/next-action";
import { OverviewTab } from "@/components/workspace/tabs/OverviewTab";
import { ResearchTab } from "@/components/workspace/tabs/ResearchTab";
import { ActionsTab } from "@/components/workspace/tabs/ActionsTab";
import { BuildTab } from "@/components/workspace/tabs/BuildTab";
import { DeployTab } from "@/components/workspace/tabs/DeployTab";
import { ValidationTab } from "@/components/workspace/tabs/ValidationTab";
import { OperatingTeamTab } from "@/components/workspace/tabs/OperatingTeamTab";
import { ToolsTab } from "@/components/workspace/tabs/ToolsTab";
import { ActivityTab } from "@/components/workspace/tabs/ActivityTab";
import { SettingsTab } from "@/components/workspace/tabs/SettingsTab";

type BusinessWorkspaceProps = {
  business: DashboardBusiness;
  initialExecutionStatus?: BusinessExecutionStatus | null;
};

function resolveInitialTab(searchParam: string | null): TabKey {
  const valid: TabKey[] = [
    "overview",
    "research",
    "actions",
    "build",
    "deploy",
    "validation",
    "team",
    "tools",
    "activity",
    "settings",
  ];
  if (searchParam && valid.includes(searchParam as TabKey)) {
    return searchParam as TabKey;
  }
  return "overview";
}

export function BusinessWorkspace({
  business,
  initialExecutionStatus,
}: BusinessWorkspaceProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [activeTab, setActiveTab] = useState<TabKey>(
    resolveInitialTab(searchParams.get("tab"))
  );
  const [blueprintOpen, setBlueprintOpen] = useState(false);
  const [executionStatus, setExecutionStatus] =
    useState<BusinessExecutionStatus | null>(initialExecutionStatus ?? null);
  const [agentState, setAgentState] = useState<WorkspaceAgentState>({
    registryLoaded: false,
  });

  // Sync tab to URL
  const handleTabChange = useCallback(
    (tab: TabKey) => {
      setActiveTab(tab);
      const params = new URLSearchParams(searchParams.toString());
      params.set("tab", tab);
      router.replace(`?${params.toString()}`, { scroll: false });
    },
    [router, searchParams]
  );

  // Load fresh execution status after initial render
  useEffect(() => {
    async function load() {
      const result = await fetchBusinessExecutionStatus(business.id);
      if (!result.ok) return;

      const timelineResult = await fetchExecutionTimeline(business.id);
      const timeline =
        timelineResult.ok && timelineResult.data.length > 0
          ? timelineResult.data
          : result.data.timeline;

      setExecutionStatus({ ...result.data, timeline });
    }

    void load();
  }, [business.id]);

  // Load compact agent state for primary next-action decisions
  useEffect(() => {
    let ignore = false;

    async function loadAgents() {
      const [registryResult, runsResult] = await Promise.all([
        fetchAgentRegistry(business.id),
        fetchAgentRuns(business.id),
      ]);

      if (ignore) return;

      if (!registryResult.ok) {
        setAgentState({
          registryLoaded: false,
          agentRunsSchemaMissing:
            runsResult.ok ? Boolean(runsResult.warning) : runsResult.code === "agent_runs_schema_missing",
        });
        return;
      }

      setAgentState({
        registryLoaded: true,
        totalAgents: registryResult.data.summary.totalAgents,
        activeCount: registryResult.data.summary.activeCount,
        completedCount: registryResult.data.summary.completedCount,
        blockedCount: registryResult.data.summary.blockedCount,
        waitingCount: registryResult.data.summary.waitingCount,
        monitoringCount: registryResult.data.summary.monitoringCount,
        runCount: runsResult.ok ? runsResult.data.summary.totalRuns : 0,
        agentRunsSchemaMissing:
          runsResult.ok ? Boolean(runsResult.warning) : runsResult.code === "agent_runs_schema_missing",
      });
    }

    void loadAgents();

    return () => {
      ignore = true;
    };
  }, [business.id]);

  const pendingApprovalCount =
    business.humanActionItems?.length ?? business.humanActions.length;
  const blockerCount = executionStatus?.blockers?.length ?? 0;
  const actionCount = pendingApprovalCount + blockerCount;
  const primaryAction = resolvePrimaryNextAction(business, executionStatus, agentState);
  const badgeCounts = { actions: actionCount };

  const activeTabContent =
    activeTab === "overview" ? (
      <OverviewTab
        business={business}
        executionStatus={executionStatus}
        onTabChange={handleTabChange}
        onBlueprintOpen={() => setBlueprintOpen(true)}
      />
    ) : activeTab === "actions" ? (
      <ActionsTab business={business} executionStatus={executionStatus} />
    ) : activeTab === "research" ? (
      <ResearchTab business={business} />
    ) : activeTab === "build" ? (
      <BuildTab business={business} />
    ) : activeTab === "deploy" ? (
      <DeployTab business={business} />
    ) : activeTab === "validation" ? (
      <ValidationTab business={business} />
    ) : activeTab === "team" ? (
      <OperatingTeamTab business={business} />
    ) : activeTab === "tools" ? (
      <ToolsTab
        business={business}
        businessId={business.id}
        businessName={business.name}
      />
    ) : activeTab === "activity" ? (
      <ActivityTab business={business} executionStatus={executionStatus} />
    ) : activeTab === "settings" ? (
      <SettingsTab business={business} />
    ) : null;

  return (
    <div className="flex min-h-screen flex-col overflow-x-hidden bg-background pt-[69px]">
      <div className="flex min-w-0 flex-1">
        {/* Desktop left navigation */}
        <WorkspaceSidebar
          activeTab={activeTab}
          business={business}
          executionStatus={executionStatus}
          badgeCounts={badgeCounts}
          onTabChange={handleTabChange}
        />

        {/* Main column: sticky command bar + scrolling content */}
        <div className="flex min-w-0 flex-1 flex-col">
          <div
            className="sticky top-[69px] z-30 border-b border-border backdrop-blur"
            style={{ background: "var(--surface-glass)" }}
          >
            <WorkspaceHeader
              business={business}
              executionStatus={executionStatus}
              onBlueprintOpen={() => setBlueprintOpen(true)}
            />

            {/* Primary next action — desktop */}
            <div className="hidden border-t border-border-subtle lg:block">
              <PrimaryActionStrip
                business={business}
                executionStatus={executionStatus}
                agentState={agentState}
                onTabChange={handleTabChange}
              />
            </div>

            {/* Tabs — mobile / tablet */}
            <div className="border-t border-border-subtle lg:hidden">
              <WorkspaceTabs
                activeTab={activeTab}
                onTabChange={handleTabChange}
                badgeCounts={badgeCounts}
              />
            </div>
          </div>

          <main className="min-w-0 flex-1 px-4 py-5 pb-24 sm:px-6 lg:px-8 lg:pb-8">
            <div className="mx-auto max-w-5xl">{activeTabContent}</div>
          </main>
        </div>

        {/* Status rail — wide desktop only */}
        <aside className="hidden w-80 shrink-0 border-l border-border 2xl:block">
          <div className="sticky top-[69px] max-h-[calc(100vh-69px)] overflow-y-auto p-4">
            <WorkspaceRightRail
              business={business}
              executionStatus={executionStatus}
              agentState={agentState}
              onTabChange={handleTabChange}
            />
          </div>
        </aside>
      </div>

      {/* Mobile sticky bottom action bar */}
      <div
        className="fixed inset-x-0 bottom-0 z-40 border-t border-border px-3 py-2.5 backdrop-blur lg:hidden"
        style={{ background: "var(--surface-glass)" }}
      >
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => handleTabChange(primaryAction.target)}
            className="flex min-w-0 flex-1 items-center gap-2 rounded-lg border border-warning/35 bg-warning/10 px-3 py-2 text-left"
          >
            <span className="block min-w-0">
              <span className="block font-mono text-[10px] uppercase tracking-[0.18em] text-warning">
                Next action
              </span>
              <span className="block truncate text-xs font-semibold text-foreground">
                {primaryAction.label}
              </span>
            </span>
          </button>
          <button
            type="button"
            onClick={() => handleTabChange("activity")}
            className="shrink-0 rounded-lg border border-border bg-elevated px-3 py-2.5 font-mono text-[11px] uppercase tracking-[0.18em] text-secondary"
          >
            Activity
          </button>
        </div>
      </div>

      {/* Blueprint drawer */}
      <WorkspaceDrawer
        open={blueprintOpen}
        onClose={() => setBlueprintOpen(false)}
        title="Blueprint"
      >
        <div className="space-y-4">
          <p className="text-sm leading-7 text-secondary">
            {business.blueprintSummary ??
              "No blueprint summary is available for this project."}
          </p>

          {business.nextActions.length > 0 ? (
            <div>
              <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
                Next autonomous actions
              </p>
              <ul className="space-y-1.5">
                {business.nextActions.map((action, i) => (
                  <li
                    key={i}
                    className="rounded-lg border border-border bg-elevated px-3 py-2 text-xs text-secondary"
                  >
                    {action}
                  </li>
                ))}
              </ul>
            </div>
          ) : null}
        </div>
      </WorkspaceDrawer>
    </div>
  );
}
