export type PipelineStatus = "done" | "running" | "queued" | "blocked" | "pending";

const statusConfig: Record<
  PipelineStatus,
  { label: string; color: string; pulse: boolean }
> = {
  done: { label: "Done", color: "var(--status-done)", pulse: false },
  running: { label: "Running", color: "var(--status-running)", pulse: true },
  queued: { label: "Queued", color: "var(--status-queued)", pulse: false },
  blocked: { label: "Blocked", color: "var(--status-blocked)", pulse: false },
  pending: { label: "Pending", color: "var(--status-pending)", pulse: false },
};

/**
 * Pipeline status chip. Running state pulses (disabled under
 * prefers-reduced-motion); label text always accompanies the color dot.
 */
export function StatusChip({
  status,
  label,
  className = "",
}: {
  status: PipelineStatus;
  label?: string;
  className?: string;
}) {
  const config = statusConfig[status];
  return (
    <span
      className={`inline-flex flex-shrink-0 items-center gap-1.5 rounded-full border border-border bg-surface px-2.5 py-1 font-mono text-[11px] font-medium uppercase tracking-wider text-secondary ${className}`}
    >
      <span
        aria-hidden
        className={`h-1.5 w-1.5 rounded-full ${config.pulse ? "pulse-dot" : ""}`}
        style={{ background: config.color }}
      />
      {label ?? config.label}
    </span>
  );
}
