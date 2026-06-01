import type { ResearchBuyerBudgetRecord } from "@/types/research-ui";
import { ResearchStatusBadge } from "@/components/research/ResearchStatusBadge";

type BuyerBudgetPanelProps = {
  buyerBudgets: ResearchBuyerBudgetRecord[];
};

function Detail({ label, value }: { label: string; value: string | null }) {
  return (
    <p className="text-xs leading-5">
      <span className="font-mono uppercase tracking-widest text-muted">{label}</span>{" "}
      <span className="break-words text-secondary">{value ?? "Not captured"}</span>
    </p>
  );
}

export function BuyerBudgetPanel({ buyerBudgets }: BuyerBudgetPanelProps) {
  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
          Buyer and budget
        </p>
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
          {buyerBudgets.length} records
        </span>
      </div>

      <div className="mt-3 grid gap-2 lg:grid-cols-2">
        {buyerBudgets.length > 0 ? (
          buyerBudgets.map((budget) => (
            <div key={budget.id} className="min-w-0 rounded border border-border bg-background p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <div className="min-w-0">
                  <p className="break-words text-sm font-semibold text-foreground">
                    {budget.buyer}
                  </p>
                  <p className="mt-0.5 break-words text-xs text-muted">
                    Budget owner: {budget.budget_owner ?? "Not captured"}
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <ResearchStatusBadge value={budget.priority} />
                  <ResearchStatusBadge value={budget.confidence} />
                </div>
              </div>
              <div className="mt-3 space-y-2">
                <Detail label="Existing spend" value={budget.existing_spend} />
                <Detail label="WTP" value={budget.willingness_to_pay} />
                <Detail label="Value driver" value={budget.value_driver} />
                <Detail label="Pricing signal" value={budget.pricing_signal} />
              </div>
            </div>
          ))
        ) : (
          <p className="rounded border border-border bg-background px-3 py-4 text-sm text-muted">
            No buyer budget records yet.
          </p>
        )}
      </div>
    </div>
  );
}
