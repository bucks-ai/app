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

/**
 * The run as a vertical spine.
 *
 * This was a five-column grid inside a two-column section, which left each
 * stage about 78px of text width — every description broke after one or two
 * words, and five bordered tiles sat in a row like a filing cabinet. A
 * single continuous rail gives each stage a full line length, and the line
 * itself carries the sense of the work moving from one agent to the next.
 */
export function AnimatedProgressRail({ stages }: { stages: RailStage[] }) {
  return (
    <ol className="relative grid gap-0">
      {stages.map((stage, index) => {
        const isLast = index === stages.length - 1;
        const isRunning = stage.status === "Running";

        return (
          <li key={stage.label} className="relative grid grid-cols-[2.5rem_minmax(0,1fr)] gap-4">
            {/* The spine. Animated only on the segment leaving the active
                stage, so motion marks where work is actually flowing. */}
            {!isLast ? (
              <span
                aria-hidden
                className={`absolute left-5 top-10 h-[calc(100%-2.5rem)] -translate-x-1/2 ${
                  isRunning
                    ? "flow-line-y"
                    : stage.status === "Complete"
                      ? "w-px rail-line-done"
                      : "w-px rail-line-idle"
                }`}
              />
            ) : null}

            <span
              className={`relative z-10 flex h-10 w-10 items-center justify-center rounded-full font-mono text-xs ${
                isRunning
                  ? "pulse-ring bg-accent text-accent-contrast"
                  : "bg-muted text-foreground-secondary"
              }`}
            >
              {String(index + 1).padStart(2, "0")}
            </span>

            <div className={isLast ? "min-w-0 pb-0" : "min-w-0 pb-7"}>
              <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
                <h3 className="text-sm font-semibold text-foreground">
                  {stage.label}
                </h3>
                <StatusPill
                  label={stage.status}
                  variant={variantForStatus(stage.status)}
                />
              </div>
              <p className="mt-2 max-w-prose text-sm leading-6 text-foreground-secondary">
                {stage.detail}
              </p>
            </div>
          </li>
        );
      })}
    </ol>
  );
}
