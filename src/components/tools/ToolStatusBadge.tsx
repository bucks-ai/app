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
  preferred: "border-accent/35 bg-accent/10 text-accent-bright",
  approved: "border-border bg-elevated text-foreground-secondary",
  external: "border-warning/35 bg-warning/10 text-warning",
  blocked: "border-error/35 bg-error/10 text-error",
  human: "border-warning/35 bg-warning/10 text-warning",
  low: "border-risk-low/25 bg-risk-low/10 text-risk-low",
  medium: "border-risk-medium/25 bg-risk-medium/10 text-risk-medium",
  high: "border-risk-high/35 bg-risk-high/10 text-risk-high",
  critical: "border-risk-critical/35 bg-risk-critical/10 text-risk-critical",
  success: "border-success/25 bg-success/10 text-success",
  warning: "border-warning/35 bg-warning/10 text-warning",
  neutral: "border-border bg-elevated text-foreground-secondary",
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
