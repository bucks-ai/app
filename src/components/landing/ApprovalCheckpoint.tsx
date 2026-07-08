import { GlassPanel } from "@/components/ui/GlassPanel";
import { RiskBadge, type RiskTone } from "@/components/ui/RiskBadge";
import { StatusPill } from "@/components/ui/StatusPill";

export type CheckpointData = {
  title: string;
  body: string;
  state: "Awaiting approval" | "Auto-approved" | "Rolled back" | "Cleared";
  risk: RiskTone;
  riskLabel: string;
  /** the permission the agent asked for, verbatim */
  permissionPrompt: string;
  /** what happens if the founder says no */
  rollback: string;
  featured?: boolean;
};

function variantForState(state: CheckpointData["state"]) {
  if (state === "Awaiting approval") return "warning" as const;
  if (state === "Rolled back") return "danger" as const;
  if (state === "Cleared") return "success" as const;
  return "neutral" as const;
}

/**
 * A single human gate, rendered the way the console renders it: what the
 * agent wants, the risk label, the exact permission prompt, and the rollback
 * path. Informational by design — the real approve control lives in the
 * dashboard, not on a marketing page.
 */
export function ApprovalCheckpoint({ checkpoint }: { checkpoint: CheckpointData }) {
  return (
    <GlassPanel
      className={`h-full ${
        checkpoint.featured ? "border-status-pending/40" : ""
      }`}
      innerClassName="flex h-full flex-col p-5"
    >
      <div className="flex flex-wrap items-center justify-between gap-2.5">
        <StatusPill
          label={checkpoint.state}
          variant={variantForState(checkpoint.state)}
        />
        <RiskBadge level={checkpoint.risk} label={checkpoint.riskLabel} />
      </div>

      <h3 className="mt-4 text-lg font-semibold tracking-tight text-foreground">
        {checkpoint.title}
      </h3>
      <p className="mt-2.5 text-sm leading-6 text-secondary">{checkpoint.body}</p>

      <div className="mt-auto grid gap-2.5 pt-5">
        <div className="rounded-lg border border-border bg-background/72 px-3 py-2.5">
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
            Permission prompt
          </p>
          <p className="mt-1.5 font-mono text-xs leading-5 text-secondary">
            {checkpoint.permissionPrompt}
          </p>
        </div>
        <div className="rounded-lg border border-border bg-background/72 px-3 py-2.5">
          <p className="font-mono text-[10px] uppercase tracking-[0.16em] text-muted">
            Rollback path
          </p>
          <p className="mt-1.5 text-xs leading-5 text-secondary">
            {checkpoint.rollback}
          </p>
        </div>
      </div>
    </GlassPanel>
  );
}
