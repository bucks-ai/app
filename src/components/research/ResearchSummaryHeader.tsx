import type { ResearchWorkspace } from "@/types/research-ui";
import { ResearchStatusBadge } from "@/components/research/ResearchStatusBadge";
import { resolveResearchNextAction } from "@/components/research/ResearchNextActionCard";

type ResearchSummaryHeaderProps = {
  workspace: ResearchWorkspace;
};

export function ResearchSummaryHeader({ workspace }: ResearchSummaryHeaderProps) {
  const summary = workspace.summary;
  const nextAction = resolveResearchNextAction(workspace);

  return (
    <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4 sm:p-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
              Research mode
            </p>
            <ResearchStatusBadge value={summary.status} />
          </div>
          <h2 className="mt-3 text-xl font-semibold text-[#F0F0F0]">
            Map the opportunity before building
          </h2>
          <p className="mt-1 max-w-2xl break-words text-sm leading-6 text-[#888]">
            {nextAction.title}: {nextAction.description}
          </p>
        </div>
        <div className="shrink-0 rounded border border-[#4F46E5]/30 bg-[#4F46E5]/10 px-3 py-2">
          <p className="font-mono text-[10px] uppercase tracking-widest text-[#A5B4FC]">
            Score
          </p>
          <p className="mt-1 text-xl font-semibold text-[#F0F0F0]">
            {summary.opportunityScore ?? "--"}
            <span className="ml-1 text-xs text-[#666]">/100</span>
          </p>
        </div>
      </div>

      <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-5">
        {[
          ["Segments", summary.segmentCount],
          ["Competitors", summary.competitorCount],
          ["Risks", summary.riskCount],
          ["Hypotheses", summary.hypothesisCount],
          ["Evidence", summary.evidenceCount],
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
