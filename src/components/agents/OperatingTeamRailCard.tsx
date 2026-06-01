"use client";

import { useEffect, useState } from "react";
import {
  fetchAgentRegistry,
  fetchAgentRuns,
  type AgentRunListData,
} from "@/lib/agents-client";
import type { AgentRegistrySummary } from "@/types/agents";
import { resolveOperatingTeamNextAction } from "@/components/agents/agent-view-model";

type OperatingTeamRailCardProps = {
  businessId: string;
  onOpenTeam: () => void;
};

export function OperatingTeamRailCard({
  businessId,
  onOpenTeam,
}: OperatingTeamRailCardProps) {
  const [summary, setSummary] = useState<AgentRegistrySummary | null>(null);
  const [runsData, setRunsData] = useState<AgentRunListData | null>(null);
  const [runsWarning, setRunsWarning] = useState<string | null>(null);
  const [message, setMessage] = useState("Checking team...");

  useEffect(() => {
    let ignore = false;

    async function load() {
      const [registryResult, runsResult] = await Promise.all([
        fetchAgentRegistry(businessId),
        fetchAgentRuns(businessId),
      ]);
      if (ignore) return;

      if (!registryResult.ok) {
        setSummary(null);
        setMessage("Team unavailable.");
        return;
      }

      setSummary(registryResult.data.summary);
      setMessage("");

      if (runsResult.ok) {
        setRunsData(runsResult.data);
        setRunsWarning(runsResult.warning ?? null);
      } else {
        setRunsData(null);
        setRunsWarning(runsResult.error);
      }
    }

    void load();

    return () => {
      ignore = true;
    };
  }, [businessId]);

  const action = summary
    ? resolveOperatingTeamNextAction(summary, runsData?.summary ?? null, Boolean(runsWarning))
    : null;

  return (
    <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
          Team
        </p>
        {summary ? (
          <span className="rounded border border-[#1C1C1C] bg-[#080808] px-2 py-1 font-mono text-[10px] uppercase tracking-widest text-[#888]">
            {summary.totalAgents} agents
          </span>
        ) : null}
      </div>
      <button
        type="button"
        onClick={onOpenTeam}
        className="mt-3 w-full rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2 text-left transition-colors hover:border-[#4F46E5]/45"
      >
        <p className="break-words text-xs font-semibold text-[#D4D4D4]">
          {action?.title ?? message}
        </p>
        {action ? (
          <p className="mt-1 break-words text-xs leading-5 text-[#666]">
            {summary?.blockedCount || summary?.waitingCount
              ? `${(summary?.blockedCount ?? 0) + (summary?.waitingCount ?? 0)} held, ${summary?.monitoringCount ?? 0} monitoring`
              : action.description}
          </p>
        ) : null}
      </button>
    </div>
  );
}
