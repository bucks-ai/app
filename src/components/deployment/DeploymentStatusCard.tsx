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
          <h2 className="mt-4 text-2xl font-semibold tracking-tight text-foreground">
            {hasProject
              ? view.projectName ?? "Vercel project"
              : "No Vercel project yet"}
          </h2>
          <p className="mt-2 max-w-2xl text-sm leading-6 text-secondary">
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
              className="inline-flex w-full items-center justify-center rounded-md border border-error/35 bg-error/10 px-4 py-2.5 text-sm font-semibold text-error transition-colors hover:border-error/60 hover:text-error sm:w-auto"
            >
              Open Vercel
            </a>
          ) : view.status === "no_project" ? (
            <a
              href="#deployment-execution"
              className="inline-flex w-full items-center justify-center rounded-md border border-border bg-background px-4 py-2.5 text-sm font-semibold text-secondary transition-colors hover:border-accent/50 hover:text-foreground sm:w-auto"
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
        <div className="min-w-0 rounded border border-border bg-background px-3 py-2.5">
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Status
          </p>
          <p className="mt-1 truncate text-sm font-semibold text-secondary">
            {deploymentStatusLabel(view.status)}
          </p>
        </div>
        <div className="min-w-0 rounded border border-border bg-background px-3 py-2.5">
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Live URL
          </p>
          {view.liveUrl ? (
            <a
              href={view.liveUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="mt-1 block truncate text-sm font-semibold text-success hover:text-success"
            >
              {view.liveUrl}
            </a>
          ) : (
            <p className="mt-1 truncate text-sm font-semibold text-muted">
              {hasProject ? "Deployment pending" : "Not available"}
            </p>
          )}
        </div>
        <div className="min-w-0 rounded border border-border bg-background px-3 py-2.5">
          <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
            Latest checked
          </p>
          <p className="mt-1 truncate text-sm font-semibold text-secondary">
            {formatTimestamp(view.latestCheckedAt)}
          </p>
        </div>
      </div>

      {view.dashboardUrl ? (
        <a
          href={view.dashboardUrl}
          target="_blank"
          rel="noopener noreferrer"
          className="mt-3 inline-flex max-w-full truncate font-mono text-[11px] uppercase tracking-widest text-secondary transition-colors hover:text-accent"
        >
          Vercel dashboard
        </a>
      ) : null}

      {message ? (
        <div
          className={`mt-4 rounded border px-3 py-2 text-sm leading-6 ${
            loadState === "error"
              ? "border-error/30 bg-error/10 text-error"
              : "border-warning/30 bg-warning/10 text-warning"
          }`}
        >
          {message}
        </div>
      ) : null}

      {view.warnings.length > 0 ? (
        <div className="mt-4 rounded border border-warning/25 bg-warning/8 px-3 py-2">
          <p className="font-mono text-[10px] uppercase tracking-widest text-warning">
            Warnings
          </p>
          <ul className="mt-2 space-y-1 text-sm leading-6 text-warning">
            {view.warnings.map((warning) => (
              <li key={warning}>{warning}</li>
            ))}
          </ul>
        </div>
      ) : null}
    </OperatorPanel>
  );
}
