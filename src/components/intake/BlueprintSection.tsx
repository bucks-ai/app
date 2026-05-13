import type { ReactNode } from "react";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";

type BlueprintSectionProps = {
  title: string;
  description?: string;
  children: ReactNode;
};

export function BlueprintSection({
  title,
  description,
  children,
}: BlueprintSectionProps) {
  return (
    <OperatorPanel className="p-5 shadow-[0_20px_80px_rgba(0,0,0,0.22)] sm:p-6">
      <div className="mb-5 flex items-start justify-between gap-4">
        <div>
          <SectionLabel>Mission Control</SectionLabel>
          <h2 className="mt-2 text-xl font-semibold text-[#F0F0F0]">{title}</h2>
          {description ? (
            <p className="mt-2 max-w-2xl text-sm leading-6 text-[#888888]">
              {description}
            </p>
          ) : null}
        </div>
        <StatusPill label="Draft" variant="accent" className="hidden md:inline-flex" />
      </div>
      {children}
    </OperatorPanel>
  );
}
