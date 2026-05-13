import { Footer } from "@/components/shared/Footer";
import { Navbar } from "@/components/shared/Navbar";
import { AutonomyConstitutionPanel } from "@/components/tools/AutonomyConstitutionPanel";
import { ToolCard } from "@/components/tools/ToolCard";
import { ToolStatusBadge } from "@/components/tools/ToolStatusBadge";
import { DataTile } from "@/components/ui/DataTile";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { autonomyConstitution } from "@/lib/autonomy-constitution";
import { extendedTools, preferredTools, toolRegistry } from "@/lib/tool-registry";

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
    <OperatorPanel className="p-6 shadow-[0_20px_70px_rgba(0,0,0,0.24)]">
      <div className="flex items-center justify-between gap-3">
        <h2 className="text-2xl font-semibold text-[#F0F0F0]">{title}</h2>
        <ToolStatusBadge label={badge} variant="warning" />
      </div>
      <ul className="mt-5 space-y-3">
        {items.map((item) => (
          <li
            key={item}
            className="rounded-md border border-[#F59E0B]/20 bg-[#F59E0B]/10 px-4 py-3 text-sm leading-6 text-[#FDE68A]"
          >
            {item}
          </li>
        ))}
      </ul>
    </OperatorPanel>
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
      <main className="relative min-h-screen overflow-hidden bg-[#080808] px-5 pb-20 pt-28 sm:px-6">
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage:
              "linear-gradient(rgba(79,70,229,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(79,70,229,0.025) 1px, transparent 1px)",
            backgroundSize: "64px 64px",
          }}
        />
        <div className="relative mx-auto max-w-7xl space-y-10">
          <OperatorPanel className="overflow-hidden p-6 shadow-[0_30px_140px_rgba(0,0,0,0.38)] sm:p-10">
            <div className="max-w-4xl">
              <div className="flex flex-wrap items-center gap-3">
                <SectionLabel>Permission Layer</SectionLabel>
                <ToolStatusBadge label="Frontend-only foundation" variant="neutral" />
              </div>
              <h1 className="mt-5 text-4xl font-semibold tracking-tight text-[#F0F0F0] sm:text-5xl">
                Every tool, the right permission.
              </h1>
              <p className="mt-5 max-w-3xl text-base leading-8 text-[#888888] sm:text-lg">
                bucks.ai prefers a trusted operating stack, but it can request
                external tools only when needed, and escalates anything
                involving legal, identity, payments, contracts, or live-client
                commitments.
              </p>
              <p className="mt-3 max-w-3xl text-sm leading-7 text-[#666666]">
                Counts below are registry categories for the prototype, not
                traction claims.
              </p>
            </div>

            <div className="mt-8 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <DataTile
                label="Preferred tools"
                value={`${preferredTools.length}`}
                detail="The default stack bucks.ai reaches for first when it can execute inside guardrails."
                tone="accent"
              />
              <DataTile
                label="Extended tools"
                value={`${extendedTools.length}`}
                detail="Approved or review-required alternatives for more specialized go-to-market or ops needs."
              />
              <DataTile
                label="High-risk tools"
                value={`${highRiskTools}`}
                detail="Tools that touch spend, identity, customer data, or live acquisition channels."
                tone="warning"
              />
              <DataTile
                label="Human-only / blocked"
                value={`${blockedOrHumanOnly}`}
                detail="Destinations that remain off-limits or founder-controlled until future approval flows exist."
                tone="danger"
              />
            </div>
          </OperatorPanel>

          <section className="space-y-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <SectionLabel>Trusted default stack</SectionLabel>
                <h2 className="mt-2 text-3xl font-semibold tracking-tight text-[#F0F0F0]">
                  Preferred Tools
                </h2>
                <p className="mt-3 max-w-3xl text-sm leading-7 text-[#888888] sm:text-base">
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
                <SectionLabel>Expanded operating surface</SectionLabel>
                <h2 className="mt-2 text-3xl font-semibold tracking-tight text-[#F0F0F0]">
                  Extended Tools
                </h2>
                <p className="mt-3 max-w-3xl text-sm leading-7 text-[#888888] sm:text-base">
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
              <OperatorPanel className="p-6 shadow-[0_20px_70px_rgba(0,0,0,0.24)]">
                <h2 className="text-2xl font-semibold text-[#F0F0F0]">
                  Outreach limits
                </h2>
                <div className="mt-5 grid gap-4 sm:grid-cols-2">
                  <div className="rounded-lg border border-[#1C1C1C] bg-[#080808] p-4">
                    <SectionLabel tone="muted">Cold emails / day</SectionLabel>
                    <p className="mt-2 text-3xl font-semibold text-[#F0F0F0]">
                      {autonomyConstitution.maxColdEmailsPerDay}
                    </p>
                  </div>
                  <div className="rounded-lg border border-[#1C1C1C] bg-[#080808] p-4">
                    <SectionLabel tone="muted">DMs / day</SectionLabel>
                    <p className="mt-2 text-3xl font-semibold text-[#F0F0F0]">
                      {autonomyConstitution.maxDMsPerDay}
                    </p>
                  </div>
                </div>
                <div className="mt-5 space-y-3">
                  <div className="flex items-center justify-between gap-3 rounded-md border border-[#1C1C1C] bg-[#080808] px-4 py-3">
                    <span className="text-sm text-[#D4D4D4]">Staging deploys</span>
                    <ToolStatusBadge
                      label={autonomyConstitution.canDeployStaging ? "Allowed" : "Blocked"}
                      variant={autonomyConstitution.canDeployStaging ? "success" : "danger"}
                    />
                  </div>
                  <div className="flex items-center justify-between gap-3 rounded-md border border-[#1C1C1C] bg-[#080808] px-4 py-3">
                    <span className="text-sm text-[#D4D4D4]">
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
              </OperatorPanel>
            </div>
          </section>
        </div>
      </main>
      <Footer />
    </>
  );
}
