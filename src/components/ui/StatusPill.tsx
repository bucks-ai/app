type StatusPillVariant =
  | "accent"
  | "success"
  | "warning"
  | "danger"
  | "neutral";

const variantClasses: Record<StatusPillVariant, string> = {
  accent: "border-accent/35 bg-accent/10 text-accent",
  success: "border-success/25 bg-success/10 text-success",
  warning: "border-warning/35 bg-warning/10 text-warning",
  danger: "border-error/35 bg-error/10 text-error",
  neutral: "border-border bg-elevated text-secondary",
};

type StatusPillProps = {
  label: string;
  variant?: StatusPillVariant;
  className?: string;
};

export function StatusPill({
  label,
  variant = "neutral",
  className = "",
}: StatusPillProps) {
  return (
    <span
      className={`inline-flex w-fit items-center rounded-md border px-2.5 py-1 font-mono text-[11px] font-medium uppercase tracking-[0.18em] ${variantClasses[variant]} ${className}`}
    >
      {label}
    </span>
  );
}
