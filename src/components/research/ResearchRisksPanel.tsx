import type { ResearchRiskRecord } from "@/types/research-ui";
import { ResearchStatusBadge } from "@/components/research/ResearchStatusBadge";

type ResearchRisksPanelProps = {
  risks: ResearchRiskRecord[];
};

export function ResearchRisksPanel({ risks }: ResearchRisksPanelProps) {
  return (
    <div id="research-risks" className="scroll-mt-28 rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
          Risks
        </p>
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
          {risks.length} tracked
        </span>
      </div>

      <div className="mt-3 grid gap-2 lg:grid-cols-3">
        {risks.length > 0 ? (
          risks.map((risk) => (
            <div key={risk.id} className="min-w-0 rounded border border-border bg-background p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="min-w-0 break-words text-sm font-semibold text-foreground">
                  {risk.title}
                </p>
                <div className="flex flex-wrap gap-2">
                  <ResearchStatusBadge value={risk.severity} />
                  <ResearchStatusBadge value={risk.priority} />
                </div>
              </div>
              <p className="mt-3 break-words text-xs leading-5 text-secondary">
                {risk.description ?? "Description not captured."}
              </p>
              <p className="mt-2 text-xs leading-5">
                <span className="font-mono uppercase tracking-widest text-muted">
                  Mitigation
                </span>{" "}
                <span className="break-words text-secondary">
                  {risk.mitigation ?? "Not captured"}
                </span>
              </p>
            </div>
          ))
        ) : (
          <p className="rounded border border-border bg-background px-3 py-4 text-sm text-muted">
            No risks tracked yet.
          </p>
        )}
      </div>
    </div>
  );
}
