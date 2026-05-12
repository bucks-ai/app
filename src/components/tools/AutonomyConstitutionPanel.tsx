import type { AutonomyConstitution, AutonomyRuleCategory } from "@/types/tools";
import { ToolStatusBadge } from "@/components/tools/ToolStatusBadge";

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
    <section className="rounded-[2rem] border border-white/10 bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.18),_transparent_36%),linear-gradient(180deg,rgba(255,255,255,0.08),rgba(255,255,255,0.03))] p-7 shadow-[0_30px_120px_rgba(0,0,0,0.35)] backdrop-blur-sm sm:p-8">
      <div className="flex flex-col gap-4 border-b border-white/8 pb-6">
        <div className="inline-flex w-fit rounded-full border border-emerald-500/30 bg-emerald-500/12 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-emerald-300">
          Default constitution
        </div>
        <div>
          <h2 className="text-3xl font-semibold tracking-tight text-white">
            Autonomy Constitution
          </h2>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-neutral-300 sm:text-base">
            bucks.ai can execute aggressively inside clearly defined limits. The
            constitution below keeps spend, outreach, deployments, sales, and
            legal actions inside a founder-approved operating envelope.
          </p>
        </div>
      </div>

      <div className="mt-6 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-3xl border border-white/10 bg-black/25 p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-neutral-500">
            Spend per action
          </p>
          <p className="mt-3 text-3xl font-semibold text-white">
            {formatUsd(constitution.maxSpendPerActionUsd)}
          </p>
        </div>
        <div className="rounded-3xl border border-white/10 bg-black/25 p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-neutral-500">
            Daily spend cap
          </p>
          <p className="mt-3 text-3xl font-semibold text-white">
            {formatUsd(constitution.maxDailySpendUsd)}
          </p>
        </div>
        <div className="rounded-3xl border border-white/10 bg-black/25 p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-neutral-500">
            Monthly spend cap
          </p>
          <p className="mt-3 text-3xl font-semibold text-white">
            {formatUsd(constitution.maxMonthlySpendUsd)}
          </p>
        </div>
        <div className="rounded-3xl border border-white/10 bg-black/25 p-5">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-neutral-500">
            Sales discount limit
          </p>
          <p className="mt-3 text-3xl font-semibold text-white">
            {constitution.maxDiscountPercent}%
          </p>
        </div>
      </div>

      <div className="mt-8 grid gap-6 xl:grid-cols-2">
        {groupedRules.map(({ category, rules }) => (
          <div
            key={category}
            className="rounded-3xl border border-white/10 bg-black/25 p-6"
          >
            <div className="flex items-center justify-between gap-3">
              <h3 className="text-lg font-semibold text-white">{category}</h3>
              <ToolStatusBadge label={`${rules.length} rules`} variant="neutral" />
            </div>
            <div className="mt-5 space-y-3">
              {rules.map((rule) => (
                <div
                  key={rule.id}
                  className="rounded-2xl border border-white/8 bg-white/[0.03] p-4"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-white">
                        {rule.title}
                      </p>
                      <p className="mt-2 text-sm leading-6 text-neutral-400">
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
    </section>
  );
}
