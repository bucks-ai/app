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
    <OperatorPanel className="p-6 sm:p-8">
      {/* keyed on step so each step slides in; animation is disabled under reduced motion */}
      <div key={step} className="step-in">
        <div className="mb-8 flex flex-col gap-5 border-b border-border pb-6 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <SectionLabel>{`Step ${step} of ${totalSteps}`}</SectionLabel>
            <h2 className="mt-3 text-2xl font-semibold tracking-tight text-foreground sm:text-3xl">
              {title}
            </h2>
            <p className="mt-3 max-w-2xl text-sm leading-6 text-secondary sm:text-base">
              {description}
            </p>
          </div>
          <StatusPill label="Intake wizard" />
        </div>
        {children}
      </div>
    </OperatorPanel>
  );
}
