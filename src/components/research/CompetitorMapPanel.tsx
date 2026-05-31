import type { ResearchCompetitorRecord } from "@/types/research-ui";
import { ResearchStatusBadge } from "@/components/research/ResearchStatusBadge";

type CompetitorMapPanelProps = {
  competitors: ResearchCompetitorRecord[];
};

function ListLine({ label, items }: { label: string; items: string[] | null }) {
  return (
    <p className="text-xs leading-5">
      <span className="font-mono uppercase tracking-widest text-[#444]">{label}</span>{" "}
      <span className="break-words text-[#888]">
        {items && items.length > 0 ? items.slice(0, 3).join(", ") : "Not captured"}
      </span>
    </p>
  );
}

export function CompetitorMapPanel({ competitors }: CompetitorMapPanelProps) {
  return (
    <div id="research-competitors" className="scroll-mt-28 rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
          Competitor map
        </p>
        <span className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
          {competitors.length} mapped
        </span>
      </div>

      <div className="mt-3 grid gap-2 lg:grid-cols-3">
        {competitors.length > 0 ? (
          competitors.map((competitor) => (
            <div key={competitor.id} className="min-w-0 rounded border border-[#1C1C1C] bg-[#080808] p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="break-words text-sm font-semibold text-[#F0F0F0]">
                    {competitor.name}
                  </p>
                  <p className="mt-0.5 break-words text-xs text-[#666]">
                    {competitor.category ?? "Category not set"}
                  </p>
                </div>
                <ResearchStatusBadge value={competitor.priority} />
              </div>
              <div className="mt-3 space-y-2">
                <p className="break-words text-xs leading-5 text-[#888]">
                  {competitor.positioning ?? "Positioning not captured."}
                </p>
                <p className="text-xs leading-5">
                  <span className="font-mono uppercase tracking-widest text-[#444]">
                    Pricing
                  </span>{" "}
                  <span className="break-words text-[#888]">
                    {competitor.pricing_summary ?? "Not captured"}
                  </span>
                </p>
                <ListLine label="Strengths" items={competitor.strengths} />
                <ListLine label="Weaknesses" items={competitor.weaknesses} />
                <p className="text-xs leading-5">
                  <span className="font-mono uppercase tracking-widest text-[#444]">
                    Wedge
                  </span>{" "}
                  <span className="break-words text-[#888]">
                    {competitor.wedge_opportunity ?? "Not captured"}
                  </span>
                </p>
              </div>
            </div>
          ))
        ) : (
          <p className="rounded border border-[#1C1C1C] bg-[#080808] px-3 py-4 text-sm text-[#666]">
            No competitors mapped yet.
          </p>
        )}
      </div>
    </div>
  );
}
