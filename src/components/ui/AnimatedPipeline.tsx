"use client";

import { motion } from "framer-motion";
import { StatusChip, type PipelineStatus } from "@/components/ui/StatusChip";

export type PipelineStage = {
  label: string;
  detail: string;
  status: PipelineStatus;
};

type AnimatedPipelineProps = {
  stages: PipelineStage[];
  className?: string;
};

function nodeClass(status: PipelineStatus) {
  if (status === "done") return "border-status-done/40 bg-status-done/10";
  if (status === "running") return "pulse-ring border-accent bg-accent/15";
  if (status === "blocked") return "border-status-blocked/40 bg-status-blocked/10";
  if (status === "pending") return "border-status-pending/40 bg-status-pending/10";
  return "border-border bg-surface";
}

function dotColor(status: PipelineStatus) {
  if (status === "done") return "var(--status-done)";
  if (status === "running") return "var(--status-running)";
  if (status === "blocked") return "var(--status-blocked)";
  if (status === "pending") return "var(--status-pending)";
  return "var(--status-queued)";
}

function connectorClass(status: PipelineStatus) {
  if (status === "done") return "rail-line-done";
  if (status === "running") return "flow-line-x";
  if (status === "blocked") return "bg-status-blocked/50";
  return "rail-line-idle";
}

export function AnimatedPipeline({ stages, className = "" }: AnimatedPipelineProps) {
  return (
    <div className={className}>
      <div className="hidden sm:block">
        <div className="flex items-center">
          {stages.map((stage, index) => (
            <motion.div
              key={stage.label}
              className="flex flex-1 items-center last:flex-none"
              initial={false}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.08, duration: 0.35 }}
            >
              <span
                className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border ${nodeClass(stage.status)}`}
              >
                <span
                  aria-hidden
                  className="h-2 w-2 rounded-full"
                  style={{ background: dotColor(stage.status) }}
                />
              </span>
              {index < stages.length - 1 ? (
                <span
                  aria-hidden
                  className={`mx-2 h-px flex-1 ${connectorClass(stage.status)}`}
                />
              ) : null}
            </motion.div>
          ))}
        </div>
        <div className="mt-5 grid grid-cols-4 gap-4">
          {stages.map((stage) => (
            <div key={stage.label} className="min-w-0 pr-2">
              <p className="text-sm font-semibold text-foreground">{stage.label}</p>
              <p className="mt-1 truncate text-xs text-muted-foreground">{stage.detail}</p>
              <StatusChip status={stage.status} className="mt-2.5" />
            </div>
          ))}
        </div>
      </div>

      <div className="sm:hidden">
        {stages.map((stage, index) => (
          <div key={stage.label} className="flex gap-4">
            <div className="flex flex-col items-center">
              <span
                className={`flex h-8 w-8 flex-shrink-0 items-center justify-center rounded-full border ${nodeClass(stage.status)}`}
              >
                <span
                  aria-hidden
                  className="h-2 w-2 rounded-full"
                  style={{ background: dotColor(stage.status) }}
                />
              </span>
              {index < stages.length - 1 ? (
                <span
                  aria-hidden
                  className={`my-1 w-px flex-1 ${
                    stage.status === "running" ? "flow-line-y" : "rail-line-idle"
                  }`}
                />
              ) : null}
            </div>
            <div className={`min-w-0 flex-1 ${index < stages.length - 1 ? "pb-6" : ""}`}>
              <div className="flex items-center justify-between gap-3">
                <p className="text-sm font-semibold text-foreground">{stage.label}</p>
                <StatusChip status={stage.status} />
              </div>
              <p className="mt-1 text-xs text-muted-foreground">{stage.detail}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
