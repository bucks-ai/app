import Link from "next/link";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { ExecutionStatusPill } from "@/components/execution/ExecutionStatusPill";
import type { ExecutionBlocker } from "@/types/execution-ui";

type ExecutionBlockersPanelProps = {
  blockers: ExecutionBlocker[];
};

function ownerLabel(owner: ExecutionBlocker["owner"]) {
  return owner === "founder" ? "Founder" : "bucks.ai";
}

export function ExecutionBlockersPanel({ blockers }: ExecutionBlockersPanelProps) {
  return (
    <div className="rounded-lg border border-border bg-background p-5">
      <div className="flex items-center justify-between gap-3">
        <SectionLabel tone={blockers.length > 0 ? "warning" : "muted"}>
          Blockers
        </SectionLabel>
        <ExecutionStatusPill
          label={blockers.length > 0 ? `${blockers.length} active` : "Clear"}
          status={blockers.length > 0 ? "warning" : "success"}
        />
      </div>

      <div className="mt-4 space-y-3">
        {blockers.length > 0 ? (
          blockers.map((blocker) => (
            <div
              key={blocker.id}
              className="rounded-md border border-warning/25 bg-warning/10 p-4"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-warning">
                    {ownerLabel(blocker.owner)}
                  </p>
                  <h3 className="mt-2 text-sm font-semibold text-foreground">
                    {blocker.title}
                  </h3>
                </div>
                <ExecutionStatusPill label={blocker.severity} status={blocker.severity} />
              </div>
              {blocker.description ? (
                <p className="mt-3 text-sm leading-6 text-warning">
                  {blocker.description}
                </p>
              ) : null}
              {blocker.href ? (
                <Link
                  href={blocker.href}
                  className="mt-4 inline-flex rounded-md border border-warning/35 px-3 py-2 text-sm font-semibold text-warning transition-colors hover:border-warning/70 hover:text-warning"
                >
                  Review blocker
                </Link>
              ) : null}
            </div>
          ))
        ) : (
          <p className="rounded-md border border-border bg-surface p-4 text-sm leading-6 text-secondary">
            No active blockers are recorded.
          </p>
        )}
      </div>
    </div>
  );
}
