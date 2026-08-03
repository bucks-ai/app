type StatusPillVariant =
  | "accent"
  | "success"
  | "warning"
  | "danger"
  | "neutral";

/*
  Tint carries the meaning. The outline was a second signal doing the same
  job, and it made every label read as one more little box. A 12% fill plus
  the text colour is enough, and it matches StatusChip's weight so the two
  primitives stop looking like they came from different systems.
*/
const variantClasses: Record<StatusPillVariant, string> = {
  // accent uses the on-tint variant: --accent is the *surface* teal, and as
  // 11px text on its own 12% tint it only reached ~3.9:1.
  accent: "bg-accent/12 text-accent-on-tint",
  success: "bg-success/12 text-success",
  warning: "bg-warning/12 text-warning",
  danger: "bg-error/12 text-error",
  neutral: "bg-muted text-foreground-secondary",
};

type StatusPillProps = {
  label: string;
  variant?: StatusPillVariant;
  className?: string;
};

/**
 * A text-first status label.
 *
 * Chip vocabulary rule: `StatusPill` never carries a leading dot. The dot
 * belongs to `StatusChip`, where it encodes live pipeline state — having it
 * appear on some labels and not others is what made it meaningless.
 */
export function StatusPill({
  label,
  variant = "neutral",
  className = "",
}: StatusPillProps) {
  return (
    <span
      className={`inline-flex w-fit items-center rounded-full px-2.5 py-1 font-mono text-[11px] font-medium uppercase tracking-[0.18em] ${variantClasses[variant]} ${className}`}
    >
      {label}
    </span>
  );
}
