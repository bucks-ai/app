import { SectionLabel } from "@/components/ui/SectionLabel";

type MetricStatProps = {
  label: string;
  value: string;
  detail?: string;
  tone?: "accent" | "success" | "warning" | "danger" | "neutral";
  className?: string;
};

const valueToneClasses = {
  accent: "text-accent-bright",
  success: "text-success",
  warning: "text-warning",
  danger: "text-error",
  neutral: "text-foreground",
};

const barToneStyles = {
  accent: "var(--accent)",
  success: "var(--status-done)",
  warning: "var(--risk-medium)",
  danger: "var(--risk-critical)",
  neutral: "var(--border-strong)",
};

/**
 * Lead stat for dense operator pages: mono numeral, hairline top rule with
 * a colored tick that echoes the flow-rail motif.
 */
export function MetricStat({
  label,
  value,
  detail,
  tone = "neutral",
  className = "",
}: MetricStatProps) {
  return (
    <div className={`relative border-t border-border pt-4 ${className}`}>
      <span
        aria-hidden
        className="absolute -top-px left-0 h-px w-8"
        style={{ background: barToneStyles[tone] }}
      />
      <SectionLabel tone="muted">{label}</SectionLabel>
      <p
        className={`mt-2 font-mono text-4xl font-semibold tracking-tight ${valueToneClasses[tone]}`}
      >
        {value}
      </p>
      {detail ? (
        <p className="mt-2 text-sm leading-6 text-foreground-secondary">{detail}</p>
      ) : null}
    </div>
  );
}
