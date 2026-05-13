import type { ReactNode } from "react";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";

type IntakeStepProps = {
  step: number;
  totalSteps: number;
  title: string;
  description: string;
  children: ReactNode;
};

export function IntakeStep({
  step,
  totalSteps,
  title,
  description,
  children,
}: IntakeStepProps) {
  return (
    <OperatorPanel className="p-6 shadow-[0_20px_80px_rgba(0,0,0,0.22)] sm:p-8">
      <div className="mb-8 flex flex-col gap-5 border-b border-[#1C1C1C] pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <SectionLabel>{`Step ${step} of ${totalSteps}`}</SectionLabel>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-[#F0F0F0] sm:text-3xl">
            {title}
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-[#888888] sm:text-base">
            {description}
          </p>
        </div>
        <StatusPill label="Intake wizard" />
      </div>
      {children}
    </OperatorPanel>
  );
}
