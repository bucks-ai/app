import Link from "next/link";
import {
  DeploymentStatusBadge,
  deploymentStatusLabel,
} from "@/components/deployment/DeploymentStatusBadge";
import { StatusPill } from "@/components/ui/StatusPill";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { DeploymentStatus } from "@/types/deployment-ui";
import { resolvePrimaryNextAction } from "@/components/workspace/next-action";

type BusinessCardProps = {
  business: DashboardBusiness;
  label?: string;
};

function metricTone(value: number, intent: "warning" | "danger") {
  if (value === 0) return "text-success";
  return intent === "warning" ? "text-warning" : "text-error";
}

export function BusinessCard({ business, label }: BusinessCardProps) {
  const nextAction = resolvePrimaryNextAction(business);
  const blockerCount =
    business.humanActionItems?.filter((action) =>
      action.status.toLowerCase().includes("block")
    ).length ?? 0;
  const approvalCount = business.humanActionItems?.length ?? business.humanActions.length;
  const deployStatus: DeploymentStatus = business.vercelProject?.deploymentUrl
    ? "live"
    : business.vercelProject
      ? "not_deployed"
      : "unknown";
  const lastActivity =
    business.activityLogs?.[0]?.message ?? business.activity?.[0]?.event ?? "No activity yet";
  const progress =
    business.vercelProject?.deploymentUrl
      ? 75
      : business.vercelProject
        ? 65
        : business.githubRepo
          ? 48
          : business.blueprintSummary
            ? 25
            : 10;

  return (
    <Link
      href={`/dashboard/businesses/${business.id}`}
      className="group block rounded-card border border-border bg-surface p-4 shadow-[var(--shadow-soft)] transition-all duration-200 hover:-translate-y-0.5 hover:border-accent/40 hover:shadow-[var(--shadow-card)] sm:p-5"
    >
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_17rem]">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill label={business.status} variant={business.statusVariant} />
            <DeploymentStatusBadge status={deployStatus} />
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
              {label ?? business.businessType}
            </span>
          </div>

          <div className="mt-3 flex items-start justify-between gap-3">
            <div className="min-w-0">
              <h3 className="truncate text-xl font-semibold tracking-tight text-foreground sm:text-2xl">
                {business.name}
              </h3>
              <p className="mt-1 line-clamp-2 text-sm leading-6 text-secondary">
                {business.oneLineIdea ?? business.overview}
              </p>
            </div>
            <span className="hidden shrink-0 items-center gap-1.5 rounded-lg bg-accent px-3.5 py-2 text-sm font-semibold text-accent-contrast transition-colors group-hover:bg-accent-hover sm:inline-flex">
              Open
              <span aria-hidden className="transition-transform group-hover:translate-x-0.5">
                &#8594;
              </span>
            </span>
          </div>

          <div className="mt-4 h-1.5 overflow-hidden rounded-full bg-border">
            <div
              className="h-full rounded-full bg-accent transition-all duration-700"
              style={{ width: `${progress}%` }}
            />
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-x-5 gap-y-1.5 text-xs">
            <span className="text-secondary">
              Progress <span className="font-semibold text-accent">{progress}%</span>
            </span>
            <span className="text-secondary">
              Approvals{" "}
              <span className={`font-semibold ${metricTone(approvalCount, "warning")}`}>
                {approvalCount}
              </span>
            </span>
            <span className="text-secondary">
              Blockers{" "}
              <span className={`font-semibold ${metricTone(blockerCount, "danger")}`}>
                {blockerCount}
              </span>
            </span>
            <span className="min-w-0 truncate text-muted">Last: {lastActivity}</span>
          </div>
        </div>

        <div className="rounded-xl border border-warning/20 bg-warning/8 p-3.5">
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-warning">
            Next action
          </p>
          <p className="mt-2 text-sm font-semibold text-foreground">
            {nextAction.label}
          </p>
          <p className="mt-1 line-clamp-2 text-xs leading-5 text-secondary">
            {nextAction.description}
          </p>
          <p className="mt-3 font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
            {deployStatus === "not_deployed"
              ? "Vercel project ready"
              : deploymentStatusLabel(deployStatus)}
          </p>
        </div>
      </div>
    </Link>
  );
}
