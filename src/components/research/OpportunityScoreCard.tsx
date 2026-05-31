import type { ResearchReportRecord } from "@/types/research-ui";
import { ResearchStatusBadge } from "@/components/research/ResearchStatusBadge";

type OpportunityScoreCardProps = {
  report: ResearchReportRecord | null;
};

function Field({ label, value }: { label: string; value: string | null | undefined }) {
  return (
    <div className="min-w-0 rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2.5">
      <p className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
        {label}
      </p>
      <p className="mt-1 break-words text-xs leading-5 text-[#D4D4D4]">
        {value ?? "Not captured"}
      </p>
    </div>
  );
}

export function OpportunityScoreCard({ report }: OpportunityScoreCardProps) {
  const score = report?.opportunity_score;
  const scoreLabel = score === null || score === undefined ? "--" : String(score);

  return (
    <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
      <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
        <div className="min-w-0">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
            Opportunity score
          </p>
          <p className="mt-3 text-4xl font-semibold tracking-tight text-[#F0F0F0]">
            {scoreLabel}
            <span className="ml-1 text-base text-[#444]">/100</span>
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <ResearchStatusBadge value={report?.confidence} />
          <ResearchStatusBadge value={report?.priority} />
        </div>
      </div>

      <div className="mt-4 grid gap-2 lg:grid-cols-2">
        <Field label="Thesis" value={report?.thesis} />
        <Field label="Target customer" value={report?.target_customer} />
        <Field label="Money pool" value={report?.money_pool} />
        <Field label="Wedge" value={report?.wedge} />
      </div>

      <div className="mt-2 rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2.5">
        <p className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
          Recommendation
        </p>
        <p className="mt-1 break-words text-sm leading-6 text-[#D4D4D4]">
          {report?.recommendation ?? "Not captured"}
        </p>
      </div>
    </div>
  );
}
