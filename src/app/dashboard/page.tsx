import type { Metadata } from "next";
import Link from "next/link";
import { MissionCanvas, type CanvasBusiness } from "@/components/dashboard/MissionCanvas";
import {
  demoActivity,
  demoBusinesses,
  demoHumanActions,
  type ActivityItem,
  type HumanAction,
  type StatusVariant,
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
import { Navbar } from "@/components/shared/Navbar";
import { PageField } from "@/components/ui/PageField";
import { GlassCard } from "@/components/ui/GlassCard";
import { StatusPill } from "@/components/ui/StatusPill";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Mission Canvas | bucks.ai",
  description:
    "Your businesses as a live node canvas: workspaces, approvals, deploys, and activity branching from one hub.",
};

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

function statusVariant(status: string): StatusVariant {
  if (status === "active" || status === "completed") return "success";
  if (status === "paused") return "warning";
  return "accent";
}

function toCanvasBusiness(business: BusinessRecord): CanvasBusiness {
  return {
    id: business.id,
    name: business.idea_name,
    status: formatStatus(business.status),
    statusVariant: statusVariant(business.status),
    goal: business.primary_goal ?? "Goal not set",
    businessType: business.business_type ?? "Unclassified",
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

const demoCanvasBusinesses: CanvasBusiness[] = demoBusinesses.map((b) => ({
  id: b.id,
  name: b.name,
  status: b.status,
  statusVariant: b.statusVariant,
  goal: b.goal,
  businessType: b.businessType,
}));

/* Full-bleed canvas layout: the page itself never scrolls on lg — you pan
   the canvas instead. An optional notice floats over the canvas rather than
   pushing it down. */
function CanvasShell({
  notice,
  children,
}: {
  notice?: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <>
      <Navbar />
      <PageField />
      <main id="main-content" className="relative pt-[4.75rem]">
        {notice ? (
          <div className="relative z-10 mx-auto max-w-2xl px-5 pt-4 lg:absolute lg:left-1/2 lg:top-[5.5rem] lg:w-full lg:-translate-x-1/2 lg:px-0 lg:pt-0">
            {notice}
          </div>
        ) : null}
        {children}
      </main>
    </>
  );
}

function SampleCanvas() {
  return (
    <MissionCanvas
      businesses={demoCanvasBusinesses}
      humanActions={demoHumanActions}
      activity={demoActivity}
      deploys={1}
      blockers={1}
      sample
    />
  );
}

export default async function DashboardPage() {
  if (!hasSupabaseEnv()) {
    return (
      <CanvasShell
        notice={
          <div className="cloud-panel flex flex-wrap items-center justify-center gap-3 px-5 py-3 text-center">
            <StatusPill label="Setup required" variant="warning" />
            <p className="text-sm text-foreground-secondary">
              Sample canvas. Add Supabase env vars in{" "}
              <code className="rounded bg-background px-1.5 py-0.5 font-mono text-accent">
                .env.local
              </code>{" "}
              for real projects.
            </p>
          </div>
        }
      >
        <SampleCanvas />
      </CanvasShell>
    );
  }

  const userResult = await getCurrentUser();
  if (userResult.error || !userResult.data) {
    return (
      <CanvasShell
        notice={
          <div className="cloud-panel flex flex-wrap items-center justify-center gap-3 px-5 py-3 text-center">
            <StatusPill label="Sample preview" variant="neutral" />
            <p className="text-sm text-foreground-secondary">
              Sign in to load your saved businesses.
            </p>
            <Link
              href="/login"
              className="cloud-node inline-flex min-h-11 items-center gap-1.5 px-4 py-2 text-sm font-semibold text-foreground"
            >
              Sign in <span aria-hidden>&#8594;</span>
            </Link>
          </div>
        }
      >
        <SampleCanvas />
      </CanvasShell>
    );
  }

  const businessesResult = await getUserBusinesses();
  if (businessesResult.error || !businessesResult.data) {
    return (
      <CanvasShell>
        <div className="mx-auto max-w-2xl px-5 py-20">
          <GlassCard as="section" variant="elevated" className="p-6 sm:p-10">
            <StatusPill label="Load failed" variant="danger" />
            <h1 className="mt-5 text-3xl font-semibold tracking-tight text-foreground">
              Mission Canvas could not load businesses.
            </h1>
            <p className="mt-4 text-sm leading-7 text-error">
              {businessesResult.error ?? "No business data was returned."}
            </p>
          </GlassCard>
        </div>
      </CanvasShell>
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

  const blockerCount = humanActions.filter((action) => {
    const value = `${action.status} ${action.reason}`.toLowerCase();
    return value.includes("block") || value.includes("human-only");
  }).length;

  return (
    <CanvasShell>
      <MissionCanvas
        businesses={businesses.map(toCanvasBusiness)}
        humanActions={humanActions}
        activity={activityItems}
        deploys={0}
        blockers={blockerCount}
      />
    </CanvasShell>
  );
}
