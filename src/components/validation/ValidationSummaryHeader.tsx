import type { ValidationWorkspace } from "@/types/validation-ui";
import { ValidationStatusBadge } from "@/components/validation/ValidationStatusBadge";
import { resolveValidationNextAction } from "@/components/validation/ValidationNextActionCard";

type ValidationSummaryHeaderProps = {
  workspace: ValidationWorkspace;
};

export function ValidationSummaryHeader({ workspace }: ValidationSummaryHeaderProps) {
  const summary = workspace.summary;
  const nextAction = resolveValidationNextAction(workspace);

  return (
    <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4 sm:p-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
              Customer validation
            </p>
            <ValidationStatusBadge value={summary.status} />
          </div>
          <h2 className="mt-3 text-xl font-semibold text-[#F0F0F0]">
            Validate demand before overbuilding
          </h2>
          <p className="mt-1 max-w-2xl text-sm leading-6 text-[#888]">
            {nextAction.title}: {nextAction.description}
          </p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-5">
        {[
          ["Personas", summary.personaCount],
          ["Hypotheses", summary.hypothesisCount],
          ["Leads", summary.leadCount],
          ["Feedback", summary.feedbackNoteCount],
          ["Strong signal", summary.strongSignalCount],
        ].map(([label, value]) => (
          <div
            key={label}
            className="min-w-0 rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2.5"
          >
            <p className="truncate font-mono text-[10px] uppercase tracking-widest text-[#444]">
              {label}
            </p>
            <p className="mt-1 text-lg font-semibold text-[#F0F0F0]">{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
