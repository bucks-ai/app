import type { ReactNode } from "react";

type OperatorPanelProps = {
  children: ReactNode;
  id?: string;
  className?: string;
  elevated?: boolean;
};

export function OperatorPanel({
  children,
  id,
  className = "",
  elevated = false,
}: OperatorPanelProps) {
  return (
    <section
      id={id}
      className={`rounded-card border border-border shadow-[var(--shadow-soft)] ${
        elevated ? "bg-elevated" : "bg-surface"
      } ${className}`}
    >
      {children}
    </section>
  );
}
