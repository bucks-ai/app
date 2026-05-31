"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { BusinessExecutionStatus } from "@/types/execution-ui";
import {
  fetchBusinessExecutionStatus,
  fetchExecutionTimeline,
} from "@/lib/execution-client";
import { WorkspaceHeader } from "@/components/workspace/WorkspaceHeader";
import { PrimaryActionStrip } from "@/components/workspace/PrimaryActionStrip";
import { WorkspaceTabs } from "@/components/workspace/WorkspaceTabs";
import type { TabKey } from "@/components/workspace/WorkspaceTabs";
import { WorkspaceRightRail } from "@/components/workspace/WorkspaceRightRail";
import { WorkspaceDrawer } from "@/components/workspace/WorkspaceDrawer";
import { CommandMenuHint } from "@/components/workspace/CommandMenuHint";
import { resolvePrimaryNextAction } from "@/components/workspace/next-action";
import { OverviewTab } from "@/components/workspace/tabs/OverviewTab";
import { ResearchTab } from "@/components/workspace/tabs/ResearchTab";
import { ActionsTab } from "@/components/workspace/tabs/ActionsTab";
import { BuildTab } from "@/components/workspace/tabs/BuildTab";
import { DeployTab } from "@/components/workspace/tabs/DeployTab";
import { ValidationTab } from "@/components/workspace/tabs/ValidationTab";
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
  const primaryAction = resolvePrimaryNextAction(business, executionStatus);

  return (
    <div className="flex min-h-screen min-w-0 flex-col overflow-x-hidden">
      {/* Workspace header */}
      <WorkspaceHeader
        business={business}
        executionStatus={executionStatus}
        onBlueprintOpen={() => setBlueprintOpen(true)}
      />

      <div className="sticky top-0 z-30 bg-[#080808]/95 backdrop-blur">
        {/* Primary action strip */}
        <PrimaryActionStrip
          business={business}
          executionStatus={executionStatus}
          onTabChange={handleTabChange}
        />

        <div className="flex items-center justify-between gap-3 border-b border-[#1C1C1C] bg-[#080808] pr-4 sm:pr-6">
          {/* Tab bar */}
          <WorkspaceTabs
            activeTab={activeTab}
            onTabChange={handleTabChange}
            badgeCounts={{ actions: actionCount }}
          />
          <div className="hidden shrink-0 lg:block">
            <CommandMenuHint onTabChange={handleTabChange} />
          </div>
        </div>
      </div>

      {/* Body: main content + right rail */}
      <div className="flex flex-1 gap-0">
        {/* Main content */}
        <main className="min-w-0 flex-1 p-4 sm:p-6">
          {activeTab === "overview" ? (
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
          ) : null}
        </main>

        {/* Right rail (desktop only) */}
        <div className="hidden w-72 shrink-0 border-l border-[#1C1C1C] p-4 xl:block">
          <div className="sticky top-4">
            <WorkspaceRightRail
              business={business}
              executionStatus={executionStatus}
              onTabChange={handleTabChange}
            />
          </div>
        </div>
      </div>

      {/* Mobile sticky bottom bar */}
      <div className="sticky bottom-0 z-30 border-t border-[#1C1C1C] bg-[#080808]/95 px-3 py-3 backdrop-blur xl:hidden">
        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => handleTabChange(primaryAction.target)}
            className="min-w-0 flex-1 rounded border border-[#F59E0B]/35 bg-[#F59E0B]/10 px-3 py-2.5 text-left"
          >
            <span className="block font-mono text-[10px] uppercase tracking-widest text-[#FCD34D]">
              Next action
            </span>
            <span className="block truncate text-xs font-semibold text-[#F0F0F0]">
              {primaryAction.label}
            </span>
          </button>
          <button
            type="button"
            onClick={() => handleTabChange("activity")}
            className="rounded border border-[#1C1C1C] bg-[#141414] px-3 py-2.5 font-mono text-[11px] uppercase tracking-widest text-[#888]"
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
          <p className="text-sm leading-7 text-[#888]">
            {business.blueprintSummary ??
              "No blueprint summary is available for this project."}
          </p>

          {business.nextActions.length > 0 ? (
            <div>
              <p className="mb-2 font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
                Next autonomous actions
              </p>
              <ul className="space-y-1.5">
                {business.nextActions.map((action, i) => (
                  <li
                    key={i}
                    className="rounded border border-[#1C1C1C] bg-[#141414] px-3 py-2 text-xs text-[#888]"
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
