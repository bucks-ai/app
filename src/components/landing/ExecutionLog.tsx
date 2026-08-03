"use client";

import { motion, useReducedMotion } from "framer-motion";

export type ExecutionLogItem = {
  time: string;
  actor: string;
  event: string;
  tone?: "accent" | "success" | "warning" | "danger" | "neutral";
};

const toneColor = {
  accent: "var(--accent-bright)",
  success: "var(--status-done)",
  warning: "var(--status-pending)",
  danger: "var(--status-blocked)",
  neutral: "var(--text-muted)",
};

export function ExecutionLog({
  items,
  compact = false,
}: {
  items: ExecutionLogItem[];
  compact?: boolean;
}) {
  const reducedMotion = useReducedMotion();

  return (
    // A log is a list, not a stack of cards. Each row was individually
    // outlined and filled, which turned five lines of text into five boxes;
    // rows are now separated by a hairline only.
    <div className="flow-well p-4">
      <div className="mb-3 flex items-center justify-between gap-3">
        <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
          Execution log
        </p>
        <span className="inline-flex items-center gap-2 rounded-full bg-status-running/10 px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.14em] text-running-on-tint">
          <span aria-hidden className="pulse-dot h-1.5 w-1.5 rounded-full bg-status-running" />
          streaming
        </span>
      </div>
      <div className="divide-y divide-edge">
        {items.map((item, index) => (
          <motion.div
            key={`${item.time}-${item.actor}-${item.event}`}
            className={`grid grid-cols-[3.5rem_minmax(0,1fr)] gap-3 ${
              compact ? "py-2" : "py-2.5"
            }`}
            initial={false}
            whileInView={reducedMotion ? undefined : { opacity: 1, x: 0 }}
            viewport={{ once: true }}
            transition={{ duration: 0.32, delay: index * 0.055 }}
          >
            <span className="font-mono text-[11px] text-muted-foreground">{item.time}</span>
            <p className="min-w-0 text-sm leading-5 text-foreground-secondary">
              <span
                className="font-mono text-[11px] uppercase tracking-[0.14em]"
                style={{ color: toneColor[item.tone ?? "neutral"] }}
              >
                {item.actor}
              </span>{" "}
              {item.event}
            </p>
          </motion.div>
        ))}
      </div>
    </div>
  );
}
