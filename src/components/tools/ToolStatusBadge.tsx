type ToolStatusBadgeVariant =
  | "preferred"
  | "approved"
  | "external"
  | "blocked"
  | "human"
  | "low"
  | "medium"
  | "high"
  | "critical"
  | "success"
  | "warning"
  | "neutral"
  | "danger";

const variantClasses: Record<ToolStatusBadgeVariant, string> = {
  preferred: "border-emerald-500/30 bg-emerald-500/12 text-emerald-300",
  approved: "border-cyan-500/30 bg-cyan-500/12 text-cyan-300",
  external: "border-amber-500/30 bg-amber-500/12 text-amber-300",
  blocked: "border-rose-500/30 bg-rose-500/12 text-rose-300",
  human: "border-orange-500/30 bg-orange-500/12 text-orange-300",
  low: "border-emerald-500/30 bg-emerald-500/12 text-emerald-300",
  medium: "border-yellow-500/30 bg-yellow-500/12 text-yellow-300",
  high: "border-orange-500/30 bg-orange-500/12 text-orange-300",
  critical: "border-rose-500/30 bg-rose-500/12 text-rose-300",
  success: "border-emerald-500/30 bg-emerald-500/12 text-emerald-300",
  warning: "border-amber-500/30 bg-amber-500/12 text-amber-300",
  neutral: "border-white/12 bg-white/6 text-neutral-300",
  danger: "border-rose-500/30 bg-rose-500/12 text-rose-300",
};

type ToolStatusBadgeProps = {
  label: string;
  variant: ToolStatusBadgeVariant;
};

export function ToolStatusBadge({
  label,
  variant,
}: ToolStatusBadgeProps) {
  return (
    <span
      className={`inline-flex rounded-full border px-3 py-1 text-[11px] font-semibold uppercase tracking-[0.2em] ${variantClasses[variant]}`}
    >
      {label}
    </span>
  );
}
