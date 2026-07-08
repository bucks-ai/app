import { AnimatedProgressRail, type RailStage } from "@/components/landing/AnimatedProgressRail";
import { ExecutionLog, type ExecutionLogItem } from "@/components/landing/ExecutionLog";
import { GlassPanel } from "@/components/ui/GlassPanel";
import { StatusPill } from "@/components/ui/StatusPill";

const consoleLog: ExecutionLogItem[] = [
  { time: "09:41", actor: "strategy", event: "Mapped wedge, ICP, and pricing constraint.", tone: "accent" },
  { time: "09:44", actor: "research", event: "Found 18 competing products and 4 underserved segments.", tone: "success" },
  { time: "09:48", actor: "build", event: "Prepared GitHub task for Vercel preview scaffold.", tone: "accent" },
  { time: "09:51", actor: "safety", event: "Paused outbound copy for founder approval.", tone: "warning" },
];

const railStages: RailStage[] = [
  { label: "Strategy", detail: "Business model and operating constraints", status: "Complete" },
  { label: "Research", detail: "Market signals and competitor map", status: "Complete" },
  { label: "Validation", detail: "Customer test plan and persona scripts", status: "Running" },
  { label: "Build", detail: "GitHub task and preview scaffold", status: "Waiting for approval" },
  { label: "Deploy", detail: "Vercel preview ready behind checkpoint", status: "Waiting for approval" },
];

export function MissionConsole({ compact = false }: { compact?: boolean }) {
  return (
    <GlassPanel
      className="p-2"
      innerClassName="rounded-[0.65rem] border border-border-subtle bg-elevated/88"
    >
      <div className="flex items-center justify-between gap-3 border-b border-border-subtle px-4 py-3">
        <div className="flex min-w-0 items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full bg-status-blocked/80" />
          <span className="h-2.5 w-2.5 rounded-full bg-status-pending/90" />
          <span className="h-2.5 w-2.5 rounded-full bg-status-done/90" />
          <span className="ml-3 truncate font-mono text-xs text-muted">
            mission-console · clipforge-ai
          </span>
        </div>
        <StatusPill label="Active run" variant="accent" />
      </div>

      <div className="grid gap-4 p-4 sm:p-5">
        <div className="grid gap-3 sm:grid-cols-3">
          {[
            ["Agent", "Validation", "creating test plan"],
            ["Deploy", "Preview ready", "Vercel checkpoint"],
            ["Risk", "Approval gated", "outbound copy"],
          ].map(([label, value, detail]) => (
            <div
              key={label}
              className="rounded-xl border border-border bg-background/72 p-3"
            >
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
                {label}
              </p>
              <p className="mt-2 text-base font-semibold text-foreground">{value}</p>
              <p className="mt-1 text-xs text-secondary">{detail}</p>
            </div>
          ))}
        </div>

        {!compact ? <AnimatedProgressRail stages={railStages} /> : null}
        <ExecutionLog items={consoleLog} compact={compact} />

        <div className="rounded-xl border border-status-pending/30 bg-status-pending/10 p-4">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-status-pending">
                Human checkpoint
              </p>
              <p className="mt-2 text-sm font-semibold text-foreground">
                Approve preview deployment and first validation script.
              </p>
            </div>
            <StatusPill label="Waiting for approval" variant="warning" />
          </div>
        </div>
      </div>
    </GlassPanel>
  );
}

export { consoleLog, railStages };
