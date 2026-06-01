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
    { label: "Total", value: summary.totalAgents, tone: "text-foreground" },
    { label: "Active", value: summary.activeCount, tone: "text-accent" },
    { label: "Completed", value: summary.completedCount, tone: "text-success" },
    { label: "Blocked", value: summary.blockedCount, tone: "text-error" },
    { label: "Waiting", value: summary.waitingCount, tone: "text-warning" },
    { label: "Monitoring", value: summary.monitoringCount, tone: "text-success" },
  ];

  return (
    <section className="rounded-lg border border-border bg-surface p-4 sm:p-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
        <div className="min-w-0">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
            Operating Team
          </p>
          <h2 className="mt-2 break-words text-2xl font-semibold tracking-tight text-foreground">
            21 agents across strategy, research, deployment, validation, safety, and orchestration.
          </h2>
          <div
            className={`mt-4 rounded border px-3 py-2.5 ${
              nextAction.tone === "danger"
                ? "border-error/25 bg-error/8"
                : nextAction.tone === "warning"
                  ? "border-warning/25 bg-warning/8"
                  : nextAction.tone === "accent"
                    ? "border-accent/25 bg-accent/8"
                    : "border-border bg-background"
            }`}
          >
            <p className="font-mono text-[10px] uppercase tracking-widest text-secondary">
              Primary team action
            </p>
            <p className="mt-1 text-sm font-semibold text-foreground">
              {nextAction.title}
            </p>
            <p className="mt-1 break-words text-xs leading-5 text-secondary">
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
            className="rounded border border-border bg-background px-3 py-2.5"
          >
            <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
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
