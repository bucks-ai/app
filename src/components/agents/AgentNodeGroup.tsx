import type { AgentNodeSummary, AgentTemplateId } from "@/types/agents";
import type { AgentRunRecord } from "@/types/agent-runs";
import { AgentCard } from "@/components/agents/AgentCard";

type AgentNodeGroupProps = {
  node: AgentNodeSummary;
  latestRuns: Partial<Record<AgentTemplateId, AgentRunRecord>>;
};

export function AgentNodeGroup({ node, latestRuns }: AgentNodeGroupProps) {
  const blockedCount = node.agents.filter(
    (entry) => entry.businessStatus.status === "blocked"
  ).length;
  const waitingCount = node.agents.filter(
    (entry) => entry.businessStatus.status === "waiting_for_approval"
  ).length;

  return (
    <section id={`agents-${node.nodeId}`} className="rounded-lg border border-border bg-background p-3 sm:p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
            {node.nodeLabel}
          </p>
          <p className="mt-2 max-w-3xl break-words text-sm leading-6 text-secondary">
            {node.nodeDescription}
          </p>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center sm:flex sm:shrink-0 sm:flex-wrap sm:justify-end">
          <span className="rounded border border-accent/20 bg-accent/8 px-2 py-1.5">
            <span className="block font-mono text-[10px] uppercase tracking-widest text-accent">
              Ready
            </span>
            <span className="text-sm font-semibold text-foreground">{node.readyCount}</span>
          </span>
          <span className="rounded border border-success/20 bg-success/8 px-2 py-1.5">
            <span className="block font-mono text-[10px] uppercase tracking-widest text-success">
              Done
            </span>
            <span className="text-sm font-semibold text-foreground">{node.completedCount}</span>
          </span>
          <span className="rounded border border-error/20 bg-error/8 px-2 py-1.5">
            <span className="block font-mono text-[10px] uppercase tracking-widest text-error">
              Held
            </span>
            <span className="text-sm font-semibold text-foreground">
              {blockedCount + waitingCount}
            </span>
          </span>
        </div>
      </div>

      <div className="mt-4 grid min-w-0 gap-3 md:grid-cols-2 2xl:grid-cols-3">
        {node.agents.map((entry) => (
          <AgentCard
            key={entry.template.id}
            entry={entry}
            latestRun={latestRuns[entry.template.id] ?? null}
          />
        ))}
      </div>
    </section>
  );
}
