import type { ResearchHypothesisRecord } from "@/types/research-ui";
import { ResearchStatusBadge } from "@/components/research/ResearchStatusBadge";

type ResearchHypothesesPanelProps = {
  hypotheses: ResearchHypothesisRecord[];
};

export function ResearchHypothesesPanel({
  hypotheses,
}: ResearchHypothesesPanelProps) {
  return (
    <div id="research-hypotheses" className="scroll-mt-28 rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
          Research hypotheses
        </p>
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
          {hypotheses.length} hypotheses
        </span>
      </div>

      <div className="mt-3 space-y-2">
        {hypotheses.length > 0 ? (
          hypotheses.map((hypothesis) => (
            <div key={hypothesis.id} className="rounded border border-border bg-background p-3">
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="break-words text-sm font-semibold text-foreground">
                      {hypothesis.title}
                    </p>
                    <ResearchStatusBadge value={hypothesis.priority} />
                    <ResearchStatusBadge value={hypothesis.confidence} />
                  </div>
                  <p className="mt-2 break-words text-xs leading-5 text-secondary">
                    {hypothesis.description ?? "Description not captured."}
                  </p>
                </div>
              </div>
              <div className="mt-3 grid gap-2 md:grid-cols-2">
                <div className="rounded border border-border bg-surface p-2.5">
                  <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
                    Test method
                  </p>
                  <p className="mt-1 break-words text-xs leading-5 text-secondary">
                    {hypothesis.test_method ?? "Not captured"}
                  </p>
                </div>
                <div className="rounded border border-border bg-surface p-2.5">
                  <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
                    Success criteria
                  </p>
                  <p className="mt-1 break-words text-xs leading-5 text-secondary">
                    {hypothesis.success_criteria ?? "Not captured"}
                  </p>
                </div>
              </div>
            </div>
          ))
        ) : (
          <p className="rounded border border-border bg-background px-3 py-4 text-sm text-muted">
            No research hypotheses yet.
          </p>
        )}
      </div>
    </div>
  );
}
