import type { ReactNode } from "react";

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
    <section className="rounded-[2rem] border border-white/10 bg-white/[0.04] p-6 shadow-[0_20px_80px_rgba(0,0,0,0.22)] backdrop-blur-sm sm:p-8">
      <div className="mb-8 flex flex-col gap-5 border-b border-white/8 pb-6 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.28em] text-emerald-400/80">
            Step {step} of {totalSteps}
          </p>
          <h2 className="mt-3 text-2xl font-semibold tracking-tight text-white sm:text-3xl">
            {title}
          </h2>
          <p className="mt-3 max-w-2xl text-sm leading-6 text-neutral-400 sm:text-base">
            {description}
          </p>
        </div>
        <div className="rounded-full border border-white/10 bg-black/30 px-4 py-2 text-xs font-medium uppercase tracking-[0.22em] text-neutral-400">
          Intake wizard
        </div>
      </div>
      {children}
    </section>
  );
}
