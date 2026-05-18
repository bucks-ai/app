import type { Metadata } from "next";
import Link from "next/link";
import { ActivityLog } from "@/components/dashboard/ActivityLog";
import { BusinessCard } from "@/components/dashboard/BusinessCard";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import { HumanActionQueue } from "@/components/dashboard/HumanActionQueue";
import { ToolPermissionSummary } from "@/components/dashboard/ToolPermissionSummary";
import {
  demoBusinesses,
  demoPermissions,
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
import { DataTile } from "@/components/ui/DataTile";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";

export const dynamic = "force-dynamic";

export const metadata: Metadata = {
  title: "Mission Control | bucks.ai",
  description:
    "Saved startup builds, operator runs, human-required actions, and tool permissions.",
};

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

function SetupPanel() {
  return (
    <OperatorPanel className="p-6 shadow-[0_30px_140px_rgba(0,0,0,0.38)] sm:p-10">
      <StatusPill label="Setup required" variant="warning" />
      <h1 className="mt-5 text-4xl font-semibold tracking-tight text-[#F0F0F0] sm:text-5xl">
        Connect Supabase to see real projects.
      </h1>
      <p className="mt-5 max-w-3xl text-base leading-8 text-[#888888] sm:text-lg">
        Mission Control builds without secrets, but real saved businesses need{" "}
        <code className="rounded bg-[#080808] px-1.5 py-0.5 font-mono text-[#A5B4FC]">
          NEXT_PUBLIC_SUPABASE_URL
        </code>{" "}
        and{" "}
        <code className="rounded bg-[#080808] px-1.5 py-0.5 font-mono text-[#A5B4FC]">
          NEXT_PUBLIC_SUPABASE_ANON_KEY
        </code>{" "}
        in <code className="rounded bg-[#080808] px-1.5 py-0.5 font-mono">.env.local</code>.
      </p>
    </OperatorPanel>
  );
}

function SignInPanel() {
  return (
    <OperatorPanel className="p-6 shadow-[0_30px_140px_rgba(0,0,0,0.38)] sm:p-10">
      <StatusPill label="Signed out" variant="neutral" />
      <h1 className="mt-5 text-4xl font-semibold tracking-tight text-[#F0F0F0] sm:text-5xl">
        Sign in to load your saved businesses.
      </h1>
      <p className="mt-5 max-w-3xl text-base leading-8 text-[#888888] sm:text-lg">
        The dashboard reads from Supabase when a session is present. Until then,
        the preview below is sample data only.
      </p>
      <div className="mt-6 flex flex-col gap-3 sm:flex-row">
        <Link
          href="/login"
          className="rounded-md bg-[#4F46E5] px-4 py-3 text-center text-sm font-semibold text-[#F0F0F0] transition-colors hover:bg-[#6366F1]"
        >
          Sign in -&gt;
        </Link>
        <Link
          href="/signup"
          className="rounded-md border border-[#1C1C1C] bg-[#080808] px-4 py-3 text-center text-sm font-semibold text-[#D4D4D4] transition-colors hover:border-[#4F46E5]/60 hover:text-[#F0F0F0]"
        >
          Create account -&gt;
        </Link>
      </div>
    </OperatorPanel>
  );
}

function DemoPreview() {
  return (
    <OperatorPanel className="p-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <SectionLabel>Saved businesses</SectionLabel>
          <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[#F0F0F0]">
            Sample dashboard preview
          </h2>
        </div>
        <p className="max-w-md text-sm leading-6 text-[#888888]">
          Sample data - connect Supabase and sign in to see real projects.
        </p>
      </div>
      <div className="mt-6 grid gap-4">
        {demoBusinesses.map((business) => (
          <BusinessCard
            key={business.id}
            business={business}
            label="Sample business"
          />
        ))}
      </div>
    </OperatorPanel>
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
        <OperatorPanel className="p-6 shadow-[0_30px_140px_rgba(0,0,0,0.38)] sm:p-10">
          <StatusPill label="Load failed" variant="danger" />
          <h1 className="mt-5 text-4xl font-semibold tracking-tight text-[#F0F0F0]">
            Mission Control could not load businesses.
          </h1>
          <p className="mt-4 text-sm leading-7 text-[#FCA5A5]">
            {businessesResult.error ?? "No business data was returned."}
          </p>
        </OperatorPanel>
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

  return (
    <DashboardShell>
      <div className="space-y-8">
        <OperatorPanel className="overflow-hidden p-6 shadow-[0_30px_140px_rgba(0,0,0,0.38)] sm:p-10">
          <div className="flex flex-col gap-6 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-4xl">
              <div className="flex flex-wrap items-center gap-3">
                <SectionLabel>Mission Control</SectionLabel>
                <StatusPill label="Live Supabase data" variant="success" />
              </div>
              <h1 className="mt-4 text-3xl font-semibold tracking-tight text-[#F0F0F0] sm:text-5xl">
                Command queue for saved startup builds
              </h1>
              <p className="mt-4 max-w-3xl text-sm leading-7 text-[#888888] sm:text-base">
                Each project card now leads with stage, health, open approvals,
                asset readiness, and the next action to take.
              </p>
            </div>
            <div className="flex flex-col gap-3 sm:flex-row lg:flex-col xl:flex-row">
              <Link
                href="/intake"
                className="rounded-md bg-[#4F46E5] px-4 py-3 text-center text-sm font-semibold text-[#F0F0F0] transition-colors hover:bg-[#6366F1]"
              >
                New blueprint -&gt;
              </Link>
              <Link
                href="/tools"
                className="rounded-md border border-[#1C1C1C] bg-[#080808] px-4 py-3 text-center text-sm font-semibold text-[#D4D4D4] transition-colors hover:border-[#4F46E5]/60 hover:text-[#F0F0F0]"
              >
                Tool registry -&gt;
              </Link>
            </div>
          </div>

          <div className="mt-6 grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <DataTile
              label="Saved businesses"
              value={`${businesses.length}`}
              detail="Projects created through the intake save flow."
              tone="accent"
            />
            <DataTile
              label="Human queue"
              value={`${humanActions.length}`}
              detail="Approval-gated actions from saved blueprints."
              tone="warning"
            />
            <DataTile
              label="Recent logs"
              value={`${activityItems.length}`}
              detail="Agent activity records stored in Supabase."
            />
            <DataTile
              label="Data source"
              value="Live"
              detail="Supabase RLS-scoped project data."
              tone="success"
            />
          </div>
        </OperatorPanel>

        <section className="grid gap-5 xl:grid-cols-[1.25fr_0.75fr]">
          <OperatorPanel className="p-6">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
              <div>
                <SectionLabel>Workspace re-entry</SectionLabel>
                <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[#F0F0F0]">
                  Open project workspaces
                </h2>
              </div>
              <p className="max-w-md text-sm leading-6 text-[#888888]">
                Sorted as a practical command queue instead of a gallery.
              </p>
            </div>
            <div className="mt-6 grid gap-4">
              {businessCards.length > 0 ? (
                businessCards.map((business) => (
                  <BusinessCard key={business.id} business={business} />
                ))
              ) : (
                <div className="rounded-lg border border-[#1C1C1C] bg-[#080808] p-6">
                  <StatusPill label="Empty" variant="neutral" />
                  <h3 className="mt-4 text-xl font-semibold text-[#F0F0F0]">
                    No saved businesses yet.
                  </h3>
                  <p className="mt-3 text-sm leading-6 text-[#888888]">
                    Generate a blueprint from intake while signed in to create
                    your first Mission Control project.
                  </p>
                  <Link
                    href="/intake"
                    className="mt-5 inline-flex rounded-md bg-[#4F46E5] px-4 py-2.5 text-sm font-semibold text-[#F0F0F0] transition-colors hover:bg-[#6366F1]"
                  >
                    Start intake -&gt;
                  </Link>
                </div>
              )}
            </div>
          </OperatorPanel>

          <div className="grid gap-6">
            <OperatorPanel className="p-6">
              <SectionLabel>Recent agent activity</SectionLabel>
              <div className="mt-5">
                {activityItems.length > 0 ? (
                  <ActivityLog items={activityItems} />
                ) : (
                  <p className="rounded-md border border-[#1C1C1C] bg-[#080808] p-4 text-sm leading-6 text-[#888888]">
                    Activity logs will appear after a blueprint is saved.
                  </p>
                )}
              </div>
            </OperatorPanel>

            <OperatorPanel className="p-6" elevated>
              <SectionLabel tone="warning">Human-required action queue</SectionLabel>
              <div className="mt-5">
                {humanActions.length > 0 ? (
                  <HumanActionQueue actions={humanActions} />
                ) : (
                  <p className="rounded-md border border-[#F59E0B]/25 bg-[#F59E0B]/10 p-4 text-sm leading-6 text-[#FDE68A]">
                    No pending human-required actions for saved businesses.
                  </p>
                )}
              </div>
            </OperatorPanel>
          </div>
        </section>

        <OperatorPanel className="p-6">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <SectionLabel>Tool permissions summary</SectionLabel>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-[#F0F0F0]">
                Permission layer
              </h2>
            </div>
            <StatusPill label="Integrations deferred" variant="neutral" />
          </div>
          <ToolPermissionSummary
            permissions={demoPermissions.map((permission) =>
              permission.tool === "Supabase"
                ? {
                    ...permission,
                    access: "Connected",
                    note: "Project data is loaded through Supabase with user-scoped RLS.",
                    tone: "success",
                  }
                : permission
            )}
            className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4"
          />
        </OperatorPanel>
      </div>
    </DashboardShell>
  );
}
