"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { PermissionToolCard } from "@/components/tools/PermissionToolCard";
import { DataTile } from "@/components/ui/DataTile";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";
import {
  fetchToolPermissions,
  seedToolPermissions,
  updateToolPermission,
} from "@/lib/tool-permission-client";
import { toolRegistry } from "@/lib/tool-registry";
import type { RiskLevel, ToolRegistryItem } from "@/types/tools";
import type {
  ToolPermissionAction,
  ToolPermissionStatus,
  ToolPermissionView,
} from "@/types/tool-permission-ui";

type PermissionControlRoomProps = {
  businessId?: string | null;
  businessName?: string;
  signedOutCta?: boolean;
};

type LoadState =
  | "demo"
  | "loading"
  | "ready"
  | "empty"
  | "api_unavailable"
  | "error";

const setupToolIds = [
  "github",
  "vercel",
  "supabase",
  "stripe",
  "posthog",
  "gmail-google-workspace",
  "resend",
  "cloudflare",
  "openai",
];

const API_UNAVAILABLE =
  "Permission API not available yet. Merge backend branch first.";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value)
    ? value.filter((item): item is string => typeof item === "string")
    : [];
}

function riskToLower(risk: RiskLevel | string | undefined): ToolPermissionView["riskLevel"] {
  const normalized = risk?.toLowerCase();
  if (
    normalized === "low" ||
    normalized === "medium" ||
    normalized === "high" ||
    normalized === "critical"
  ) {
    return normalized;
  }

  return "medium";
}

function normalizeStatus(value: unknown): ToolPermissionStatus {
  switch (value) {
    case "approval_requested":
    case "approved":
    case "human_required":
    case "approved_by_founder":
    case "connected_demo":
    case "rejected":
    case "blocked":
    case "not_connected":
      return value;
    case "connected":
      return "approved";
    case "error":
      return "blocked";
    default:
      return "not_connected";
  }
}

function defaultStatusForTool(tool: ToolRegistryItem, demo: boolean): ToolPermissionStatus {
  if (demo && (tool.id === "github" || tool.id === "posthog")) {
    return "connected_demo";
  }

  if (
    tool.id === "stripe" ||
    tool.id === "gmail-google-workspace" ||
    tool.id === "cloudflare"
  ) {
    return "human_required";
  }

  if (
    tool.requiresPaymentSetup ||
    tool.requiresIdentityVerification ||
    tool.requiresTermsAcceptance
  ) {
    return "approval_requested";
  }

  return "not_connected";
}

function toPermissionView(
  tool: ToolRegistryItem,
  businessId: string | null,
  demo = false
): ToolPermissionView {
  const status = defaultStatusForTool(tool, demo);

  return {
    id: `${businessId ?? "demo"}-${tool.id}`,
    businessId,
    toolId: tool.id,
    toolName: tool.name,
    category: tool.category,
    purpose: tool.purpose,
    typicalUse: tool.typicalUse,
    riskLevel: riskToLower(tool.riskLevel),
    status,
    setupStatus: status,
    permissions: tool.defaultPermissions,
    humanOnlyReasons: tool.humanOnlyReasons,
    requiresTermsAcceptance: tool.requiresTermsAcceptance,
    requiresIdentityVerification: tool.requiresIdentityVerification,
    requiresPaymentSetup: tool.requiresPaymentSetup,
    canAiSetupFully: tool.canAiSetupFully,
  };
}

function expectedQueue(businessId: string | null, demo = false) {
  return setupToolIds
    .map((toolId) => toolRegistry.find((tool) => tool.id === toolId))
    .filter((tool): tool is ToolRegistryItem => Boolean(tool))
    .map((tool) => toPermissionView(tool, businessId, demo));
}

function normalizePermission(value: unknown): ToolPermissionView | null {
  if (!isRecord(value)) return null;

  const toolId = asString(value.toolId) ?? asString(value.tool_id);
  const registryTool = toolId
    ? toolRegistry.find((tool) => tool.id === toolId)
    : undefined;
  const toolName =
    asString(value.toolName) ??
    asString(value.tool_name) ??
    registryTool?.name ??
    null;

  if (!toolId || !toolName) return null;

  const status = normalizeStatus(value.status);
  const setupStatus = normalizeStatus(value.setupStatus ?? value.setup_status);

  return {
    id: asString(value.id) ?? `${asString(value.businessId) ?? "unknown"}-${toolId}`,
    businessId:
      asString(value.businessId) ?? asString(value.business_id) ?? null,
    toolId,
    toolName,
    category: registryTool?.category,
    purpose:
      asString(value.purpose) ??
      registryTool?.purpose ??
      "Tool permission requested for this business.",
    typicalUse: asString(value.typicalUse) ?? registryTool?.typicalUse,
    riskLevel: riskToLower(asString(value.riskLevel) ?? asString(value.risk_level) ?? registryTool?.riskLevel),
    status,
    setupStatus,
    permissions:
      asStringArray(value.permissions).length > 0
        ? asStringArray(value.permissions)
        : registryTool?.defaultPermissions ?? [],
    humanOnlyReasons:
      asStringArray(value.humanOnlyReasons).length > 0
        ? asStringArray(value.humanOnlyReasons)
        : registryTool?.humanOnlyReasons ?? [],
    requiresTermsAcceptance: registryTool?.requiresTermsAcceptance,
    requiresIdentityVerification: registryTool?.requiresIdentityVerification,
    requiresPaymentSetup: registryTool?.requiresPaymentSetup,
    canAiSetupFully: registryTool?.canAiSetupFully,
    updatedAt: asString(value.updatedAt) ?? asString(value.updated_at) ?? undefined,
  };
}

