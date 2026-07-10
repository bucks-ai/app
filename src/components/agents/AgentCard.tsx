import type { AgentRegistryEntry } from "@/types/agents";
import type { AgentRunRecord } from "@/types/agent-runs";
import { AgentStatusBadge } from "@/components/agents/AgentStatusBadge";
import { formatAgentRunWindow } from "@/components/agents/agent-view-model";

type AgentCardProps = {
  entry: AgentRegistryEntry;
  latestRun?: AgentRunRecord | null;
};

export function AgentCard({ entry, latestRun }: AgentCardProps) {
  const { template, businessStatus } = entry;
  const capabilities = template.capabilities.slice(0, 2);

  return (
    <article className="min-w-0 rounded-lg border border-border bg-surface p-3">
      <div className="flex min-w-0 items-start justify-between gap-2">
        <div className="min-w-0">
          <h4 className="break-words text-sm font-semibold text-foreground">
            {template.name}
          </h4>
          <p className="mt-1 break-words text-xs leading-5 text-muted">
            {template.description}
          </p>
        </div>
        <div className="shrink-0">
          <AgentStatusBadge value={businessStatus.status} />
        </div>
      </div>

      <p className="mt-3 break-words text-xs leading-5 text-secondary">
        {template.purpose}
      </p>

      <div className="mt-3 flex flex-wrap gap-1.5">
        <AgentStatusBadge kind="risk" value={template.riskLevel} />
        <AgentStatusBadge kind="autonomy" value={template.autonomyLevel} />
      </div>

      {capabilities.length > 0 ? (
        <div className="mt-3 flex flex-wrap gap-1.5">
          {capabilities.map((capability) => (
            <span
              key={capability.id}
              className="max-w-full rounded border border-border bg-background px-2 py-1 text-[11px] text-secondary"
            >
              <span className="break-words">{capability.label}</span>
            </span>
          ))}
        </div>
      ) : null}

      <div className="mt-3 rounded border border-border bg-background px-3 py-2">
        <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
          Registry signal
        </p>
        <p className="mt-1 break-words text-xs leading-5 text-secondary">
          {businessStatus.statusReason}
        </p>
      </div>

      {latestRun ? (
        <div className="mt-2 rounded border border-accent/20 bg-accent/8 px-3 py-2.5">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="font-mono text-[10px] uppercase tracking-widest text-accent">
              Latest real run
            </p>
            <AgentStatusBadge kind="run" value={latestRun.status} />
          </div>
          <p className="mt-2 break-words text-xs font-semibold leading-5 text-foreground">
            {latestRun.title}
          </p>
          {latestRun.summary ? (
            <p
              className="mt-1 truncate text-xs leading-5 text-secondary"
              title={latestRun.summary}
            >
              {latestRun.summary}
            </p>
          ) : null}
          <p className="mt-2 break-words font-mono text-[10px] uppercase tracking-widest text-muted">
            {formatAgentRunWindow(latestRun)}
          </p>
        </div>
      ) : (
        <div className="mt-2 rounded border border-dashed border-border bg-background px-3 py-2.5">
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Latest real run
          </p>
          <p className="mt-1 text-xs leading-5 text-muted">
            No runner run has been recorded for this agent yet.
          </p>
        </div>
      )}
    </article>
  );
}
