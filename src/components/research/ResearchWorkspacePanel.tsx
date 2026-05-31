"use client";

import { useCallback, useEffect, useState } from "react";
import {
  fetchResearchWorkspace,
  generateResearchWorkspace,
} from "@/lib/research-client";
import type { ResearchWorkspace } from "@/types/research-ui";
import { BuyerBudgetPanel } from "@/components/research/BuyerBudgetPanel";
import { CompetitorMapPanel } from "@/components/research/CompetitorMapPanel";
import { CustomerSegmentsPanel } from "@/components/research/CustomerSegmentsPanel";
import { DistributionChannelsPanel } from "@/components/research/DistributionChannelsPanel";
import { MonetizationPanel } from "@/components/research/MonetizationPanel";
import { OpportunityScoreCard } from "@/components/research/OpportunityScoreCard";
import { ResearchEmptyState } from "@/components/research/ResearchEmptyState";
import { ResearchEvidencePanel } from "@/components/research/ResearchEvidencePanel";
import { ResearchHypothesesPanel } from "@/components/research/ResearchHypothesesPanel";
import { ResearchNextActionCard } from "@/components/research/ResearchNextActionCard";
import { ResearchRisksPanel } from "@/components/research/ResearchRisksPanel";
import { ResearchSummaryHeader } from "@/components/research/ResearchSummaryHeader";

type ResearchWorkspacePanelProps = {
  businessId: string;
};

type LoadState = "loading" | "ready" | "empty" | "error";

export function ResearchWorkspacePanel({ businessId }: ResearchWorkspacePanelProps) {
  const [workspace, setWorkspace] = useState<ResearchWorkspace | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [message, setMessage] = useState<string | null>(null);
  const [generating, setGenerating] = useState(false);

  const loadWorkspace = useCallback(async () => {
    setMessage(null);
    const result = await fetchResearchWorkspace(businessId);

    if (!result.ok) {
      setWorkspace(null);
      setLoadState("error");
      setMessage(result.error);
      return;
    }

    setWorkspace(result.data);
    setLoadState(result.data.summary.canGenerate ? "empty" : "ready");
  }, [businessId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadWorkspace();
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [loadWorkspace]);

  async function handleGenerate() {
    setGenerating(true);
    setMessage(null);

    const result = await generateResearchWorkspace(businessId);
    setGenerating(false);

    if (!result.ok) {
      setMessage(result.error);
      setLoadState("empty");
      return;
    }

    await loadWorkspace();
  }

  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  if (loadState === "loading") {
    return (
      <div className="space-y-3">
        <div className="h-36 animate-pulse rounded-lg border border-[#1C1C1C] bg-[#0F0F0F]" />
        <div className="grid gap-3 lg:grid-cols-2">
          <div className="h-52 animate-pulse rounded-lg border border-[#1C1C1C] bg-[#0F0F0F]" />
          <div className="h-52 animate-pulse rounded-lg border border-[#1C1C1C] bg-[#0F0F0F]" />
        </div>
      </div>
    );
  }

  if (loadState === "error") {
    return (
      <div className="rounded-lg border border-[#EF4444]/25 bg-[#EF4444]/8 p-5">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#FCA5A5]">
          Research unavailable
        </p>
        <p className="mt-3 text-sm leading-6 text-[#FECACA]">
          {message ?? "Research could not be loaded."}
        </p>
        <button
          type="button"
          onClick={() => void loadWorkspace()}
          className="mt-4 rounded-md border border-[#EF4444]/35 bg-[#080808] px-3 py-2 text-xs font-semibold text-[#FCA5A5] transition-colors hover:border-[#EF4444]/60"
        >
          Retry
        </button>
      </div>
    );
  }

  if (loadState === "empty") {
    return (
      <div className="space-y-4">
        <ResearchEmptyState
          onGenerate={handleGenerate}
          loading={generating}
          error={message}
        />
        <ResearchNextActionCard
          workspace={null}
          onCreateWorkspace={handleGenerate}
          loading={generating}
        />
      </div>
    );
  }

  if (!workspace) return null;

  return (
    <div className="space-y-4">
      <ResearchSummaryHeader workspace={workspace} />
      <ResearchNextActionCard
        workspace={workspace}
        onFocusRisks={() => scrollTo("research-risks")}
        onFocusHypotheses={() => scrollTo("research-hypotheses")}
        onFocusCompetitors={() => scrollTo("research-competitors")}
      />
      <OpportunityScoreCard report={workspace.report} />
      <div className="grid gap-4 xl:grid-cols-2">
        <CustomerSegmentsPanel segments={workspace.segments} />
        <BuyerBudgetPanel buyerBudgets={workspace.buyerBudgets} />
      </div>
      <CompetitorMapPanel competitors={workspace.competitors} />
      <div className="grid gap-4 xl:grid-cols-2">
        <MonetizationPanel models={workspace.monetizationModels} />
        <DistributionChannelsPanel channels={workspace.distributionChannels} />
      </div>
      <ResearchRisksPanel risks={workspace.risks} />
      <ResearchHypothesesPanel hypotheses={workspace.hypotheses} />
      <ResearchEvidencePanel evidence={workspace.evidence} />
    </div>
  );
}
