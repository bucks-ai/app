"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import { LOBES } from "@/components/dashboard/brain/brain-model";
import type { BusinessExecutionStatus } from "@/types/execution-ui";
import {
  fetchBusinessExecutionStatus,
  fetchExecutionTimeline,
} from "@/lib/execution-client";
import { PageField } from "@/components/ui/PageField";
import { RegionShell, brainHref } from "@/components/workspace/RegionShell";
import { useSectionFocus } from "@/components/workspace/use-section-focus";
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
  /** The region the Brain sent us into. Never defaults — see the note below. */
  region: string;
  initialExecutionStatus?: BusinessExecutionStatus | null;
};

/**
 * One region of one business, and nothing else.
 *
 * This used to render WorkspaceSidebar (all ten regions, always) plus
 * WorkspaceTabs (the same ten on mobile) around whichever tab was active, with
 * `resolveInitialTab` quietly defaulting to "overview". That is what made the
 * Brain a doorway: you arrived and every other region was already in reach.
 *
 * Now the region arrives as a prop, there is no switcher, and a business with
 * no region chosen never lands here at all — the route sends it back to the
 * Brain to choose one. Both lateral navigations are deliberately gone; the
 * Brain is the only way across.
 */
export function BusinessWorkspace({
  business,
  region,
  initialExecutionStatus,
}: BusinessWorkspaceProps) {
  const router = useRouter();
  const searchParams = useSearchParams();
  const [executionStatus, setExecutionStatus] =
    useState<BusinessExecutionStatus | null>(initialExecutionStatus ?? null);

  /* Overview's cards point at other regions. Under the old sidebar those were
     lateral jumps, which is exactly the "everything is equally reachable"
     problem. They now travel THROUGH the Brain: following one flies the camera
     to that lobe, and you commit from the map. One extra step, and that step is
     the spatial transition rather than a hidden teleport. */
  const travelTo = useCallback(
    (tab: string) => {
      const lobe = LOBES.find((entry) => entry.tab === tab);
      router.push(brainHref(lobe ? `${business.id}:${lobe.key}` : business.id));
    },
    [router, business.id]
  );

  const activeSection = searchParams.get("section");
  useSectionFocus(activeSection, region);

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

  const panel =
    region === "overview" ? (
      <OverviewTab
        business={business}
        executionStatus={executionStatus}
        onTabChange={travelTo}
      />
    ) : region === "actions" ? (
      <ActionsTab business={business} executionStatus={executionStatus} />
    ) : region === "research" ? (
      <ResearchTab business={business} />
    ) : region === "build" ? (
      <BuildTab business={business} />
    ) : region === "deploy" ? (
      <DeployTab business={business} />
    ) : region === "validation" ? (
      <ValidationTab business={business} />
    ) : region === "team" ? (
      <OperatingTeamTab business={business} />
    ) : region === "tools" ? (
      <ToolsTab
        business={business}
        businessId={business.id}
        businessName={business.name}
      />
    ) : region === "activity" ? (
      <ActivityTab business={business} executionStatus={executionStatus} />
    ) : region === "settings" ? (
      <SettingsTab business={business} />
    ) : null;

  return (
    <div className="flex min-h-screen flex-col overflow-x-hidden pt-[69px]">
      <PageField grid={false} />
      <main id="main-content" className="min-w-0 flex-1">
        <RegionShell
          businessId={business.id}
          businessName={business.name}
          regionKey={region}
          activeSection={activeSection}
        >
          {panel}
        </RegionShell>
      </main>
    </div>
  );
}
