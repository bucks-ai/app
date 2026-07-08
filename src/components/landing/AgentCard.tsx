import { GlassPanel } from "@/components/ui/GlassPanel";
import { StatusPill } from "@/components/ui/StatusPill";

export type AgentCardData = {
  name: string;
  purpose: string;
  permissions: string[];
  state: "Running" | "Waiting" | "Complete" | "Blocked";
  lastRun: string;
};

function variantForState(state: AgentCardData["state"]) {
  if (state === "Running") return "accent" as const;
  if (state === "Complete") return "success" as const;
  if (state === "Blocked") return "danger" as const;
  return "warning" as const;
}

export function AgentCard({ agent }: { agent: AgentCardData }) {
  return (
    <GlassPanel as="article" interactive className="h-full p-5">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
            Agent
          </p>
          <h3 className="mt-3 text-lg font-semibold tracking-tight text-foreground">
            {agent.name}
          </h3>
        </div>
        <StatusPill label={agent.state} variant={variantForState(agent.state)} />
      </div>
      <p className="mt-4 text-sm leading-6 text-secondary">{agent.purpose}</p>
      <div className="mt-5 border-t border-border/70 pt-4">
        <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
          Permissions
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          {agent.permissions.map((permission) => (
            <span
              key={permission}
              className="rounded-md border border-border bg-background/70 px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.12em] text-secondary"
            >
              {permission}
            </span>
          ))}
        </div>
      </div>
      <p className="mt-5 font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
        Last run: <span className="text-secondary">{agent.lastRun}</span>
      </p>
    </GlassPanel>
  );
}
