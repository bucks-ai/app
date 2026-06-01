import type { ResearchEvidenceRecord } from "@/types/research-ui";
import { ResearchStatusBadge } from "@/components/research/ResearchStatusBadge";

type ResearchEvidencePanelProps = {
  evidence: ResearchEvidenceRecord[];
};

export function ResearchEvidencePanel({ evidence }: ResearchEvidencePanelProps) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
          Evidence
        </p>
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
          {evidence.length} records
        </span>
      </div>

      <div className="mt-3 grid gap-2 lg:grid-cols-2">
        {evidence.length > 0 ? (
          evidence.map((record) => (
            <div key={record.id} className="min-w-0 rounded border border-border bg-background p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="min-w-0 break-words text-sm font-semibold text-foreground">
                  {record.claim}
                </p>
                <ResearchStatusBadge value={record.confidence} />
              </div>
              <div className="mt-3 space-y-2 text-xs leading-5">
                <p>
                  <span className="font-mono uppercase tracking-widest text-muted">
                    Source
                  </span>{" "}
                  <span className="break-words text-secondary">
                    {record.source ?? "Not captured"}
                  </span>
                </p>
                <p>
                  <span className="font-mono uppercase tracking-widest text-muted">
                    Type
                  </span>{" "}
                  <span className="break-words text-secondary">
                    {record.evidence_type ?? "Not captured"}
                  </span>
                </p>
                {record.source_url ? (
                  <a
                    href={record.source_url}
                    target="_blank"
                    rel="noreferrer"
                    className="block break-all text-accent hover:text-accent"
                  >
                    {record.source_url}
                  </a>
                ) : null}
                <p className="break-words text-secondary">
                  {record.notes ?? "No notes captured."}
                </p>
              </div>
            </div>
          ))
        ) : (
          <p className="rounded border border-border bg-background px-3 py-4 text-sm text-muted">
            No evidence records yet.
          </p>
        )}
      </div>
    </div>
  );
}
