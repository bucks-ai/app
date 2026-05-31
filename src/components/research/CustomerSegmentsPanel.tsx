import type { ResearchCustomerSegmentRecord } from "@/types/research-ui";
import { ResearchStatusBadge } from "@/components/research/ResearchStatusBadge";

type CustomerSegmentsPanelProps = {
  segments: ResearchCustomerSegmentRecord[];
};

function score(value: number | null) {
  return value === null ? "--" : `${value}/10`;
}

function InlineList({ items }: { items: string[] | null }) {
  if (!items || items.length === 0) return <span className="text-[#555]">Not captured</span>;

  return (
    <span className="break-words text-[#888]">
      {items.slice(0, 3).join(", ")}
      {items.length > 3 ? ` +${items.length - 3}` : ""}
    </span>
  );
}

export function CustomerSegmentsPanel({ segments }: CustomerSegmentsPanelProps) {
  return (
    <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
          Customer segments
        </p>
        <span className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
          {segments.length} total
        </span>
      </div>

      <div className="mt-3 grid gap-2 lg:grid-cols-2">
        {segments.length > 0 ? (
          segments.map((segment) => (
            <div
              key={segment.id}
              className="min-w-0 rounded border border-[#1C1C1C] bg-[#080808] p-3"
            >
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="break-words text-sm font-semibold text-[#F0F0F0]">
                    {segment.name}
                  </p>
                  <p className="mt-1 break-words text-xs leading-5 text-[#888]">
                    {segment.description ?? "No description captured."}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <ResearchStatusBadge value={segment.priority} />
                  <ResearchStatusBadge value={segment.confidence} />
                </div>
              </div>

              <div className="mt-3 grid grid-cols-3 gap-2">
                {[
                  ["Pain", score(segment.pain_level)],
                  ["Pay", score(segment.ability_to_pay)],
                  ["Reach", score(segment.reachability)],
                ].map(([label, value]) => (
                  <div key={label} className="rounded border border-[#1C1C1C] bg-[#0F0F0F] p-2">
                    <p className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
                      {label}
                    </p>
                    <p className="mt-1 text-xs font-semibold text-[#D4D4D4]">{value}</p>
                  </div>
                ))}
              </div>

              <div className="mt-3 space-y-2 text-xs leading-5">
                <p>
                  <span className="font-mono uppercase tracking-widest text-[#444]">
                    Market
                  </span>{" "}
                  <span className="break-words text-[#888]">
                    {segment.market_size_guess ?? "Not captured"}
                  </span>
                </p>
                <p>
                  <span className="font-mono uppercase tracking-widest text-[#444]">
                    Channels
                  </span>{" "}
                  <InlineList items={segment.channels} />
                </p>
              </div>
            </div>
          ))
        ) : (
          <p className="rounded border border-[#1C1C1C] bg-[#080808] px-3 py-4 text-sm text-[#666]">
            No customer segments yet.
          </p>
        )}
      </div>
    </div>
  );
}
