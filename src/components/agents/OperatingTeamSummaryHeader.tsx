import type { AgentRegistryView } from "@/types/agents";
import type { AgentRunListData } from "@/lib/agents-client";
import { InferAgentRunsButton } from "@/components/agents/InferAgentRunsButton";
import { resolveOperatingTeamNextAction } from "@/components/agents/agent-view-model";

type OperatingTeamSummaryHeaderProps = {
  businessId: string;
  registry: AgentRegistryView;
  runsData: AgentRunListData | null;
  runsWarning?: string | null;
  onRunsChanged?: () => Promise<void> | void;
};

export function OperatingTeamSummaryHeader({
  businessId,
  registry,
  runsData,
  runsWarning,
  onRunsChanged,
}: OperatingTeamSummaryHeaderProps) {
  const summary = registry.summary;
  const nextAction = resolveOperatingTeamNextAction(
    summary,
    runsData?.summary ?? null,
    Boolean(runsWarning)
  );
  const metrics = [
    { label: "Total", value: summary.totalAgents, tone: "text-[#F0F0F0]" },
    { label: "Active", value: summary.activeCount, tone: "text-[#C7D2FE]" },
    { label: "Completed", value: summary.completedCount, tone: "text-[#86EFAC]" },
    { label: "Blocked", value: summary.blockedCount, tone: "text-[#FCA5A5]" },
    { label: "Waiting", value: summary.waitingCount, tone: "text-[#FCD34D]" },
    { label: "Monitoring", value: summary.monitoringCount, tone: "text-[#99F6E4]" },
  ];

  return (
    <section className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4 sm:p-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
            Operating Team
          </p>
          <h2 className="mt-2 break-words text-2xl font-semibold tracking-tight text-[#F0F0F0]">
            21 agents across strategy, research, deployment, validation, safety, and orchestration.
          </h2>
          <div
            className={`mt-4 rounded border px-3 py-2.5 ${
              nextAction.tone === "danger"
                ? "border-[#EF4444]/25 bg-[#EF4444]/8"
                : nextAction.tone === "warning"
                  ? "border-[#F59E0B]/25 bg-[#F59E0B]/8"
                  : nextAction.tone === "accent"
                    ? "border-[#4F46E5]/25 bg-[#4F46E5]/8"
                    : "border-[#1C1C1C] bg-[#080808]"
            }`}
          >
            <p className="font-mono text-[10px] uppercase tracking-widest text-[#888]">
              Primary team action
            </p>
            <p className="mt-1 text-sm font-semibold text-[#F0F0F0]">
              {nextAction.title}
            </p>
            <p className="mt-1 break-words text-xs leading-5 text-[#888]">
              {nextAction.description}
            </p>
          </div>
        </div>

        <InferAgentRunsButton
          businessId={businessId}
          disabled={Boolean(runsWarning)}
          onInferred={onRunsChanged}
        />
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 sm:grid-cols-3 xl:grid-cols-6">
        {metrics.map((metric) => (
          <div
            key={metric.label}
            className="rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2.5"
          >
            <p className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
              {metric.label}
            </p>
            <p className={`mt-1 text-xl font-semibold ${metric.tone}`}>
              {metric.value}
            </p>
          </div>
        ))}
      </div>
    </section>
  );
}
