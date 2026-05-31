import type { ResearchMonetizationModelRecord } from "@/types/research-ui";
import { ResearchStatusBadge } from "@/components/research/ResearchStatusBadge";

type MonetizationPanelProps = {
  models: ResearchMonetizationModelRecord[];
};

export function MonetizationPanel({ models }: MonetizationPanelProps) {
  return (
    <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
          Monetization
        </p>
        <span className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
          {models.length} models
        </span>
      </div>

      <div className="mt-3 grid gap-2 lg:grid-cols-2">
        {models.length > 0 ? (
          models.map((model) => (
            <div key={model.id} className="min-w-0 rounded border border-[#1C1C1C] bg-[#080808] p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="break-words text-sm font-semibold text-[#F0F0F0]">
                    {model.model}
                  </p>
                  <p className="mt-0.5 break-words text-xs text-[#666]">
                    Buyer: {model.buyer ?? "Not captured"}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <ResearchStatusBadge value={model.priority} />
                  <ResearchStatusBadge value={model.confidence} />
                </div>
              </div>
              <div className="mt-3 space-y-2 text-xs leading-5">
                <p>
                  <span className="font-mono uppercase tracking-widest text-[#444]">
                    Price
                  </span>{" "}
                  <span className="break-words text-[#888]">
                    {model.price_assumption ?? "Not captured"}
                  </span>
                </p>
                <p>
                  <span className="font-mono uppercase tracking-widest text-[#444]">
                    Metric
                  </span>{" "}
                  <span className="break-words text-[#888]">
                    {model.value_metric ?? "Not captured"}
                  </span>
                </p>
                <p className="break-words text-[#888]">
                  {model.reasoning ?? "Reasoning not captured."}
                </p>
              </div>
            </div>
          ))
        ) : (
          <p className="rounded border border-[#1C1C1C] bg-[#080808] px-3 py-4 text-sm text-[#666]">
            No monetization models yet.
          </p>
        )}
      </div>
    </div>
  );
}
