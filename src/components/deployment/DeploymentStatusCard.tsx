"use client";

import { useEffect, useMemo, useState } from "react";
import { DeploymentRefreshButton } from "@/components/deployment/DeploymentRefreshButton";
import {
  DeploymentStatusBadge,
  deploymentStatusLabel,
} from "@/components/deployment/DeploymentStatusBadge";
import { LiveAppLink } from "@/components/deployment/LiveAppLink";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import {
  deploymentViewFromProject,
  fetchDeploymentStatus,
  refreshDeploymentStatus,
} from "@/lib/deployment-client";
import type { DeploymentStatusView } from "@/types/deployment-ui";
import type { VercelProjectResult } from "@/types/vercel-ui";

type DeploymentStatusCardProps = {
  businessId: string;
  initialProject?: VercelProjectResult | null;
};

type LoadState = "loading" | "ready" | "backend_missing" | "error";

const BACKEND_MISSING =
  "Deployment status backend is not available yet. Merge backend branch first.";

function formatTimestamp(value?: string | null) {
  if (!value) return "Not checked yet";

  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;

  return new Intl.DateTimeFormat("en", {
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  }).format(date);
}

function statusCopy(view: DeploymentStatusView) {
  if (view.status === "manual_action_required") {
    return view.manualAction ?? "Connect Git or push to main in Vercel/GitHub";
  }

  if (view.status === "no_project") return "No Vercel project yet.";
  if (view.status === "not_deployed") return "Vercel project exists, but no live deployment URL is recorded yet.";
  if (view.status === "queued") return "Deployment is queued in Vercel.";
  if (view.status === "building") return "Deployment is building. Refresh for the latest state.";
  if (view.status === "failed") return "Latest deployment failed. Open Vercel for logs and recovery.";
  if (view.status === "live" || view.status === "ready") return "Production deployment is live.";

  return "Deployment status is unknown.";
}

