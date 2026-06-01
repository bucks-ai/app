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
    <div className="rounded-lg border border-border bg-surface p-4 sm:p-5">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
              Research mode
            </p>
            <ResearchStatusBadge value={summary.status} />
          </div>
          <h2 className="mt-3 text-xl font-semibold text-foreground">
            Map the opportunity before building
          </h2>
          <p className="mt-1 max-w-2xl break-words text-sm leading-6 text-secondary">
            {nextAction.title}: {nextAction.description}
          </p>
        </div>
        <div className="shrink-0 rounded border border-accent/30 bg-accent/10 px-3 py-2">
          <p className="font-mono text-[10px] uppercase tracking-widest text-accent">
            Score
          </p>
          <p className="mt-1 text-xl font-semibold text-foreground">
            {summary.opportunityScore ?? "--"}
            <span className="ml-1 text-xs text-muted">/100</span>
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
            className="min-w-0 rounded border border-border bg-background px-3 py-2.5"
          >
            <p className="truncate font-mono text-[10px] uppercase tracking-widest text-muted">
              {label}
            </p>
            <p className="mt-1 text-lg font-semibold text-foreground">{value}</p>
          </div>
        ))}
      </div>
    </div>
  );
}
