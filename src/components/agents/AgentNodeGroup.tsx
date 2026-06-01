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
    <section id={`agents-${node.nodeId}`} className="rounded-lg border border-[#1C1C1C] bg-[#080808] p-3 sm:p-4">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
            {node.nodeLabel}
          </p>
          <p className="mt-2 max-w-3xl break-words text-sm leading-6 text-[#888]">
            {node.nodeDescription}
          </p>
        </div>
        <div className="grid grid-cols-3 gap-2 text-center sm:flex sm:shrink-0 sm:flex-wrap sm:justify-end">
          <span className="rounded border border-[#4F46E5]/20 bg-[#4F46E5]/8 px-2 py-1.5">
            <span className="block font-mono text-[10px] uppercase tracking-widest text-[#A5B4FC]">
              Ready
            </span>
            <span className="text-sm font-semibold text-[#F0F0F0]">{node.readyCount}</span>
          </span>
          <span className="rounded border border-[#22C55E]/20 bg-[#22C55E]/8 px-2 py-1.5">
            <span className="block font-mono text-[10px] uppercase tracking-widest text-[#86EFAC]">
              Done
            </span>
            <span className="text-sm font-semibold text-[#F0F0F0]">{node.completedCount}</span>
          </span>
          <span className="rounded border border-[#EF4444]/20 bg-[#EF4444]/8 px-2 py-1.5">
            <span className="block font-mono text-[10px] uppercase tracking-widest text-[#FCA5A5]">
              Held
            </span>
            <span className="text-sm font-semibold text-[#F0F0F0]">
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
