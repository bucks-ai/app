import type { Metadata } from "next";
import Link from "next/link";
import { ActivityLog } from "@/components/dashboard/ActivityLog";
import { BusinessCard } from "@/components/dashboard/BusinessCard";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { HumanActionQueue } from "@/components/dashboard/HumanActionQueue";
import {
  demoActivity,
  demoBusinesses,
  demoHumanActions,
  type ActivityItem,
  type DashboardBusiness,
  type HumanAction,
} from "@/components/dashboard/mock-data";
import {
  getAgentActivityLogs,
  getCurrentUser,
  getHumanRequiredActions,
  getUserBusinesses,
} from "@/lib/projects";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import type {
  AgentActivityLogRecord,
  BusinessRecord,
  HumanRequiredActionRecord,
} from "@/types/database";
import { GlassCard } from "@/components/ui/GlassCard";
import { KpiStat } from "@/components/ui/KpiStat";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Mission Control | bucks.ai",
  description:
    "Saved startup builds, their current stage, open approvals, and the next action to take.",
};

const primaryCta =
  "inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-accent-contrast shadow-[var(--shadow-soft)] transition-colors hover:bg-accent-hover";
const secondaryCta =
  "inline-flex min-h-11 items-center justify-center gap-1.5 rounded-lg border border-border bg-surface px-4 py-2.5 text-sm font-medium text-secondary transition-colors hover:border-accent/40 hover:text-foreground";

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    year: "numeric",
  }).format(new Date(value));
}

function formatDateTime(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function formatStatus(status: string) {
  return status
    .split("_")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function statusVariant(status: string): DashboardBusiness["statusVariant"] {
  if (status === "active" || status === "completed") return "success";
  if (status === "paused") return "warning";
  return "accent";
}

function toDashboardBusiness(business: BusinessRecord): DashboardBusiness {
  return {
    id: business.id,
    name: business.idea_name,
    sourceLabel: "Saved business",
    businessType: business.business_type ?? "Unclassified",
    status: formatStatus(business.status),
    statusVariant: statusVariant(business.status),
    goal: business.primary_goal ?? "Goal not set",
    created: formatDate(business.created_at),
    overview:
      business.one_line_idea ??
      business.idea_description ??
      "Saved business project from the intake flow.",
    blueprintSummary: "Open the business record to review the latest saved blueprint.",
    nextActions: [],
    humanActions: [],
    activity: [],
    permissions: [],
  };
}

function toActivityItem(log: AgentActivityLogRecord): ActivityItem {
  return {
    time: formatDateTime(log.created_at),
    actor: formatStatus(log.activity_type),
    event: log.message,
    tone: log.activity_type === "blueprint_created" ? "accent" : "neutral",
    statusLabel: "log",
  };
}

function toHumanAction(
  action: HumanRequiredActionRecord,
  businessName: string
): HumanAction {
  return {
    title: action.title,
    business: businessName,
    reason:
      action.description ??
      "Founder approval is required before bucks.ai can continue this step.",
    status: formatStatus(action.status),
  };
}

function DashboardKpis({
  projects,
  approvals,
  activeDeploys,
  blockers,
  sample = false,
}: {
  projects: number;
  approvals: number;
  activeDeploys: number;
  blockers: number;
  sample?: boolean;
}) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      <KpiStat
        label={sample ? "Sample projects" : "Total projects"}
        value={projects}
        detail={sample ? "Preview workspace records" : "Saved MVP workspaces"}
        tone="accent"
        sparkline={[1, 2, 2, 3, projects + 1]}
      />
      <KpiStat
        label="Open approvals"
        value={approvals}
        detail="Founder decisions waiting"
        tone={approvals > 0 ? "warning" : "success"}
        sparkline={[0, 1, approvals, approvals + 1, approvals]}
      />
      <KpiStat
        label="Active deploys"
        value={activeDeploys}
        detail="Builds with live deployment state"
        tone={activeDeploys > 0 ? "success" : "neutral"}
        sparkline={[0, 0, 1, activeDeploys, activeDeploys]}
      />
      <KpiStat
        label="Blockers"
        value={blockers}
        detail={blockers > 0 ? "Needs intervention" : "No hard stops"}
        tone={blockers > 0 ? "danger" : "success"}
        sparkline={[0, blockers, blockers, Math.max(0, blockers - 1), blockers]}
      />
    </div>
  );
}

function SidePanel({
  title,
  count,
  tone = "accent",
  children,
}: {
  title: string;
  count?: number;
  tone?: "accent" | "warning";
  children: React.ReactNode;
}) {
  return (
    <GlassCard as="section" className="p-4 sm:p-5">
      <div className="flex items-center justify-between gap-3">
        <SectionLabel tone={tone === "warning" ? "warning" : "accent"}>
          {title}
        </SectionLabel>
        {typeof count === "number" && count > 0 ? (
          <span
            className={`rounded-full px-2 py-0.5 font-mono text-[10px] font-semibold ${
              tone === "warning"
                ? "bg-warning/15 text-warning"
                : "bg-accent/15 text-accent"
            }`}
          >
            {count}
          </span>
        ) : null}
      </div>
      <div className="mt-4">{children}</div>
    </GlassCard>
  );
}

