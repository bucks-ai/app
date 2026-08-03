export type RiskTone = "low" | "medium" | "high" | "critical";

/*
  `color` reads the *-on-tint tokens, not the raw --risk-* hues.
  The raw hues are tuned to sit on a dark surface; used as 11px text on their
  own light tint they measured 3.4-4.4:1. The dot and the border keep the raw
  hue — those are non-text and only need 3:1.
*/
const riskStyles: Record<
  RiskTone,
  { color: string; dot: string; bg: string; border: string }
> = {
  low: {
    color: "var(--risk-low-on-tint)",
    dot: "var(--risk-low)",
    bg: "var(--success-soft)",
    border: "color-mix(in srgb, var(--risk-low) 30%, transparent)",
  },
  medium: {
    color: "var(--risk-medium-on-tint)",
    dot: "var(--risk-medium)",
    bg: "var(--warning-soft)",
    border: "color-mix(in srgb, var(--risk-medium) 30%, transparent)",
  },
  high: {
    color: "var(--risk-high-on-tint)",
    dot: "var(--risk-high)",
    bg: "var(--high-soft)",
    border: "color-mix(in srgb, var(--risk-high) 30%, transparent)",
  },
  critical: {
    color: "var(--risk-critical-on-tint)",
    dot: "var(--risk-critical)",
    bg: "var(--error-soft)",
    border: "color-mix(in srgb, var(--risk-critical) 35%, transparent)",
  },
};

/**
 * Risk badge for tools and constitution rules. Mono, uppercase, always
 * paired with the word so color is never the only signal.
 */
export function RiskBadge({
  level,
  label,
  className = "",
}: {
  level: RiskTone;
  label?: string;
  className?: string;
}) {
  const style = riskStyles[level];
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-md border px-2 py-0.5 font-mono text-[11px] font-medium uppercase tracking-wider ${className}`}
      style={{
        color: style.color,
        background: style.bg,
        borderColor: style.border,
      }}
    >
      <span
        aria-hidden
        className="h-1.5 w-1.5 rounded-full"
        style={{ background: style.dot }}
      />
      {label ?? `${level} risk`}
    </span>
  );
}
