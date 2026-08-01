import { StatusPill } from "@/components/ui/StatusPill";
import type { HumanAction } from "@/components/dashboard/mock-data";

type HumanActionQueueProps = {
  actions: HumanAction[];
};

export function HumanActionQueue({ actions }: HumanActionQueueProps) {
  return (
    <div className="space-y-3">
      {actions.map((action) => (
        <div
          key={`${action.business}-${action.title}`}
          className="interactive-surface rounded-lg border border-warning/30 bg-[linear-gradient(135deg,var(--warning-soft),rgba(255,255,255,0.02))] p-4 hover:border-warning/50"
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-warning">
                {action.business}
              </p>
              <h3 className="mt-2 text-base font-semibold text-foreground">
                {action.title}
              </h3>
            </div>
            <StatusPill label={action.status} variant="warning" />
          </div>
          <p className="mt-3 text-sm leading-6 text-foreground-secondary">{action.reason}</p>
        </div>
      ))}
    </div>
  );
}
