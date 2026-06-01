import type { AgentRegistryEntry } from "@/types/agents";
import type { AgentRunRecord } from "@/types/agent-runs";
import { AgentStatusBadge } from "@/components/agents/AgentStatusBadge";
import {
  formatAgentTime,
  humanizeAgentValue,
} from "@/components/agents/agent-view-model";

type AgentRunTimelineProps = {
  runs: AgentRunRecord[];
  agents: AgentRegistryEntry[];
  limit?: number;
};

export function AgentRunTimeline({ runs, agents, limit = 8 }: AgentRunTimelineProps) {
  const namesByAgent = new Map(
    agents.map((entry) => [entry.template.id, entry.template.name])
  );
  const visibleRuns = runs.slice(0, limit);

  return (
    <section className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
          Recent agent runs
        </p>
        <span className="rounded border border-[#1C1C1C] bg-[#080808] px-2 py-1 font-mono text-[10px] uppercase tracking-widest text-[#666]">
          {runs.length} total
        </span>
      </div>

      {visibleRuns.length > 0 ? (
        <div className="mt-3 space-y-2">
          {visibleRuns.map((run) => {
            const timestamp = run.completed_at ?? run.started_at ?? run.created_at;
            return (
              <article
                key={run.id}
                className="min-w-0 rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2.5"
              >
                <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <p className="break-words text-xs font-semibold text-[#F0F0F0]">
                      {run.title}
                    </p>
                    <p className="mt-1 break-words font-mono text-[10px] uppercase tracking-widest text-[#555]">
                      {namesByAgent.get(run.agent_id) ?? humanizeAgentValue(run.agent_id)}
                      {" / "}
                      {humanizeAgentValue(run.source)}
                      {run.trigger ? ` / ${humanizeAgentValue(run.trigger)}` : ""}
                    </p>
                  </div>
                  <div className="shrink-0">
                    <AgentStatusBadge kind="run" value={run.status} />
                  </div>
                </div>
                {run.summary ? (
                  <p className="mt-2 break-words text-xs leading-5 text-[#888]">
                    {run.summary}
                  </p>
                ) : null}
                {run.error?.message ? (
                  <p className="mt-2 break-words text-xs leading-5 text-[#FCA5A5]">
                    {run.error.message}
                  </p>
                ) : null}
                <p className="mt-2 font-mono text-[10px] uppercase tracking-widest text-[#444]">
                  {formatAgentTime(timestamp)}
                </p>
              </article>
            );
          })}
        </div>
      ) : (
        <p className="mt-3 text-sm leading-6 text-[#666]">
          No agent runs are recorded yet. Build run history from existing activity logs when
          the Agent Runs SQL is installed.
        </p>
      )}
    </section>
  );
}