function extractPermissions(payload: unknown): ToolPermissionView[] {
  const source = isRecord(payload) && isRecord(payload.data) ? payload.data : payload;
  const rawPermissions = isRecord(source) ? source.permissions : null;

  if (!Array.isArray(rawPermissions)) return [];

  return rawPermissions
    .map(normalizePermission)
    .filter((permission): permission is ToolPermissionView => Boolean(permission));
}

function extractPermission(payload: unknown): ToolPermissionView | null {
  const source = isRecord(payload) && isRecord(payload.data) ? payload.data : payload;
  const rawPermission = isRecord(source)
    ? source.permission ?? source.toolPermission ?? source
    : null;

  return normalizePermission(rawPermission);
}

function countByStatus(permissions: ToolPermissionView[], status: ToolPermissionStatus) {
  return permissions.filter((permission) => permission.status === status).length;
}

export function PermissionControlRoom({
  businessId,
  businessName,
  signedOutCta = false,
}: PermissionControlRoomProps) {
  const [permissions, setPermissions] = useState<ToolPermissionView[]>(() =>
    expectedQueue(null, true)
  );
  const [loadState, setLoadState] = useState<LoadState>("demo");
  const [message, setMessage] = useState<string | null>(null);
  const [seedBusy, setSeedBusy] = useState(false);
  const [busy, setBusy] = useState<{
    id: string;
    action: ToolPermissionAction;
  } | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      if (!businessId) {
        setPermissions(expectedQueue(null, true));
        setLoadState("demo");
        setMessage(null);
        return;
      }

      setLoadState("loading");
      setMessage(null);

      const result = await fetchToolPermissions(businessId);
      if (cancelled) return;

      if (!result.ok) {
        setMessage(result.error);
        setLoadState(result.code === "api_unavailable" ? "api_unavailable" : "error");
        setPermissions(
          result.code === "api_unavailable" ? expectedQueue(businessId) : []
        );
        return;
      }

      const nextPermissions = extractPermissions(result.data);
      setPermissions(nextPermissions);
      setLoadState(nextPermissions.length > 0 ? "ready" : "empty");
    }

    load();

    return () => {
      cancelled = true;
    };
  }, [businessId]);

  const readOnly = !businessId || loadState === "api_unavailable" || loadState === "demo";
  const totals = useMemo(
    () => ({
      total: permissions.length,
      approved:
        countByStatus(permissions, "approved") +
        countByStatus(permissions, "approved_by_founder"),
      humanRequired: countByStatus(permissions, "human_required"),
      blocked:
        countByStatus(permissions, "blocked") + countByStatus(permissions, "rejected"),
      demoConnected: countByStatus(permissions, "connected_demo"),
    }),
    [permissions]
  );

  async function handleSeed() {
    if (!businessId) return;

    setSeedBusy(true);
    setMessage(null);

    const result = await seedToolPermissions(businessId);
    setSeedBusy(false);

    if (!result.ok) {
      setMessage(result.error);
      setLoadState(result.code === "api_unavailable" ? "api_unavailable" : "error");
      if (result.code === "api_unavailable") {
        setPermissions(expectedQueue(businessId));
      }
      return;
    }

    const nextPermissions = extractPermissions(result.data);
    setPermissions(nextPermissions);
    setLoadState(nextPermissions.length > 0 ? "ready" : "empty");
  }

  async function handleAction(id: string, action: ToolPermissionAction) {
    setBusy({ id, action });
    setMessage(null);

    const result = await updateToolPermission(id, action);
    setBusy(null);

    if (!result.ok) {
      setMessage(result.error);
      if (result.code === "api_unavailable") setLoadState("api_unavailable");
      return;
    }

    const updatedPermission = extractPermission(result.data);
    if (!updatedPermission) {
      setMessage("Tool permission API returned an invalid update response.");
      return;
    }

    setPermissions((current) =>
      current.map((permission) =>
        permission.id === updatedPermission.id ? updatedPermission : permission
      )
    );
    setLoadState("ready");
  }

  return (
    <section className="space-y-6">
      <OperatorPanel className="overflow-hidden p-6 shadow-[0_30px_120px_rgba(0,0,0,0.34)] sm:p-8">
        <div className="flex flex-col gap-6 lg:flex-row lg:items-start lg:justify-between">
          <div className="max-w-3xl">
            <div className="flex flex-wrap items-center gap-3">
              <SectionLabel>Permission Setup</SectionLabel>
              <StatusPill
                label={
                  loadState === "demo"
                    ? "Demo layer"
                    : loadState === "api_unavailable"
                      ? "Backend pending"
                      : "Setup queue"
                }
                variant={
                  loadState === "api_unavailable"
                    ? "warning"
                    : loadState === "error"
                      ? "danger"
                      : "accent"
                }
              />
            </div>
            <h2 className="mt-4 text-3xl font-semibold tracking-tight text-foreground">
              Tool Setup Queue
            </h2>
            <p className="mt-3 text-sm leading-7 text-secondary sm:text-base">
              {businessId
                ? `Approve the external tools bucks.ai needs for ${
                    businessName ?? "this business"
                  }, while keeping legal, identity, payment, and email-sending steps founder-controlled.`
                : "Preview the permission layer before a saved business is selected. This is demo-only and no external account is connected."}
            </p>
          </div>

          <div className="flex flex-col gap-3 sm:flex-row lg:flex-col xl:flex-row">
            {loadState === "empty" && businessId ? (
              <button
                type="button"
                disabled={seedBusy}
                onClick={handleSeed}
                className="rounded-md bg-accent px-4 py-3 text-sm font-semibold text-accent-contrast transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
              >
                {seedBusy ? "Creating..." : "Create setup queue"}
              </button>
            ) : null}
            {signedOutCta ? (
              <Link
                href="/login"
                className="rounded-md border border-border bg-background px-4 py-3 text-center text-sm font-semibold text-secondary transition-colors hover:border-accent/60 hover:text-foreground"
              >
                Sign in -&gt;
              </Link>
            ) : null}
          </div>
        </div>

        {message ? (
          <div
            className={`mt-6 rounded-md border px-4 py-3 text-sm leading-6 ${
              message === API_UNAVAILABLE
                ? "border-warning/30 bg-warning/10 text-warning"
                : "border-error/30 bg-error/10 text-error"
            }`}
          >
            {message}
          </div>
        ) : null}

        {loadState === "loading" ? (
          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            {["Loading", "Approvals", "Human gates", "Blocks"].map((label) => (
              <DataTile
                key={label}
                label={label}
                value="..."
                detail="Checking the setup queue."
              />
            ))}
          </div>
        ) : (
          <div className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <DataTile
              label="Tools in queue"
              value={`${totals.total}`}
              detail="Expected tools needed for a real operating setup."
              tone="accent"
            />
            <DataTile
              label="Approved"
              value={`${totals.approved}`}
              detail="Founder-approved or ready for guarded use."
              tone="success"
            />
            <DataTile
              label="Human-required"
              value={`${totals.humanRequired}`}
              detail="Legal, payment, identity, or sending steps."
              tone="warning"
            />
            <DataTile
              label="Blocked / rejected"
              value={`${totals.blocked}`}
              detail={
                totals.demoConnected > 0
                  ? `${totals.demoConnected} demo-connected; no real accounts connected.`
                  : "Tools bucks.ai cannot use yet."
              }
              tone={totals.blocked > 0 ? "danger" : "neutral"}
            />
          </div>
        )}
      </OperatorPanel>

      {loadState === "empty" ? (
        <OperatorPanel className="p-6 text-center">
          <StatusPill label="Empty" variant="neutral" />
          <h3 className="mt-4 text-2xl font-semibold text-foreground">
            No setup queue exists yet.
          </h3>
          <p className="mx-auto mt-3 max-w-2xl text-sm leading-7 text-secondary">
            Create a setup queue to seed GitHub, Vercel, Supabase, Stripe,
            PostHog, Gmail/Workspace, Resend, Cloudflare, and OpenAI permission
            records for this business.
          </p>
          {businessId ? (
            <button
              type="button"
              disabled={seedBusy}
              onClick={handleSeed}
              className="mt-5 rounded-md bg-accent px-4 py-3 text-sm font-semibold text-accent-contrast transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
            >
              {seedBusy ? "Creating..." : "Create setup queue"}
            </button>
          ) : null}
        </OperatorPanel>
      ) : null}

      {loadState !== "loading" && loadState !== "empty" ? (
        <div className="grid gap-5 xl:grid-cols-2">
          {permissions.map((permission) => (
            <PermissionToolCard
              key={permission.id}
              permission={permission}
              readOnly={readOnly}
              busyAction={busy?.id === permission.id ? busy.action : null}
              onAction={handleAction}
            />
          ))}
        </div>
      ) : null}
    </section>
  );
}
