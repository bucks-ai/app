import type { ReactNode } from "react";

type SectionLabelProps = {
  children: ReactNode;
  tone?: "accent" | "muted" | "warning";
  className?: string;
};

const toneClasses = {
  accent: "text-accent",
  muted: "text-secondary",
  warning: "text-warning",
};

export function SectionLabel({
  children,
  tone = "accent",
  className = "",
}: SectionLabelProps) {
  return (
    <p
      className={`font-mono text-xs font-medium uppercase tracking-[0.24em] ${toneClasses[tone]} ${className}`}
    >
      {children}
    </p>
  );
}
