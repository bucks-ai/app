import Link from "next/link";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { ExecutionStatusPill } from "@/components/execution/ExecutionStatusPill";
import type { ExecutionNextAction } from "@/types/execution-ui";

type ExecutionNextActionsProps = {
  actions: ExecutionNextAction[];
};

function actorLabel(actor: ExecutionNextAction["actor"]) {
  return actor === "founder" ? "Founder" : "bucks.ai";
}

export function ExecutionNextActions({ actions }: ExecutionNextActionsProps) {
  return (
    <div className="rounded-lg border border-border bg-background p-5">
      <SectionLabel>Next recommended actions</SectionLabel>
      <div className="mt-4 space-y-3">
        {actions.length > 0 ? (
          actions.map((action) => (
            <div key={action.id} className="rounded-md border border-border bg-surface p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted">
                    {actorLabel(action.actor)}
                  </p>
                  <h3 className="mt-2 text-sm font-semibold text-foreground">
                    {action.title}
                  </h3>
                </div>
                <ExecutionStatusPill
                  label={actorLabel(action.actor)}
                  status={action.actor}
                />
              </div>
              {action.description ? (
                <p className="mt-3 text-sm leading-6 text-secondary">
                  {action.description}
                </p>
              ) : null}
              {action.href ? (
                <Link
                  href={action.href}
                  className="mt-4 inline-flex rounded-md border border-accent/35 px-3 py-2 text-sm font-semibold text-accent transition-colors hover:border-accent/70 hover:text-accent"
                >
                  Open action
                </Link>
              ) : null}
            </div>
          ))
        ) : (
          <p className="rounded-md border border-border bg-surface p-4 text-sm leading-6 text-secondary">
            No recommended actions are queued yet.
          </p>
        )}
      </div>
    </div>
  );
}
