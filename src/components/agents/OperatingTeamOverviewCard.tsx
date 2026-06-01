"use client";

import { useEffect, useState } from "react";
import {
  fetchAgentRegistry,
  fetchAgentRuns,
  type AgentRunListData,
} from "@/lib/agents-client";
import type { AgentRegistrySummary } from "@/types/agents";
import { resolveOperatingTeamNextAction } from "@/components/agents/agent-view-model";

type OperatingTeamOverviewCardProps = {
  businessId: string;
  onOpenTeam: () => void;
};

export function OperatingTeamOverviewCard({
  businessId,
  onOpenTeam,
}: OperatingTeamOverviewCardProps) {
  const [summary, setSummary] = useState<AgentRegistrySummary | null>(null);
  const [runsData, setRunsData] = useState<AgentRunListData | null>(null);
  const [runsWarning, setRunsWarning] = useState<string | null>(null);
  const [message, setMessage] = useState("Checking operating team...");

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
        setMessage(registryResult.error);
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
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
          Operating Team
        </p>
        <button
          type="button"
          onClick={onOpenTeam}
          className="font-mono text-[10px] uppercase tracking-widest text-muted transition-colors hover:text-secondary"
        >
          Open
        </button>
      </div>

      {summary ? (
        <div className="mt-3 space-y-3">
          <div className="grid grid-cols-3 gap-2">
            <span className="rounded border border-border bg-background px-2.5 py-2">
              <span className="block font-mono text-[10px] uppercase tracking-widest text-muted">
                Agents
              </span>
              <span className="text-sm font-semibold text-foreground">
                {summary.totalAgents}
              </span>
            </span>
            <span className="rounded border border-success/20 bg-success/8 px-2.5 py-2">
              <span className="block font-mono text-[10px] uppercase tracking-widest text-success">
                Done
              </span>
              <span className="text-sm font-semibold text-foreground">
                {summary.completedCount}
              </span>
            </span>
            <span className="rounded border border-error/20 bg-error/8 px-2.5 py-2">
              <span className="block font-mono text-[10px] uppercase tracking-widest text-error">
                Held
              </span>
              <span className="text-sm font-semibold text-foreground">
                {summary.blockedCount + summary.waitingCount}
              </span>
            </span>
          </div>
          {action ? (
            <p className="break-words text-sm leading-6 text-secondary">
              {action.title}: <span className="text-secondary">{action.description}</span>
            </p>
          ) : null}
        </div>
      ) : (
        <p className="mt-3 break-words text-sm leading-6 text-muted">{message}</p>
      )}
    </div>
  );
}
