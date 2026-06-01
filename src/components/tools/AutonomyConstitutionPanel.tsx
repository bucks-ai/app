import type { AutonomyConstitution, AutonomyRuleCategory } from "@/types/tools";
import { ToolStatusBadge } from "@/components/tools/ToolStatusBadge";
import { DataTile } from "@/components/ui/DataTile";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";

const categoryOrder: AutonomyRuleCategory[] = [
  "Spending",
  "Outreach",
  "Product",
  "Sales",
  "Legal",
];

function formatUsd(value: number) {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 0,
  }).format(value);
}

function getCategoryLabel(category: AutonomyRuleCategory) {
  switch (category) {
    case "Spending":
      return "Spend limits";
    case "Outreach":
      return "Outreach limits";
    case "Product":
      return "Product / deployment limits";
    case "Sales":
      return "Sales limits";
    case "Legal":
      return "Legal / human-only limits";
  }
}

export function AutonomyConstitutionPanel({
  constitution,
}: {
  constitution: AutonomyConstitution;
}) {
  const groupedRules = categoryOrder.map((category) => ({
    category,
    rules: constitution.rules.filter((rule) => rule.category === category),
  }));

  return (
    <OperatorPanel className="p-6 shadow-[0_30px_120px_rgba(0,0,0,0.35)] sm:p-8">
      <div className="flex flex-col gap-4 border-b border-border pb-6">
        <SectionLabel>Default constitution</SectionLabel>
        <div>
          <h2 className="text-3xl font-semibold tracking-tight text-foreground">
            Autonomy Constitution
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-secondary sm:text-base">
            bucks.ai can execute aggressively inside clearly defined limits. The
            constitution below keeps spend, outreach, deployments, sales, and
            legal actions inside a founder-approved operating envelope.
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <DataTile
          label="Spend per action"
          value={formatUsd(constitution.maxSpendPerActionUsd)}
          tone="warning"
        />
        <DataTile
          label="Daily spend cap"
          value={formatUsd(constitution.maxDailySpendUsd)}
        />
        <DataTile
          label="Monthly spend cap"
          value={formatUsd(constitution.maxMonthlySpendUsd)}
          tone="warning"
        />
        <DataTile
          label="Sales discount limit"
          value={`${constitution.maxDiscountPercent}%`}
        />
      </div>

      <div className="mt-8 grid gap-6 xl:grid-cols-2">
        {groupedRules.map(({ category, rules }) => (
          <div
            key={category}
            className="rounded-lg border border-border bg-background p-5 sm:p-6"
          >
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-lg font-semibold text-foreground">
                {getCategoryLabel(category)}
              </h3>
              <ToolStatusBadge label={`${rules.length} rules`} variant="neutral" />
            </div>
            <div className="mt-5 space-y-3">
              {rules.map((rule) => (
                <div
                  key={rule.id}
                  className="rounded-md border border-border bg-surface p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-foreground">
                        {rule.title}
                      </p>
                      <p className="mt-2 text-sm leading-6 text-secondary">
                        {rule.description}
                      </p>
                    </div>
                    <div className="flex flex-wrap justify-end gap-2">
                      <ToolStatusBadge label={rule.value} variant="neutral" />
                      {rule.hardStop ? (
                        <ToolStatusBadge label="Hard stop" variant="danger" />
                      ) : null}
                      {rule.escalationRequired ? (
                        <ToolStatusBadge
                          label="Escalate"
                          variant="warning"
                        />
                      ) : null}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ))}
      </div>
    </OperatorPanel>
  );
}
