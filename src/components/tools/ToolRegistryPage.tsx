import { Footer } from "@/components/shared/Footer";
import { Navbar } from "@/components/shared/Navbar";
import { AutonomyConstitutionPanel } from "@/components/tools/AutonomyConstitutionPanel";
import { ToolCard } from "@/components/tools/ToolCard";
import { ToolStatusBadge } from "@/components/tools/ToolStatusBadge";
import { autonomyConstitution } from "@/lib/autonomy-constitution";
import { extendedTools, preferredTools, toolRegistry } from "@/lib/tool-registry";

function SummaryCard({
  label,
  value,
  detail,
}: {
  label: string;
  value: string;
  detail: string;
}) {
  return (
    <div className="rounded-3xl border border-white/10 bg-white/[0.04] p-5 shadow-[0_20px_70px_rgba(0,0,0,0.24)] backdrop-blur-sm">
      <p className="text-xs font-semibold uppercase tracking-[0.24em] text-neutral-500">
        {label}
      </p>
      <p className="mt-3 text-3xl font-semibold tracking-tight text-white">
        {value}
      </p>
      <p className="mt-3 text-sm leading-6 text-neutral-400">{detail}</p>
    </div>
  );
}

function RuleList({
  title,
  items,
  badge,
}: {
  title: string;
  items: string[];
  badge: string;
}) {
  return (
    <section className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-6 shadow-[0_20px_70px_rgba(0,0,0,0.24)] backdrop-blur-sm">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-2xl font-semibold text-white">{title}</h2>
        <ToolStatusBadge label={badge} variant="warning" />
      </div>
      <ul className="mt-5 space-y-3">
        {items.map((item) => (
          <li
            key={item}
            className="rounded-2xl border border-white/8 bg-black/25 px-4 py-3 text-sm leading-6 text-neutral-300"
          >
            {item}
          </li>
        ))}
      </ul>
    </section>
  );
}

