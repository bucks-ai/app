import type { Metadata } from "next";
import Link from "next/link";
import { BrainCanvas } from "@/components/dashboard/brain/BrainCanvas";
import type { BrainBusiness, BrainTone } from "@/components/dashboard/brain/brain-model";
import {
  demoBusinesses,
  type StatusVariant,
} from "@/components/dashboard/mock-data";
import {
  getCurrentUser,
  getHumanRequiredActions,
  getUserBusinesses,
} from "@/lib/projects";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import type { BusinessRecord } from "@/types/database";
import { Navbar } from "@/components/shared/Navbar";
import { PageField } from "@/components/ui/PageField";
import { GlassCard } from "@/components/ui/GlassCard";
import { StatusPill } from "@/components/ui/StatusPill";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Brain | bucks.ai",
  description:
    "Your businesses as a zoomable neural map: pick a business, zoom into research, validation, build, deploy, and the decisions waiting on you.",
};

function formatStatus(status: string) {
  return status
    .split("_")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

/* An action the founder has already dealt with is not load on the map. */
const RESOLVED_ACTION_STATUSES = new Set([
  "approved",
  "rejected",
  "dismissed",
  "complete",
  "completed",
  "resolved",
  "done",
  "closed",
]);

const TONE_BY_VARIANT: Record<StatusVariant, BrainTone> = {
  accent: "accent",
  success: "accent",
  warning: "warning",
  danger: "danger",
  neutral: "neutral",
};

function toBrainBusiness(
  business: BusinessRecord,
  approvals: number,
  blockers: number
): BrainBusiness {
  return {
    id: business.id,
    name: business.idea_name,
    detail: business.business_type ?? formatStatus(business.status),
    tone: blockers > 0 ? "danger" : approvals > 0 ? "warning" : "accent",
    approvals,
    blockers,
    live: approvals > 0 || blockers > 0,
  };
}

const demoBrainBusinesses: BrainBusiness[] = demoBusinesses.map((business) => ({
  id: business.id,
  name: business.name,
  detail: business.businessType,
  tone: TONE_BY_VARIANT[business.statusVariant],
  approvals: business.humanActions.length,
  blockers: 0,
  live: false,
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
  return <BrainCanvas businesses={demoBrainBusinesses} sample />;
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

  // Counts are per business, not global: each node in the brain carries its own
  // load, so the map shows where the work is rather than one aggregate number.
  const actionsByBusiness = await Promise.all(
    businesses.map((business) => getHumanRequiredActions(business.id))
  );

  const brainBusinesses = businesses.map((business, index) => {
    const actions = (actionsByBusiness[index]?.data ?? []).filter(
      (action) => !RESOLVED_ACTION_STATUSES.has(action.status.trim().toLowerCase())
    );
    const blockers = actions.filter((action) =>
      ["high", "critical"].includes(action.risk_level.toLowerCase())
    ).length;

    return toBrainBusiness(business, actions.length, blockers);
  });

  return (
    <CanvasShell>
      <BrainCanvas businesses={brainBusinesses} />
    </CanvasShell>
  );
}
