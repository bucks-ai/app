import Link from "next/link";
import { StatusPill } from "@/components/ui/StatusPill";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { BusinessExecutionStatus } from "@/types/execution-ui";

type WorkspaceHeaderProps = {
  business: DashboardBusiness;
  executionStatus?: BusinessExecutionStatus | null;
  onBlueprintOpen?: () => void;
};

function healthVariant(health: string): "success" | "warning" | "danger" | "accent" {
  if (health === "complete" || health === "on_track") return "success";
  if (health === "needs_attention") return "warning";
  if (health === "blocked") return "danger";
  return "accent";
}

function healthLabel(health: string): string {
  if (health === "on_track") return "On track";
  if (health === "needs_attention") return "Needs attention";
  if (health === "blocked") return "Blocked";
  if (health === "complete") return "Complete";
  return health;
}

function phaseLabel(phase: string): string {
  return phase
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

export function WorkspaceHeader({
  business,
  executionStatus,
  onBlueprintOpen,
}: WorkspaceHeaderProps) {
  const phase = executionStatus?.currentPhase ?? "blueprint";
  const health = executionStatus?.health ?? "on_track";
  const progress = executionStatus?.progressPercent ?? 0;
  const blockerCount = executionStatus?.blockers?.length ?? 0;
  const pendingApprovalCount =
    business.humanActionItems?.length ?? business.humanActions.length;
  const latestRun = executionStatus?.timeline?.[0]?.status ?? executionStatus?.timeline?.[0]?.category;

  return (
    <div className="border-b border-[#1C1C1C] bg-[#0A0A0A] px-4 py-3 sm:px-6">
      <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
        {/* Left: back + identity */}
        <div className="min-w-0 flex-1">
          <Link
            href="/dashboard"
            className="mb-1.5 inline-flex items-center gap-1.5 font-mono text-[11px] uppercase tracking-[0.18em] text-[#444] transition-colors hover:text-[#888]"
          >
            <span aria-hidden="true">←</span>
            Mission Control
          </Link>
          <div className="flex flex-wrap items-center gap-2.5">
            <h1 className="truncate text-lg font-semibold tracking-tight text-[#F0F0F0]">
              {business.name}
            </h1>
            <StatusPill
              label={healthLabel(health)}
              variant={healthVariant(health)}
            />
            <StatusPill label={phaseLabel(phase)} variant="neutral" />
            {latestRun ? (
              <StatusPill label={`Run: ${phaseLabel(latestRun)}`} variant="accent" />
            ) : null}
          </div>
          {business.oneLineIdea ? (
            <p className="mt-0.5 truncate text-[13px] text-[#666]">
              {business.oneLineIdea}
            </p>
          ) : null}
        </div>

        {/* Right: stats + quick assets */}
        <div className="hidden shrink-0 items-center gap-4 lg:flex">
          {/* Progress */}
          <div className="text-right">
            <p className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
              Progress
            </p>
            <p className="mt-0.5 text-sm font-semibold text-[#F0F0F0]">
              {progress}%
            </p>
          </div>

          {/* Progress bar */}
          <div className="h-16 w-px bg-[#1C1C1C]" />

          {/* Counters */}
          <div className="flex items-center gap-3">
            {pendingApprovalCount > 0 ? (
              <div className="rounded border border-[#F59E0B]/30 bg-[#F59E0B]/10 px-2 py-1 text-center">
                <p className="font-mono text-[10px] uppercase tracking-widest text-[#F59E0B]/70">
                  Approvals
                </p>
                <p className="text-sm font-semibold text-[#FCD34D]">
                  {pendingApprovalCount}
                </p>
              </div>
            ) : null}
            {blockerCount > 0 ? (
              <div className="rounded border border-[#EF4444]/30 bg-[#EF4444]/10 px-2 py-1 text-center">
                <p className="font-mono text-[10px] uppercase tracking-widest text-[#EF4444]/70">
                  Blockers
                </p>
                <p className="text-sm font-semibold text-[#FCA5A5]">
                  {blockerCount}
                </p>
              </div>
            ) : null}
          </div>

          <div className="h-16 w-px bg-[#1C1C1C]" />

          {/* Quick asset links */}
          <div className="flex items-center gap-2">
            {business.githubRepo ? (
              <a
                href={business.githubRepo.repoUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded border border-[#1C1C1C] bg-[#141414] px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-widest text-[#888] transition-colors hover:border-[#4F46E5]/40 hover:text-[#A5B4FC]"
              >
                GitHub
              </a>
            ) : null}
            {business.vercelProject?.dashboardUrl ? (
              <a
                href={business.vercelProject.dashboardUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded border border-[#1C1C1C] bg-[#141414] px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-widest text-[#888] transition-colors hover:border-[#4F46E5]/40 hover:text-[#A5B4FC]"
              >
                Vercel
              </a>
            ) : null}
            {business.vercelProject?.deploymentUrl ? (
              <a
                href={business.vercelProject.deploymentUrl}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded border border-[#22C55E]/30 bg-[#22C55E]/10 px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-widest text-[#86EFAC] transition-colors hover:border-[#22C55E]/50"
              >
                Live
              </a>
            ) : null}
            {onBlueprintOpen ? (
              <button
                type="button"
                onClick={onBlueprintOpen}
                className="rounded border border-[#1C1C1C] bg-[#141414] px-2.5 py-1.5 font-mono text-[11px] uppercase tracking-widest text-[#888] transition-colors hover:border-[#4F46E5]/40 hover:text-[#A5B4FC]"
              >
                Blueprint
              </button>
            ) : null}
          </div>
        </div>
      </div>

      {/* Progress bar strip */}
      <div className="mt-2.5 h-0.5 w-full overflow-hidden rounded-full bg-[#1C1C1C]">
        <div
          className="h-full rounded-full bg-[#4F46E5] transition-all duration-700"
          style={{ width: `${progress}%` }}
        />
      </div>
    </div>
  );
}