export function DeploymentStatusCard({
  businessId,
  initialProject = null,
}: DeploymentStatusCardProps) {
  const fallbackView = useMemo(
    () => deploymentViewFromProject(businessId, initialProject),
    [businessId, initialProject]
  );
  const [view, setView] = useState<DeploymentStatusView>(fallbackView);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [message, setMessage] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  useEffect(() => {
    let ignore = false;

    async function load() {
      const result = await fetchDeploymentStatus(businessId);

      if (ignore) return;

      if (!result.ok) {
        if (result.code === "api_unavailable") {
          setView(fallbackView);
          setLoadState("backend_missing");
          setMessage(BACKEND_MISSING);
          return;
        }

        setLoadState("error");
        setMessage(result.error);
        return;
      }

      setView(result.data);
      setLoadState("ready");
      setMessage(result.warning ?? null);
    }

    void load();

    return () => {
      ignore = true;
    };
  }, [businessId, fallbackView]);

  async function handleRefresh() {
    setRefreshing(true);
    setMessage(null);

    const result = await refreshDeploymentStatus(businessId);

    if (!result.ok) {
      if (result.code === "api_unavailable") {
        setLoadState("backend_missing");
        setMessage(BACKEND_MISSING);
      } else {
        setLoadState("error");
        setMessage(result.error);
      }
      setRefreshing(false);
      return;
    }

    setView(result.data);
    setLoadState("ready");
    setMessage(result.warning ?? null);
    setRefreshing(false);
  }

  const isLive = view.status === "live" || view.status === "ready";
  const isFailed = view.status === "failed";
  const hasProject = Boolean(view.project);
  const showOpenVercel = Boolean(view.dashboardUrl) && (isFailed || view.status === "manual_action_required");

  return (
    <OperatorPanel
      id="deployment-status"
      className="scroll-mt-28 p-5 shadow-[0_24px_90px_rgba(0,0,0,0.28)] sm:p-6"
      elevated
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-3">
            <SectionLabel>Deployment status</SectionLabel>
            <DeploymentStatusBadge status={view.status} />
            {loadState === "backend_missing" ? (
              <DeploymentStatusBadge status="manual_action_required" />
            ) : null}
          </div>
          <h2 className="mt-4 text-2xl font-semibold tracking-tight text-[#F0F0F0]">
            {hasProject
              ? view.projectName ?? "Vercel project"
              : "No Vercel project yet"}
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-[#888]">
            {loadState === "loading"
              ? "Checking the latest deployment state."
              : statusCopy(view)}
          </p>
        </div>

        <div className="flex w-full flex-col gap-2 sm:w-auto sm:flex-row lg:justify-end">
          {isLive ? (
            <LiveAppLink href={view.liveUrl} className="w-full sm:w-auto" />
          ) : showOpenVercel ? (
            <a
              href={view.dashboardUrl ?? undefined}
              target="_blank"
              rel="noopener noreferrer"
              className="inline-flex w-full items-center justify-center rounded-md border border-[#EF4444]/35 bg-[#EF4444]/10 px-4 py-2.5 text-sm font-semibold text-[#FCA5A5] transition-colors hover:border-[#EF4444]/60 hover:text-[#FECACA] sm:w-auto"
            >
              Open Vercel
            </a>
          ) : view.status === "no_project" ? (
            <a
              href="#deployment-execution"
              className="inline-flex w-full items-center justify-center rounded-md border border-[#1C1C1C] bg-[#080808] px-4 py-2.5 text-sm font-semibold text-[#D4D4D4] transition-colors hover:border-[#4F46E5]/50 hover:text-[#F0F0F0] sm:w-auto"
            >
              Create project
            </a>
          ) : null}
          <DeploymentRefreshButton
            loading={refreshing}
            disabled={loadState === "loading"}
            onRefresh={handleRefresh}
          />
        </div>
      </div>

      <div className="mt-5 grid gap-2 md:grid-cols-3">
        <div className="min-w-0 rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2.5">
          <p className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
            Status
          </p>
          <p className="mt-1 truncate text-sm font-semibold text-[#D4D4D4]">
            {deploymentStatusLabel(view.status)}
          </p>
        </div>
        <div className="min-w-0 rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2.5">
          <p className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
            Live URL
          </p>
          {view.liveUrl ? (
            <a
              href={view.liveUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 block truncate text-sm font-semibold text-[#86EFAC] hover:text-[#DCFCE7]"
            >
              {view.liveUrl}
            </a>
          ) : (
            <p className="mt-1 truncate text-sm font-semibold text-[#555]">
              {hasProject ? "Deployment pending" : "Not available"}
            </p>
          )}
        </div>
        <div className="min-w-0 rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2.5">
          <p className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
            Latest checked
          </p>
          <p className="mt-1 truncate text-sm font-semibold text-[#D4D4D4]">
            {formatTimestamp(view.latestCheckedAt)}
          </p>
        </div>
      </div>

      {view.dashboardUrl ? (
        <a
          href={view.dashboardUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex max-w-full truncate font-mono text-[11px] uppercase tracking-widest text-[#888] transition-colors hover:text-[#A5B4FC]"
        >
          Vercel dashboard
        </a>
      ) : null}

      {message ? (
        <div
          className={`mt-4 rounded border px-3 py-2 text-sm leading-6 ${
            loadState === "error"
              ? "border-[#EF4444]/30 bg-[#EF4444]/10 text-[#FECACA]"
              : "border-[#F59E0B]/30 bg-[#F59E0B]/10 text-[#FDE68A]"
          }`}
        >
          {message}
        </div>
      ) : null}

      {view.warnings.length > 0 ? (
        <div className="mt-4 rounded border border-[#F59E0B]/25 bg-[#F59E0B]/8 px-3 py-2">
          <p className="font-mono text-[10px] uppercase tracking-widest text-[#FCD34D]">
            Warnings
          </p>
          <ul className="mt-2 space-y-1 text-sm leading-6 text-[#FDE68A]">
            {view.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </OperatorPanel>
  );
}
