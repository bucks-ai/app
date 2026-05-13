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
      className={`rounded-lg border border-[#1C1C1C] ${
        elevated ? "bg-[#141414]" : "bg-[#0F0F0F]"
      } ${className}`}
    >
      {children}
    </section>
  );
}