function SetupPanel() {
  return (
    <GlassCard as="section" className="p-6 sm:p-10">
      <StatusPill label="Setup required" variant="warning" />
      <h1 className="mt-5 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
        Mission Control is ready. Connect Supabase for real projects.
      </h1>
      <p className="mt-5 max-w-3xl text-base leading-8 text-secondary">
        Mission Control builds without secrets, but real saved businesses need{" "}
        <code className="rounded bg-background px-1.5 py-0.5 font-mono text-accent">
          NEXT_PUBLIC_SUPABASE_URL
        </code>{" "}
        and{" "}
        <code className="rounded bg-background px-1.5 py-0.5 font-mono text-accent">
          NEXT_PUBLIC_SUPABASE_ANON_KEY
        </code>{" "}
        in <code className="rounded bg-background px-1.5 py-0.5 font-mono">.env.local</code>.
      </p>
    </GlassCard>
  );
}

function SignInPanel() {
  return (
    <GlassCard as="section" className="p-6 sm:p-10">
      <div className="grid gap-8 lg:grid-cols-[minmax(0,1fr)_20rem] lg:items-center">
        <div>
          <StatusPill label="Signed out" variant="neutral" />
          <h1 className="mt-5 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
            Mission Control for every startup workspace.
          </h1>
          <p className="mt-5 max-w-3xl text-base leading-8 text-secondary">
            Sign in to load saved businesses from Supabase. Until then, this page
            shows a clearly labeled sample preview of the operator console.
          </p>
          <div className="mt-6 flex flex-col gap-3 sm:flex-row">
            <Link href="/login" className={primaryCta}>
              Sign in <span aria-hidden>&#8594;</span>
            </Link>
            <Link href="/signup" className={secondaryCta}>
              Create account
            </Link>
          </div>
        </div>
        <div className="rounded-xl border border-border bg-background/70 p-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
            Preview mode
          </p>
          <div className="mt-4 space-y-3">
            {["Research complete", "Deploy running", "Validation queued"].map(
              (item) => (
                <div
                  key={item}
                  className="skeleton-shimmer rounded-lg border border-border bg-surface/70 px-3 py-2 text-sm text-secondary"
                >
                  {item}
                </div>
              )
            )}
          </div>
        </div>
      </div>
    </GlassCard>
  );
}

function DemoPreview() {
  return (
    <section className="space-y-5">
      <DashboardKpis
        projects={demoBusinesses.length}
        approvals={demoHumanActions.length}
        activeDeploys={1}
        blockers={1}
        sample
      />

      <div className="flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <SectionLabel>Sample data</SectionLabel>
          <h2 className="mt-2 text-xl font-semibold tracking-tight text-foreground">
            Clearly labeled dashboard preview
          </h2>
        </div>
        <p className="max-w-md text-sm leading-6 text-secondary">
          Connect Supabase and sign in to see your real projects here.
        </p>
      </div>
      <div className="grid gap-4 xl:grid-cols-2">
        {demoBusinesses.map((business) => (
          <BusinessCard key={business.id} business={business} label="Sample business" />
        ))}
      </div>

      <div className="grid gap-5 lg:grid-cols-2">
        <SidePanel title="Sample approvals" count={demoHumanActions.length} tone="warning">
          <HumanActionQueue actions={demoHumanActions} />
        </SidePanel>
        <SidePanel title="Sample activity">
          <ActivityLog items={demoActivity} />
        </SidePanel>
      </div>
    </section>
  );
}

function EmptyState() {
  return (
    <GlassCard className="p-8 text-center sm:p-12">
      <SectionLabel className="inline-block">Get started</SectionLabel>
      <h3 className="mt-4 text-2xl font-semibold tracking-tight text-foreground">
        Start your first business
      </h3>
      <p className="mx-auto mt-3 max-w-md text-sm leading-7 text-secondary">
        bucks.ai turns an idea into an execution-ready MVP. It researches the
        market, drafts the blueprint, ships a starter build, validates with
        customers, and runs a team of agents to keep the work moving.
      </p>
      <Link href="/intake" className={`${primaryCta} mt-6`}>
        Start with an idea <span aria-hidden>&#8594;</span>
      </Link>
    </GlassCard>
  );
}

