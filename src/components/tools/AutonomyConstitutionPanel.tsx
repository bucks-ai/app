import type { AutonomyConstitution, AutonomyRuleCategory } from "@/types/tools";
import { ToolStatusBadge } from "@/components/tools/ToolStatusBadge";
import { MetricStat } from "@/components/ui/MetricStat";
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

/**
 * The constitution reads like an operating document: numbered articles,
 * ledger rows, and unmistakable hard-stop / escalate treatments.
 */
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
    <OperatorPanel className="p-6 sm:p-8">
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

      {/* headline caps */}
      <div className="mt-8 grid gap-x-8 gap-y-6 sm:grid-cols-2 xl:grid-cols-4">
        <MetricStat
          label="Spend per action"
          value={formatUsd(constitution.maxSpendPerActionUsd)}
          tone="warning"
        />
        <MetricStat
          label="Daily spend cap"
          value={formatUsd(constitution.maxDailySpendUsd)}
        />
        <MetricStat
          label="Monthly spend cap"
          value={formatUsd(constitution.maxMonthlySpendUsd)}
          tone="warning"
        />
        <MetricStat
          label="Sales discount limit"
          value={`${constitution.maxDiscountPercent}%`}
        />
      </div>

      {/* articles */}
      <div className="mt-10 space-y-8">
        {groupedRules.map(({ category, rules }, articleIndex) => (
          <section key={category}>
            <div className="flex items-baseline justify-between gap-3 border-b border-border-subtle pb-3">
              <div className="flex items-baseline gap-3">
                <span className="font-mono text-xs font-semibold uppercase tracking-[0.24em] text-accent-bright">
                  §{String(articleIndex + 1).padStart(2, "0")}
                </span>
                <h3 className="text-lg font-semibold text-foreground">
                  {getCategoryLabel(category)}
                </h3>
              </div>
              <span className="font-mono text-xs text-muted">
                {rules.length} rules
              </span>
            </div>

            <div className="mt-1 divide-y divide-border-subtle">
              {rules.map((rule) => {
                const edge = rule.hardStop
                  ? "border-l-2 border-l-risk-critical/70"
                  : rule.escalationRequired
                    ? "border-l-2 border-l-risk-medium/70"
                    : "border-l-2 border-l-transparent";
                return (
                  <div
                    key={rule.id}
                    className={`flex flex-wrap items-start justify-between gap-3 py-4 pl-4 ${edge}`}
                  >
                    <div className="min-w-0 max-w-xl">
                      <p className="text-sm font-semibold text-foreground">
                        {rule.title}
                      </p>
                      <p className="mt-1.5 text-sm leading-6 text-secondary">
                        {rule.description}
                      </p>
                    </div>
                    <div className="flex flex-wrap justify-end gap-2">
                      <ToolStatusBadge label={rule.value} variant="neutral" />
                      {rule.hardStop ? (
                        <ToolStatusBadge label="Hard stop" variant="danger" />
                      ) : null}
                      {rule.escalationRequired ? (
                        <ToolStatusBadge label="Escalate" variant="warning" />
                      ) : null}
                    </div>
                  </div>
                );
              })}
            </div>
          </section>
        ))}
      </div>
    </OperatorPanel>
  );
}