export function ToolRegistryPage() {
  const blockedOrHumanOnly = toolRegistry.filter(
    (tool) => tool.status === "Blocked" || tool.status === "Human Only",
  ).length;

  const highRiskTools = toolRegistry.filter(
    (tool) => tool.riskLevel === "High" || tool.riskLevel === "Critical",
  ).length;

  return (
    <>
      <Navbar />
      <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.14),_transparent_22%),linear-gradient(180deg,#020202_0%,#050505_35%,#09090b_100%)] px-6 pb-20 pt-28">
        <div className="mx-auto max-w-7xl space-y-10">
          <section className="overflow-hidden rounded-[2.25rem] border border-white/10 bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.22),_transparent_35%),linear-gradient(180deg,rgba(255,255,255,0.09),rgba(255,255,255,0.04))] p-8 shadow-[0_30px_140px_rgba(0,0,0,0.38)] sm:p-10">
            <div className="max-w-4xl">
              <div className="inline-flex rounded-full border border-emerald-500/30 bg-emerald-500/12 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-emerald-300">
                Frontend-only foundation
              </div>
              <h1 className="mt-5 text-4xl font-semibold tracking-tight text-white sm:text-5xl">
                Tool Registry
              </h1>
              <p className="mt-5 max-w-3xl text-base leading-8 text-neutral-300 sm:text-lg">
                bucks.ai prefers a trusted operating stack, but it can request
                approval for external tools when the business case is strong.
                This registry makes the default stack, setup state, human gates,
                and autonomy limits visible before any real integrations are
                wired up.
              </p>
            </div>

            <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <SummaryCard
                label="Preferred tools"
                value={`${preferredTools.length}`}
                detail="The default stack bucks.ai reaches for first when it can execute inside guardrails."
              />
              <SummaryCard
                label="Extended tools"
                value={`${extendedTools.length}`}
                detail="Approved or review-required alternatives for more specialized go-to-market or ops needs."
              />
              <SummaryCard
                label="High-risk tools"
                value={`${highRiskTools}`}
                detail="Tools that touch spend, identity, customer data, or live acquisition channels."
              />
              <SummaryCard
                label="Human-only / blocked"
                value={`${blockedOrHumanOnly}`}
                detail="Destinations that remain off-limits or founder-controlled until future approval flows exist."
              />
            </div>
          </section>

          <section className="space-y-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-400/80">
                  Trusted default stack
                </p>
                <h2 className="mt-2 text-3xl font-semibold tracking-tight text-white">
                  Preferred Tools
                </h2>
                <p className="mt-3 max-w-3xl text-sm leading-7 text-neutral-400 sm:text-base">
                  The first 15 tools are marked as preferred because they map
                  cleanly to bucks.ai&apos;s default code, deployment, growth,
                  and monitoring workflows.
                </p>
              </div>
              <ToolStatusBadge label="15 preferred" variant="preferred" />
            </div>

            <div className="grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
              {preferredTools.map((tool) => (
                <ToolCard key={tool.id} tool={tool} />
              ))}
            </div>
          </section>

          <section className="space-y-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cyan-300/80">
                  Expanded operating surface
                </p>
                <h2 className="mt-2 text-3xl font-semibold tracking-tight text-white">
                  Extended Tools
                </h2>
                <p className="mt-3 max-w-3xl text-sm leading-7 text-neutral-400 sm:text-base">
                  These tools expand the operating surface when the founder
                  needs more options, while still making blocked, approval-only,
                  and human-only paths explicit.
                </p>
              </div>
              <ToolStatusBadge label="15 extended" variant="approved" />
            </div>

            <div className="grid gap-6 lg:grid-cols-2 xl:grid-cols-3">
              {extendedTools.map((tool) => (
                <ToolCard key={tool.id} tool={tool} />
              ))}
            </div>
          </section>

          <section className="grid gap-6 xl:grid-cols-[1.35fr_0.65fr]">
            <AutonomyConstitutionPanel constitution={autonomyConstitution} />

            <div className="space-y-6">
              <RuleList
                title="Human-only actions"
                badge="Founder approval"
                items={autonomyConstitution.humanOnlyActions}
              />
              <RuleList
                title="Escalation triggers"
                badge="Always escalate"
                items={autonomyConstitution.mustEscalateActions}
              />
              <section className="rounded-[1.75rem] border border-white/10 bg-white/[0.04] p-6 shadow-[0_20px_70px_rgba(0,0,0,0.24)] backdrop-blur-sm">
                <h2 className="text-2xl font-semibold text-white">
                  Outreach limits
                </h2>
                <div className="mt-5 grid gap-4 sm:grid-cols-2">
                  <div className="rounded-2xl border border-white/8 bg-black/25 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.24em] text-neutral-500">
                      Cold emails / day
                    </p>
                    <p className="mt-2 text-3xl font-semibold text-white">
                      {autonomyConstitution.maxColdEmailsPerDay}
                    </p>
                  </div>
                  <div className="rounded-2xl border border-white/8 bg-black/25 p-4">
                    <p className="text-xs font-semibold uppercase tracking-[0.24em] text-neutral-500">
                      DMs / day
                    </p>
                    <p className="mt-2 text-3xl font-semibold text-white">
                      {autonomyConstitution.maxDMsPerDay}
                    </p>
                  </div>
                </div>
                <div className="mt-5 space-y-3">
                  <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-black/25 px-4 py-3">
                    <span className="text-sm text-neutral-300">Staging deploys</span>
                    <ToolStatusBadge
                      label={autonomyConstitution.canDeployStaging ? "Allowed" : "Blocked"}
                      variant={autonomyConstitution.canDeployStaging ? "success" : "danger"}
                    />
                  </div>
                  <div className="flex items-center justify-between rounded-2xl border border-white/8 bg-black/25 px-4 py-3">
                    <span className="text-sm text-neutral-300">
                      Production deploys when tests pass
                    </span>
                    <ToolStatusBadge
                      label={
                        autonomyConstitution.canDeployProductionIfTestsPass
                          ? "Allowed"
                          : "Blocked"
                      }
                      variant={
                        autonomyConstitution.canDeployProductionIfTestsPass
                          ? "success"
                          : "danger"
                      }
                    />
                  </div>
                </div>
              </section>
            </div>
          </section>
        </div>
      </main>
      <Footer />
    </>
  );
}
