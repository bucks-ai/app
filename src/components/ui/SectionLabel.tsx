import type { ReactNode } from "react";

type SectionLabelProps = {
  children: ReactNode;
  tone?: "accent" | "muted" | "warning";
  className?: string;
};

const toneClasses = {
  accent: "text-[#A5B4FC]",
  muted: "text-[#888888]",
  warning: "text-[#FCD34D]",
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
