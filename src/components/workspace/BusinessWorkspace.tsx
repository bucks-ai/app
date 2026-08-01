"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { BusinessExecutionStatus } from "@/types/execution-ui";
import {
  fetchBusinessExecutionStatus,
  fetchExecutionTimeline,
} from "@/lib/execution-client";
import { WorkspaceTabs } from "@/components/workspace/WorkspaceTabs";
import type { TabKey } from "@/components/workspace/WorkspaceTabs";
import { WorkspaceSidebar } from "@/components/workspace/WorkspaceSidebar";
import { WorkspaceRightRail } from "@/components/workspace/WorkspaceRightRail";
import { WorkspaceDrawer } from "@/components/workspace/WorkspaceDrawer";
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

  const pendingApprovalCount =
    business.humanActionItems?.length ?? business.humanActions.length;
  const blockerCount = executionStatus?.blockers?.length ?? 0;
  const actionCount = pendingApprovalCount + blockerCount;
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
    <div className="light-field flex min-h-screen flex-col overflow-x-hidden bg-background pt-[69px]">
      <div className="flex min-w-0 flex-1">
        {/* Desktop left navigation */}
        <WorkspaceSidebar
          activeTab={activeTab}
          business={business}
          executionStatus={executionStatus}
          badgeCounts={badgeCounts}
          onTabChange={handleTabChange}
        />

        {/* Main column: mobile tabs + scrolling content */}
        <div className="flex min-w-0 flex-1 flex-col">
          <div className="border-b border-border/70 bg-background/50 lg:hidden">
            <WorkspaceTabs
              activeTab={activeTab}
              onTabChange={handleTabChange}
              badgeCounts={badgeCounts}
            />
          </div>

          <main className="min-w-0 flex-1 px-4 py-5 pb-24 sm:px-6 lg:px-8 lg:pb-8">
            <div className="mx-auto max-w-5xl">{activeTabContent}</div>
          </main>
        </div>

        {/* Status rail — wide desktop only */}
        <aside className="hidden w-80 shrink-0 border-l border-border/80 bg-background/35 backdrop-blur 2xl:block">
          <div className="sticky top-[69px] max-h-[calc(100vh-69px)] overflow-y-auto p-4">
            <WorkspaceRightRail
              business={business}
              executionStatus={executionStatus}
              onTabChange={handleTabChange}
            />
          </div>
        </aside>
      </div>

      {/* Blueprint drawer */}
      <WorkspaceDrawer
        open={blueprintOpen}
        onClose={() => setBlueprintOpen(false)}
        title="Blueprint"
      >
        <div className="space-y-4">
          <p className="text-sm leading-7 text-foreground-secondary">
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
                    className="rounded-lg border border-border bg-elevated px-3 py-2 text-xs text-foreground-secondary"
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
