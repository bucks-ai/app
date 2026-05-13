import type { Metadata } from "next";
import Link from "next/link";
import type { ReactNode } from "react";
import { BusinessDetail } from "@/components/dashboard/BusinessDetail";
import { DashboardShell } from "@/components/dashboard/DashboardShell";
import type {
  ActivityItem,
  DashboardBusiness,
  HumanAction,
  ToolPermission,
} from "@/components/dashboard/mock-data";
import {
  getAgentActivityLogs,
  getBusinessById,
  getCurrentUser,
  getHumanRequiredActions,
  getLatestBlueprintForBusiness,
} from "@/lib/projects";
import { hasSupabaseEnv } from "@/lib/supabase/env";
import type {
  AgentActivityLogRecord,
  BusinessRecord,
  HumanRequiredActionRecord,
} from "@/types/database";
import type { BusinessBlueprint, NextAutonomousAction } from "@/types/startup";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";

export const dynamic = "force-dynamic";

export async function generateMetadata({
  params,
}: PageProps<"/dashboard/businesses/[id]">): Promise<Metadata> {
  const { id } = await params;

  return {
    title: `Business ${id} | bucks.ai`,
    description: "Saved business project detail in Mission Control.",
  };
}

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

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null
    ? (value as Record<string, unknown>)
    : null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function statusVariant(status: string): DashboardBusiness["statusVariant"] {
  if (status === "active" || status === "completed") return "success";
  if (status === "paused") return "warning";
  return "accent";
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

function toNextAction(action: unknown): string | null {
  if (typeof action === "string") return action;

  const record = asRecord(action);
  if (!record) return null;

  const title = asString(record.title) ?? "Next action";
  const detail = asString(record.detail) ?? asString(record.description);
  const phase = asString(record.phase);

  return [phase, title, detail].filter(Boolean).join(" - ");
}

function toToolPermission(tool: unknown): ToolPermission | null {
  if (typeof tool === "string") {
    return {
      tool,
      access: "Suggested",
      note: "Suggested by the saved launch blueprint. Live connection is deferred.",
      tone: "neutral",
    };
  }

  const record = asRecord(tool);
  if (!record) return null;

  const name = asString(record.name) ?? asString(record.tool);
  if (!name) return null;

  return {
    tool: name,
    access: "Suggested",
    note:
      asString(record.purpose) ??
      "Suggested by the saved launch blueprint. Live connection is deferred.",
    tone: "neutral",
  };
}

function toDashboardBusiness(input: {
  business: BusinessRecord;
  blueprint: Record<string, unknown> | null;
  actions: HumanRequiredActionRecord[];
  logs: AgentActivityLogRecord[];
}): DashboardBusiness {
  const typedBlueprint = input.blueprint as Partial<BusinessBlueprint> | null;
  const nextActions =
    Array.isArray(typedBlueprint?.nextAutonomousActions)
      ? typedBlueprint.nextAutonomousActions
          .map((action: NextAutonomousAction | unknown) => toNextAction(action))
          .filter((action): action is string => !!action)
      : [];

  const permissions =
    Array.isArray(typedBlueprint?.requiredTools)
      ? typedBlueprint.requiredTools
          .map(toToolPermission)
          .filter((permission): permission is ToolPermission => !!permission)
      : [];

  return {
    id: input.business.id,
    name: input.business.idea_name,
    sourceLabel: "Saved build record",
    businessType: input.business.business_type ?? "Unclassified",
    status: formatStatus(input.business.status),
    statusVariant: statusVariant(input.business.status),
    goal: input.business.primary_goal ?? "Goal not set",
    created: formatDate(input.business.created_at),
    overview:
      input.business.one_line_idea ??
      input.business.idea_description ??
      asString(typedBlueprint?.businessSummary) ??
      "Saved business project from the intake flow.",
    blueprintSummary:
      asString(typedBlueprint?.businessSummary) ??
      "No saved blueprint summary was found for this project.",
    nextActions,
    humanActions: input.actions.map((action) => action.title),
    humanActionItems: input.actions.map((action) =>
      toHumanAction(action, input.business.idea_name)
    ),
    activity: input.logs.map(toActivityItem),
    permissions,
  };
}

function StatePanel({
  label,
  title,
  description,
  tone = "neutral",
  cta,
}: {
  label: string;
  title: string;
  description: string;
  tone?: "neutral" | "warning" | "danger";
  cta?: ReactNode;
}) {
  return (
    <DashboardShell>
      <div className="mx-auto max-w-3xl">
        <Link
          href="/dashboard"
          className="inline-flex text-sm font-medium text-[#A5B4FC] transition-colors hover:text-[#C7D2FE]"
        >
          &lt;- Back to Mission Control
        </Link>
        <OperatorPanel className="mt-8 p-6 text-center shadow-[0_30px_140px_rgba(0,0,0,0.38)] sm:p-10">
          <div className="flex justify-center">
            <StatusPill label={label} variant={tone} />
          </div>
          <SectionLabel className="mt-6">Business detail</SectionLabel>
          <h1 className="mt-4 text-3xl font-semibold tracking-tight text-[#F0F0F0]">
            {title}
          </h1>
          <p className="mt-4 text-sm leading-7 text-[#888888]">{description}</p>
          {cta ? <div className="mt-6">{cta}</div> : null}
        </OperatorPanel>
      </div>
    </DashboardShell>
  );
}

export default async function BusinessDetailPage({
  params,
}: PageProps<"/dashboard/businesses/[id]">) {
  const { id } = await params;

  if (!hasSupabaseEnv()) {
    return (
      <StatePanel
        label="Setup required"
        title="Connect Supabase to load saved business details."
        description="This page builds without Supabase credentials, but real business records require NEXT_PUBLIC_SUPABASE_URL and NEXT_PUBLIC_SUPABASE_ANON_KEY."
        tone="warning"
      />
    );
  }

  const userResult = await getCurrentUser();
  if (userResult.error || !userResult.data) {
    return (
      <StatePanel
        label="Signed out"
        title="Sign in to view this business."
        description="Saved business details are scoped to the authenticated Supabase user."
        cta={
          <Link
            href="/login"
            className="inline-flex rounded-md bg-[#4F46E5] px-4 py-2.5 text-sm font-semibold text-[#F0F0F0] transition-colors hover:bg-[#6366F1]"
          >
            Sign in -&gt;
          </Link>
        }
      />
    );
  }

  const businessResult = await getBusinessById(id);
  if (businessResult.error || !businessResult.data) {
    return (
      <StatePanel
        label="Not found"
        title="Business not found or not available."
        description="The record may not exist, or it may belong to a different user."
        tone="danger"
      />
    );
  }

  const business = businessResult.data;
  if (business.user_id !== userResult.data.id) {
    return (
      <StatePanel
        label="Unauthorized"
        title="This business belongs to a different user."
        description="Mission Control only shows projects owned by the current authenticated user."
        tone="danger"
      />
    );
  }

  const [blueprintResult, actionsResult, logsResult] = await Promise.all([
    getLatestBlueprintForBusiness(business.id),
    getHumanRequiredActions(business.id),
    getAgentActivityLogs(business.id),
  ]);

  const dashboardBusiness = toDashboardBusiness({
    business,
    blueprint: blueprintResult.data?.blueprint ?? null,
    actions: actionsResult.data ?? [],
    logs: logsResult.data ?? [],
  });

  return (
    <DashboardShell>
      <BusinessDetail business={dashboardBusiness} />
    </DashboardShell>
  );
}
