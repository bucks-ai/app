import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { BusinessExecutionStatus } from "@/types/execution-ui";
import type { DeploymentStatus } from "@/types/deployment-ui";
import {
  DeploymentStatusBadge,
  deploymentStatusLabel,
} from "@/components/deployment/DeploymentStatusBadge";
import { CompactActivityCenter } from "@/components/workspace/CompactActivityCenter";
import { ResearchOverviewCard } from "@/components/research/ResearchOverviewCard";
import { ValidationOverviewCard } from "@/components/validation/ValidationOverviewCard";
import { OperatingTeamOverviewCard } from "@/components/agents/OperatingTeamOverviewCard";
import { resolvePrimaryNextAction } from "@/components/workspace/next-action";

type TabKey =
  | "overview"
  | "research"
  | "actions"
  | "build"
  | "deploy"
  | "validation"
  | "team"
  | "tools"
  | "activity"
  | "settings";

type OverviewTabProps = {
  business: DashboardBusiness;
  executionStatus?: BusinessExecutionStatus | null;
  onTabChange: (tab: TabKey) => void;
  onBlueprintOpen?: () => void;
};

function phaseLabel(phase?: string | null) {
  if (!phase) return "Blueprint";

  return phase
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function deploymentStatusFromBusiness(
  business: DashboardBusiness,
  executionStatus?: BusinessExecutionStatus | null
): DeploymentStatus {
  const deploymentMilestone = executionStatus?.milestones.find(
    (milestone) => milestone.id === "deployment"
  );

  if (business.vercelProject?.deploymentUrl) return "live";
  if (deploymentMilestone?.status === "blocked") return "failed";
  if (deploymentMilestone?.status === "in_progress") return "building";
  if (business.vercelProject) return "not_deployed";
  return "no_project";
}

function OverviewMetric({
  label,
  value,
  tone = "neutral",
}: {
  label: string;
  value: string | number;
  tone?: "neutral" | "accent" | "warning" | "danger";
}) {
  const toneClass =
    tone === "accent"
      ? "text-accent"
      : tone === "warning"
        ? "text-warning"
        : tone === "danger"
          ? "text-error"
          : "text-foreground";

  return (
    <div className="elevated-surface rounded-lg px-3 py-2.5">
      <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
        {label}
      </p>
      <p className={`mt-1 truncate text-lg font-semibold ${toneClass}`}>{value}</p>
    </div>
  );
}

function DeploymentOverviewCard({
  business,
  deploymentStatus,
  onOpenDeploy,
}: {
  business: DashboardBusiness;
  deploymentStatus: DeploymentStatus;
  onOpenDeploy: () => void;
}) {
  const projectLabel =
    business.vercelProject?.deploymentUrl ??
    business.vercelProject?.projectName ??
    deploymentStatusLabel(deploymentStatus);

  return (
    <div className="solid-surface rounded-lg p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-accent">
          Deployment
        </p>
        <button
          type="button"
          onClick={onOpenDeploy}
          className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground transition-colors hover:text-accent"
        >
          Open
        </button>
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <DeploymentStatusBadge status={deploymentStatus} />
      </div>
      <p className="mt-3 truncate text-sm font-semibold text-foreground-secondary">
        {projectLabel}
      </p>
      <p className="mt-1 text-sm leading-6 text-muted-foreground">
        Build and deployment controls live in the Deploy section.
      </p>
    </div>
  );
}

export function OverviewTab({
  business,
  executionStatus,
  onTabChange,
  onBlueprintOpen,
}: OverviewTabProps) {
  const milestones = executionStatus?.milestones ?? [];
  const completedMilestones = milestones.filter((m) => m.status === "complete").length;
  const progress = executionStatus?.progressPercent ?? 0;
  const blockers = executionStatus?.blockers?.length ?? 0;
  const approvals = business.humanActionItems?.length ?? business.humanActions.length;
  const primaryAction = resolvePrimaryNextAction(business, executionStatus);
  const deploymentStatus = deploymentStatusFromBusiness(business, executionStatus);
  const currentPhase = phaseLabel(executionStatus?.currentPhase);
  const summary =
    business.blueprintSummary && business.blueprintSummary.length > 260
      ? `${business.blueprintSummary.slice(0, 260)}...`
      : business.blueprintSummary ?? business.overview;

  return (
    <div className="space-y-4">
      <section className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(18rem,0.65fr)]">
        <div className="solid-surface rounded-card p-4 sm:p-5">
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="min-w-0">
              <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-accent">
                Overview
              </p>
              <h2 className="mt-2 text-2xl font-semibold tracking-tight text-foreground">
                {business.name}
              </h2>
              <p className="mt-2 max-w-3xl break-words text-sm leading-6 text-foreground-secondary">
                {business.oneLineIdea ?? business.overview}
              </p>
            </div>
            {onBlueprintOpen ? (
              <button
                type="button"
                onClick={onBlueprintOpen}
                className="shrink-0 rounded-md border border-border bg-background px-3 py-2 font-mono text-[11px] uppercase tracking-widest text-foreground-secondary transition-colors hover:border-accent/45 hover:text-accent"
              >
                Blueprint
              </button>
            ) : null}
          </div>

          <div className="mt-4 grid grid-cols-2 gap-2 xl:grid-cols-4">
            <OverviewMetric label="Progress" value={`${progress}%`} tone="accent" />
            <OverviewMetric
              label="Milestones"
              value={`${completedMilestones}/${milestones.length || 0}`}
            />
            <OverviewMetric
              label="Approvals"
              value={approvals}
              tone={approvals > 0 ? "warning" : "neutral"}
            />
            <OverviewMetric
              label="Blockers"
              value={blockers}
              tone={blockers > 0 ? "danger" : "neutral"}
            />
          </div>

          <div className="mt-4 rounded-lg border border-border bg-background/70 p-3">
            <div className="flex items-center justify-between gap-3">
              <p className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground">
                Current phase
              </p>
              <p className="truncate text-xs font-semibold text-foreground-secondary">
                {currentPhase}
              </p>
            </div>
            <div className="mt-3 h-1.5 overflow-hidden rounded-full bg-border">
              <div
                className="h-full rounded-full bg-accent transition-all duration-700"
                style={{ width: `${progress}%` }}
              />
            </div>
            {milestones.length > 0 ? (
              <div className="mt-3 flex gap-1.5 overflow-x-auto pb-1" style={{ scrollbarWidth: "none" }}>
                {milestones.slice(0, 8).map((milestone) => (
                  <span
                    key={milestone.id}
                    className={`shrink-0 rounded-full border px-2.5 py-1 text-xs ${
                      milestone.status === "complete"
                        ? "border-success/20 bg-success/8 text-success"
                        : milestone.status === "in_progress"
                          ? "border-accent/25 bg-accent/10 text-accent"
                          : milestone.status === "blocked"
                            ? "border-error/25 bg-error/10 text-error"
                            : "border-border bg-surface text-muted-foreground"
                    }`}
                  >
                    {milestone.label}
                  </span>
                ))}
              </div>
            ) : null}
          </div>
        </div>

        <button
          type="button"
          onClick={() => onTabChange(primaryAction.target)}
          className="interactive-surface rounded-card border border-warning/30 bg-[linear-gradient(135deg,var(--warning-soft),rgba(255,255,255,0.02))] p-4 text-left shadow-[var(--shadow-soft)] transition-colors hover:border-warning/55 sm:p-5"
        >
          <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-warning">
            Primary next action
          </p>
          <h3 className="mt-3 text-xl font-semibold tracking-tight text-foreground">
            {primaryAction.label}
          </h3>
          <p className="mt-2 text-sm leading-6 text-warning">
            {primaryAction.description}
          </p>
          <span className="mt-4 inline-flex min-h-11 items-center rounded-md bg-warning px-3 py-2 text-sm font-semibold text-background">
            Continue
          </span>
        </button>
      </section>

      <section className="grid gap-4 xl:grid-cols-4">
        <ResearchOverviewCard
          businessId={business.id}
          onOpenResearch={() => onTabChange("research")}
        />
        <ValidationOverviewCard
          businessId={business.id}
          onOpenValidation={() => onTabChange("validation")}
        />
        <DeploymentOverviewCard
          business={business}
          deploymentStatus={deploymentStatus}
          onOpenDeploy={() => onTabChange("deploy")}
        />
        <OperatingTeamOverviewCard
          businessId={business.id}
          onOpenTeam={() => onTabChange("team")}
        />
      </section>

      <section className="grid gap-4 lg:grid-cols-[minmax(0,1.4fr)_minmax(0,1fr)]">
        <div className="solid-surface rounded-card p-4 sm:p-5">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-accent">
              Business summary
            </p>
            {onBlueprintOpen ? (
              <button
                type="button"
                onClick={onBlueprintOpen}
                className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground transition-colors hover:text-accent"
              >
                Full blueprint
              </button>
            ) : null}
          </div>
          <p className="mt-3 break-words text-sm leading-7 text-foreground-secondary">{summary}</p>
        </div>

        <div className="solid-surface rounded-card p-4 sm:p-5">
          <div className="flex items-center justify-between gap-3">
            <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-accent">
              Latest activity
            </p>
            <button
              type="button"
              onClick={() => onTabChange("activity")}
              className="font-mono text-[11px] uppercase tracking-widest text-muted-foreground transition-colors hover:text-accent"
            >
              All
            </button>
          </div>
          <div className="mt-3">
            <CompactActivityCenter
              business={business}
              executionStatus={executionStatus}
              maxRows={4}
              compact
            />
          </div>
        </div>
      </section>
    </div>
  );
}
