import { StatusPill } from "@/components/ui/StatusPill";

export type RailStage = {
  label: string;
  detail: string;
  status: "Complete" | "Running" | "Waiting for approval" | "Blocked";
};

function variantForStatus(status: RailStage["status"]) {
  if (status === "Complete") return "success" as const;
  if (status === "Running") return "accent" as const;
  if (status === "Blocked") return "danger" as const;
  return "warning" as const;
}

export function AnimatedProgressRail({ stages }: { stages: RailStage[] }) {
  return (
    <ol className="relative grid gap-4 lg:grid-cols-5">
      {stages.map((stage, index) => (
        <li key={stage.label} className="relative">
          {index < stages.length - 1 ? (
            <span
              aria-hidden
              className={`absolute left-5 top-5 hidden h-px w-[calc(100%+1rem)] lg:block ${
                stage.status === "Running" ? "flow-line-x" : "rail-line-idle"
              }`}
            />
          ) : null}
          <div className="relative z-10 rounded-xl border border-border bg-surface/70 p-4">
            <span className="flex h-10 w-10 items-center justify-center rounded-full border border-accent/35 bg-background font-mono text-xs text-accent-bright">
              {String(index + 1).padStart(2, "0")}
            </span>
            <h3 className="mt-4 text-sm font-semibold text-foreground">{stage.label}</h3>
            <p className="mt-2 text-sm leading-6 text-secondary">{stage.detail}</p>
            <StatusPill
              label={stage.status}
              variant={variantForStatus(stage.status)}
              className="mt-4"
            />
          </div>
        </li>
      ))}
    </ol>
  );
}