export default async function DashboardPage() {
  if (!hasSupabaseEnv()) {
    return (
      <DashboardShell>
        <div className="space-y-8">
          <SetupPanel />
          <DemoPreview />
        </div>
      </DashboardShell>
    );
  }

  const userResult = await getCurrentUser();
  if (userResult.error || !userResult.data) {
    return (
      <DashboardShell>
        <div className="space-y-8">
          <SignInPanel />
          <DemoPreview />
        </div>
      </DashboardShell>
    );
  }

  const businessesResult = await getUserBusinesses();
  if (businessesResult.error || !businessesResult.data) {
    return (
      <DashboardShell>
        <GlassCard as="section" className="p-6 sm:p-10">
          <StatusPill label="Load failed" variant="danger" />
          <h1 className="mt-5 text-3xl font-semibold tracking-tight text-foreground">
            Mission Control could not load businesses.
          </h1>
          <p className="mt-4 text-sm leading-7 text-error">
            {businessesResult.error ?? "No business data was returned."}
          </p>
        </GlassCard>
      </DashboardShell>
    );
  }

  const businesses = businessesResult.data;
  const businessNameById = new Map(
    businesses.map((business) => [business.id, business.idea_name])
  );

  const [actionsByBusiness, logsByBusiness] = await Promise.all([
    Promise.all(businesses.map((business) => getHumanRequiredActions(business.id))),
    Promise.all(businesses.map((business) => getAgentActivityLogs(business.id))),
  ]);

  const humanActions = actionsByBusiness
    .flatMap((result) => result.data ?? [])
    .slice(0, 6)
    .map((action) =>
      toHumanAction(action, businessNameById.get(action.business_id) ?? "Saved business")
    );

  const activityItems = logsByBusiness
    .flatMap((result) => result.data ?? [])
    .sort(
      (a, b) =>
        new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    )
    .slice(0, 6)
    .map(toActivityItem);

  const businessCards = businesses.map((business, index) => {
    const card = toDashboardBusiness(business);
    const businessActions = actionsByBusiness[index]?.data ?? [];
    const businessLogs = logsByBusiness[index]?.data ?? [];

    return {
      ...card,
      humanActionItems: businessActions.map((action) =>
        toHumanAction(action, business.idea_name)
      ),
      humanActions: businessActions.map((action) => action.title),
      activity: businessLogs.slice(0, 5).map(toActivityItem),
    };
  });
  const activeDeploys = businessCards.filter((business) => business.vercelProject).length;
  const blockerCount = humanActions.filter((action) => {
    const value = `${action.status} ${action.reason}`.toLowerCase();
    return value.includes("block") || value.includes("human-only");
  }).length;

  return (
    <DashboardShell>
      <div className="space-y-7">
        <header className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-2xl">
            <div className="flex flex-wrap items-center gap-2.5">
              <SectionLabel>Mission Control</SectionLabel>
              <StatusPill label="Live data" variant="success" />
            </div>
            <h1 className="mt-3 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
              Your businesses
            </h1>
            <p className="mt-2.5 max-w-xl text-sm leading-7 text-secondary">
              Every saved build, its current stage, and the next action waiting
              on you.
            </p>
          </div>
          <div className="flex flex-col gap-2.5 sm:flex-row">
            <Link href="/intake" className={primaryCta}>
              New business <span aria-hidden>&#8594;</span>
            </Link>
            <Link href="/tools" className={secondaryCta}>
              Tool registry
            </Link>
          </div>
        </header>

        <DashboardKpis
          projects={businesses.length}
          approvals={humanActions.length}
          activeDeploys={activeDeploys}
          blockers={blockerCount}
        />

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1.6fr)_minmax(0,1fr)]">
          <section className="min-w-0">
            <div className="mb-3 flex items-center justify-between gap-3">
              <h2 className="font-mono text-xs font-medium uppercase tracking-[0.18em] text-secondary">
                Workspaces
              </h2>
              {businessCards.length > 0 ? (
                <span className="font-mono text-xs text-muted">
                  {businessCards.length} saved
                </span>
              ) : null}
            </div>
            {businessCards.length > 0 ? (
              <div className="grid gap-4 xl:grid-cols-2">
                {businessCards.map((business) => (
                  <BusinessCard key={business.id} business={business} />
                ))}
              </div>
            ) : (
              <EmptyState />
            )}
          </section>

          <aside className="grid content-start gap-5">
            <SidePanel title="Needs you" count={humanActions.length} tone="warning">
              {humanActions.length > 0 ? (
                <HumanActionQueue actions={humanActions} />
              ) : (
                <p className="rounded-lg border border-border bg-background p-4 text-sm leading-6 text-muted">
                  No pending approvals. bucks.ai will surface anything that needs
                  your sign-off here.
                </p>
              )}
            </SidePanel>

            <SidePanel title="Recent activity">
              {activityItems.length > 0 ? (
                <ActivityLog items={activityItems} />
              ) : (
                <p className="rounded-lg border border-border bg-background p-4 text-sm leading-6 text-muted">
                  Activity will appear here once a blueprint is saved.
                </p>
              )}
            </SidePanel>
          </aside>
        </div>
      </div>
    </DashboardShell>
  );
}
