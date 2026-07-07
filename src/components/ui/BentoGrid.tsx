import type { ReactNode } from "react";

type BentoGridProps = {
  children: ReactNode;
  className?: string;
};

export function BentoGrid({ children, className = "" }: BentoGridProps) {
  return (
    <div
      className={`grid auto-rows-fr grid-cols-1 gap-4 md:grid-cols-6 ${className}`}
    >
      {children}
    </div>
  );
}
