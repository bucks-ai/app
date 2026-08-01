import Link from "next/link";
import {
  DeploymentStatusBadge,
  deploymentStatusLabel,
} from "@/components/deployment/DeploymentStatusBadge";
import { GlassCard } from "@/components/ui/GlassCard";
import { NextActionBlock } from "@/components/ui/NextActionBlock";
import { ProgressRing } from "@/components/ui/ProgressRing";
import { StatusPill } from "@/components/ui/StatusPill";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { DeploymentStatus } from "@/types/deployment-ui";
import { resolvePrimaryNextAction } from "@/components/workspace/next-action";

type BusinessCardProps = {
  business: DashboardBusiness;
  label?: string;
};

function statTone(value: number, intent: "warning" | "danger") {
  if (value === 0) return "border-success/20 bg-success/10 text-success";
  return intent === "warning"
    ? "border-warning/30 bg-warning/10 text-warning"
    : "border-error/30 bg-error/10 text-error";
}

function progressForBusiness(business: DashboardBusiness) {
  if (business.vercelProject?.deploymentUrl) return 76;
  if (business.vercelProject) return 64;
  if (business.githubRepo) return 48;
  if (business.blueprintSummary) return 25;
  return 10;
}

export function BusinessCard({ business, label }: BusinessCardProps) {
  const href = `/dashboard/businesses/${business.id}`;
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
  const progress = progressForBusiness(business);

  return (
    <GlassCard interactive variant="solid" className="group h-full p-5 sm:p-6">
      <article className="grid h-full gap-5">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill label={business.status} variant={business.statusVariant} />
            <DeploymentStatusBadge status={deployStatus} />
            <span className="rounded-md border border-border bg-background/70 px-2.5 py-1 font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              {label ?? business.businessType}
            </span>
          </div>

          <div className="mt-5 grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
            <div className="min-w-0">
              <h3 className="text-2xl font-semibold tracking-tight text-foreground">
                {business.name}
              </h3>
              <p className="mt-2 line-clamp-2 text-sm leading-6 text-foreground-secondary">
                {business.oneLineIdea ?? business.overview}
              </p>
            </div>
            <ProgressRing value={progress} label={`${business.name} progress`} />
          </div>

          <div className="mt-5 h-1.5 overflow-hidden rounded-full bg-border">
            <div
              className="rail-fill h-full rounded-full bg-accent"
              style={{ width: `${progress}%` }}
            />
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full border border-accent/20 bg-accent/10 px-3 py-1.5 font-mono uppercase tracking-[0.14em] text-accent-bright">
              {progress}% complete
            </span>
            <span
              className={`rounded-full border px-3 py-1.5 font-mono uppercase tracking-[0.14em] ${statTone(
                approvalCount,
                "warning"
              )}`}
            >
              {approvalCount} approvals
            </span>
            <span
              className={`rounded-full border px-3 py-1.5 font-mono uppercase tracking-[0.14em] ${statTone(
                blockerCount,
                "danger"
              )}`}
            >
              {blockerCount} blockers
            </span>
          </div>

          <p className="mt-4 min-w-0 truncate border-t border-border/70 pt-4 text-sm text-foreground-secondary">
            <span className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              Last:
            </span>{" "}
            {lastActivity}
          </p>

          <div className="mt-4 grid gap-3 rounded-xl border border-border bg-background/58 p-4 text-sm leading-6 text-foreground-secondary">
            <p className="line-clamp-3">{business.blueprintSummary}</p>
            <Link
              href={href}
              className="inline-flex min-h-11 w-fit items-center rounded-lg border border-border bg-elevated px-4 py-2 text-sm font-medium text-foreground transition-colors hover:border-accent/40 hover:text-accent-bright"
            >
              View full workspace
            </Link>
          </div>
        </div>

        <NextActionBlock
          href={href}
          title={nextAction.label}
          description={nextAction.description}
          meta={
            deployStatus === "not_deployed"
              ? "Vercel project ready"
              : deploymentStatusLabel(deployStatus)
          }
        />
      </article>
    </GlassCard>
  );
}
