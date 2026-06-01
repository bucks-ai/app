import Link from "next/link";
import { Footer } from "@/components/shared/Footer";
import { Navbar } from "@/components/shared/Navbar";
import { AutonomyConstitutionPanel } from "@/components/tools/AutonomyConstitutionPanel";
import { BusinessPermissionSelector } from "@/components/tools/BusinessPermissionSelector";
import { PermissionControlRoom } from "@/components/tools/PermissionControlRoom";
import { ToolCard } from "@/components/tools/ToolCard";
import { ToolStatusBadge } from "@/components/tools/ToolStatusBadge";
import { DataTile } from "@/components/ui/DataTile";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { autonomyConstitution } from "@/lib/autonomy-constitution";
import { extendedTools, preferredTools, toolRegistry } from "@/lib/tool-registry";
import type { BusinessPermissionOption } from "@/types/tool-permission-ui";

type ToolRegistryPageProps = {
  permissionBusinesses?: BusinessPermissionOption[];
  permissionAuthState?: "supabase_missing" | "signed_out" | "signed_in" | "load_failed";
  permissionLoadError?: string | null;
};

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
        <h2 className="text-2xl font-semibold text-foreground">{title}</h2>
        <ToolStatusBadge label={badge} variant="warning" />
      </div>
      <ul className="mt-5 space-y-3">
        {items.map((item) => (
          <li
            key={item}
            className="rounded-md border border-warning/20 bg-warning/10 px-4 py-3 text-sm leading-6 text-warning"
          >
            {item}
          </li>
        ))}
      </ul>
    </OperatorPanel>
  );
}

function PermissionSetupSection({
  businesses,
  authState,
  loadError,
}: {
  businesses: BusinessPermissionOption[];
  authState: NonNullable<ToolRegistryPageProps["permissionAuthState"]>;
  loadError?: string | null;
}) {
  if (authState === "signed_in" && businesses.length > 0) {
    return <BusinessPermissionSelector businesses={businesses} />;
  }

  if (authState === "signed_in") {
    return (
      <OperatorPanel className="p-6 shadow-[0_24px_90px_rgba(0,0,0,0.28)] sm:p-8">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
          <div>
            <SectionLabel>Permission Setup</SectionLabel>
            <h2 className="mt-3 text-3xl font-semibold tracking-tight text-foreground">
              Generate a blueprint to create a setup queue
            </h2>
            <p className="mt-3 max-w-3xl text-sm leading-7 text-secondary">
              Tool permissions attach to saved business projects. Create a
              blueprint first, then bucks.ai can show the approvals needed for
              that specific operating plan.
            </p>
          </div>
          <Link
            href="/intake"
            className="rounded-md bg-accent px-4 py-3 text-center text-sm font-semibold text-accent-contrast transition-colors hover:bg-accent-hover"
          >
            Generate a blueprint to create a setup queue -&gt;
          </Link>
        </div>
      </OperatorPanel>
    );
  }

  return (
    <div className="space-y-5">
      {authState === "load_failed" || authState === "supabase_missing" ? (
        <OperatorPanel className="p-5">
          <ToolStatusBadge
            label={authState === "supabase_missing" ? "Supabase setup required" : "Business load failed"}
            variant="warning"
          />
          <p className="mt-3 text-sm leading-6 text-secondary">
            {loadError ??
              "Saved businesses are not available in this environment, so the permission layer is shown as a demo preview."}
          </p>
        </OperatorPanel>
      ) : null}
      <PermissionControlRoom signedOutCta={authState === "signed_out"} />
    </div>
  );
}

export function ToolRegistryPage({
  permissionBusinesses = [],
  permissionAuthState = "signed_out",
  permissionLoadError = null,
}: ToolRegistryPageProps) {
  const blockedOrHumanOnly = toolRegistry.filter(
    (tool) => tool.status === "Blocked" || tool.status === "Human Only",
  ).length;

  const highRiskTools = toolRegistry.filter(
    (tool) => tool.riskLevel === "High" || tool.riskLevel === "Critical",
  ).length;

  return (
    <>
      <Navbar />
      <main className="relative min-h-screen overflow-hidden bg-background px-5 pb-20 pt-28 sm:px-6">
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
              <h1 className="mt-5 text-4xl font-semibold tracking-tight text-foreground sm:text-5xl">
                Every tool, the right permission.
              </h1>
              <p className="mt-5 max-w-3xl text-base leading-8 text-secondary sm:text-lg">
                bucks.ai prefers a trusted operating stack, but it can request
                external tools only when needed, and escalates anything
                involving legal, identity, payments, contracts, or live-client
                commitments.
              </p>
              <p className="mt-3 max-w-3xl text-sm leading-7 text-muted">
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

          <PermissionSetupSection
            businesses={permissionBusinesses}
            authState={permissionAuthState}
            loadError={permissionLoadError}
          />

          <section className="space-y-5">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <SectionLabel>Trusted default stack</SectionLabel>
                <h2 className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
                  Preferred Tools
                </h2>
                <p className="mt-3 max-w-3xl text-sm leading-7 text-secondary sm:text-base">
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
                <h2 className="mt-2 text-3xl font-semibold tracking-tight text-foreground">
                  Extended Tools
                </h2>
                <p className="mt-3 max-w-3xl text-sm leading-7 text-secondary sm:text-base">
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
                <h2 className="text-2xl font-semibold text-foreground">
                  Outreach limits
                </h2>
                <div className="mt-5 grid gap-4 sm:grid-cols-2">
                  <div className="rounded-lg border border-border bg-background p-4">
                    <SectionLabel tone="muted">Cold emails / day</SectionLabel>
                    <p className="mt-2 text-3xl font-semibold text-foreground">
                      {autonomyConstitution.maxColdEmailsPerDay}
                    </p>
                  </div>
                  <div className="rounded-lg border border-border bg-background p-4">
                    <SectionLabel tone="muted">DMs / day</SectionLabel>
                    <p className="mt-2 text-3xl font-semibold text-foreground">
                      {autonomyConstitution.maxDMsPerDay}
                    </p>
                  </div>
                </div>
                <div className="mt-5 space-y-3">
                  <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-background px-4 py-3">
                    <span className="text-sm text-secondary">Staging deploys</span>
                    <ToolStatusBadge
                      label={autonomyConstitution.canDeployStaging ? "Allowed" : "Blocked"}
                      variant={autonomyConstitution.canDeployStaging ? "success" : "danger"}
                    />
                  </div>
                  <div className="flex items-center justify-between gap-3 rounded-md border border-border bg-background px-4 py-3">
                    <span className="text-sm text-secondary">
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
