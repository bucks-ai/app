"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import {
  fetchAgentRegistry,
  fetchAgentRuns,
  type AgentRunListData,
} from "@/lib/agents-client";
import type { AgentRegistryView } from "@/types/agents";
import { AgentNodeGroup } from "@/components/agents/AgentNodeGroup";
import { AgentRunTimeline } from "@/components/agents/AgentRunTimeline";
import { OperatingTeamSummaryHeader } from "@/components/agents/OperatingTeamSummaryHeader";
import { latestRunByAgent } from "@/components/agents/agent-view-model";

type OperatingTeamPanelProps = {
  businessId: string;
};

type LoadState = "loading" | "ready" | "error";

export function OperatingTeamPanel({ businessId }: OperatingTeamPanelProps) {
  const [registry, setRegistry] = useState<AgentRegistryView | null>(null);
  const [runsData, setRunsData] = useState<AgentRunListData | null>(null);
  const [runsWarning, setRunsWarning] = useState<string | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [message, setMessage] = useState<string | null>(null);

  const loadOperatingTeam = useCallback(async () => {
    setMessage(null);
    setRunsWarning(null);

    const [registryResult, runsResult] = await Promise.all([
      fetchAgentRegistry(businessId),
      fetchAgentRuns(businessId),
    ]);

    if (!registryResult.ok) {
      setRegistry(null);
      setRunsData(null);
      setLoadState("error");
      setMessage(registryResult.error);
      return;
    }

    setRegistry(registryResult.data);

    if (runsResult.ok) {
      setRunsData(runsResult.data);
      setRunsWarning(runsResult.warning ?? null);
    } else {
      setRunsData(null);
      setRunsWarning(runsResult.error);
    }

    setLoadState("ready");
  }, [businessId]);

  useEffect(() => {
    let ignore = false;

    async function load() {
      await loadOperatingTeam();
      if (ignore) return;
    }

    void load();

    return () => {
      ignore = true;
    };
  }, [loadOperatingTeam]);

  const runs = useMemo(() => runsData?.runs ?? [], [runsData?.runs]);
  const latestRuns = useMemo(() => latestRunByAgent(runs), [runs]);

  if (loadState === "loading") {
    return (
      <div className="space-y-3">
        <div className="h-40 animate-pulse rounded-lg border border-[#1C1C1C] bg-[#0F0F0F]" />
        <div className="grid gap-3 lg:grid-cols-2">
          <div className="h-64 animate-pulse rounded-lg border border-[#1C1C1C] bg-[#0F0F0F]" />
          <div className="h-64 animate-pulse rounded-lg border border-[#1C1C1C] bg-[#0F0F0F]" />
        </div>
      </div>
    );
  }

  if (loadState === "error") {
    return (
      <div className="rounded-lg border border-[#EF4444]/25 bg-[#EF4444]/8 p-5">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#FCA5A5]">
          Operating team unavailable
        </p>
        <p className="mt-3 break-words text-sm leading-6 text-[#FECACA]">
          {message ?? "The operating team could not be loaded."}
        </p>
        <button
          type="button"
          onClick={() => void loadOperatingTeam()}
          className="mt-4 rounded-md border border-[#EF4444]/35 bg-[#080808] px-3 py-2 text-xs font-semibold text-[#FCA5A5] transition-colors hover:border-[#EF4444]/60"
        >
          Retry
        </button>
      </div>
    );
  }

  if (!registry || registry.agents.length === 0) {
    return (
      <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-5">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
          Operating Team
        </p>
        <p className="mt-3 text-sm leading-6 text-[#888]">
          No agents are available for this business yet.
        </p>
      </div>
    );
  }

  return (
    <div className="min-w-0 space-y-4">
      <OperatingTeamSummaryHeader
        businessId={businessId}
        registry={registry}
        runsData={runsData}
        runsWarning={runsWarning}
        onRunsChanged={loadOperatingTeam}
      />

      {runsWarning ? (
        <div className="rounded-lg border border-[#F59E0B]/25 bg-[#F59E0B]/8 p-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#FCD34D]">
            Agent run history
          </p>
          <p className="mt-2 break-words text-sm leading-6 text-[#FDE68A]">
            {runsWarning}
          </p>
        </div>
      ) : null}

      <div className="grid gap-4 2xl:grid-cols-[1fr_22rem]">
        <div className="min-w-0 space-y-4">
          {registry.nodes.map((node) => (
            <AgentNodeGroup key={node.nodeId} node={node} latestRuns={latestRuns} />
          ))}
        </div>
        <div className="min-w-0">
          <AgentRunTimeline runs={runs} agents={registry.agents} />
        </div>
      </div>
    </div>
  );
}
