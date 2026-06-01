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
  preferred: "border-accent/35 bg-accent/10 text-accent",
  approved: "border-border bg-elevated text-secondary",
  external: "border-warning/35 bg-warning/10 text-warning",
  blocked: "border-error/35 bg-error/10 text-error",
  human: "border-warning/35 bg-warning/10 text-warning",
  low: "border-success/25 bg-success/10 text-success",
  medium: "border-warning/25 bg-warning/10 text-warning",
  high: "border-warning/35 bg-warning/10 text-warning",
  critical: "border-error/35 bg-error/10 text-error",
  success: "border-success/25 bg-success/10 text-success",
  warning: "border-warning/35 bg-warning/10 text-warning",
  neutral: "border-border bg-elevated text-secondary",
  danger: "border-error/35 bg-error/10 text-error",
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
      className={`inline-flex w-fit rounded-md border px-2.5 py-1 font-mono text-[11px] font-medium uppercase tracking-[0.18em] ${variantClasses[variant]}`}
    >
      {label}
    </span>
  );
}
