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
  if (value === 0) return "bg-success/10 text-success";
  return intent === "warning"
    ? "bg-warning/10 text-warning"
    : "bg-error/10 text-error";
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
    <GlassCard interactive variant="solid" className="group h-full p-6 sm:p-8">
      <article className="grid h-full gap-6">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <StatusPill label={business.status} variant={business.statusVariant} />
            <DeploymentStatusBadge status={deployStatus} />
            <span className="rounded-md bg-muted px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              {label ?? business.businessType}
            </span>
          </div>

          <div className="mt-6 grid gap-4 sm:grid-cols-[minmax(0,1fr)_auto] sm:items-start">
            <div className="min-w-0">
              <h3 className="display-serif text-3xl text-foreground">
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

          {/* Three outlined pills became three tinted ones. The outline plus
              fill plus mono caps was three signals doing one job. */}
          <div className="mt-5 flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full bg-accent/10 px-3 py-1.5 font-mono uppercase tracking-[0.14em] text-accent-on-tint">
              {progress}% complete
            </span>
            <span
              className={`rounded-full px-3 py-1.5 font-mono uppercase tracking-[0.14em] ${statTone(
                approvalCount,
                "warning"
              )}`}
            >
              {approvalCount} approvals
            </span>
            <span
              className={`rounded-full px-3 py-1.5 font-mono uppercase tracking-[0.14em] ${statTone(
                blockerCount,
                "danger"
              )}`}
            >
              {blockerCount} blockers
            </span>
          </div>

          <p className="mt-5 min-w-0 truncate border-t border-edge pt-5 text-sm text-foreground-secondary">
            <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
              Last:
            </span>{" "}
            {lastActivity}
          </p>

          {/* Was a bordered box holding a bordered button. The button is gone
              too: this card already ends in a NextActionBlock whose CTA goes
              to the same href, so the card offered two buttons to one place
              and neither read as primary. */}
          <p className="mt-5 line-clamp-3 text-sm leading-6 text-foreground-secondary">
            {business.blueprintSummary}
          </p>
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
