import Link from "next/link";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import { resolvePrimaryNextAction } from "@/components/workspace/next-action";

type BusinessCardProps = {
  business: DashboardBusiness;
  label?: string;
};

export function BusinessCard({ business, label }: BusinessCardProps) {
  const nextAction = resolvePrimaryNextAction(business);
  const blockerCount =
    business.humanActionItems?.filter((action) =>
      action.status.toLowerCase().includes("block")
    ).length ?? 0;
  const approvalCount = business.humanActionItems?.length ?? business.humanActions.length;
  const repoStatus = business.githubRepo ? "Repo ready" : "Repo pending";
  const deployStatus = business.vercelProject?.deploymentUrl
    ? "Live"
    : business.vercelProject
      ? "Vercel ready"
      : "Deploy pending";
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
      className="group block rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4 transition-colors hover:border-[#4F46E5]/60 hover:bg-[#141414] sm:p-5"
    >
      <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
        <div className="min-w-0">
          <SectionLabel tone="muted">
            {label ?? business.sourceLabel ?? "Saved business"}
          </SectionLabel>
          <h3 className="mt-2 truncate text-xl font-semibold tracking-tight text-[#F0F0F0]">
            {business.name}
          </h3>
          <p className="mt-1 font-mono text-xs uppercase tracking-[0.18em] text-[#888888]">
            {business.businessType}
          </p>
        </div>
        <div className="flex shrink-0 flex-wrap gap-2 lg:justify-end">
          <StatusPill label={business.status} variant={business.statusVariant} />
          <StatusPill
            label={approvalCount > 0 ? `${approvalCount} approvals` : "No approvals"}
            variant={approvalCount > 0 ? "warning" : "neutral"}
          />
        </div>
      </div>

      <div className="mt-4 rounded border border-[#F59E0B]/25 bg-[#F59E0B]/8 px-3 py-2.5">
        <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
          <div className="min-w-0">
            <p className="font-mono text-[10px] uppercase tracking-widest text-[#FCD34D]">
              Next required action
            </p>
            <p className="mt-1 truncate text-sm font-semibold text-[#F0F0F0]">
              {nextAction.label}
            </p>
          </div>
          <span className="shrink-0 rounded bg-[#F59E0B] px-2.5 py-1 text-xs font-semibold text-[#0A0A0A]">
            Open workspace
          </span>
        </div>
      </div>

      <div className="mt-4 grid gap-2 sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2">
          <p className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
            Progress
          </p>
          <p className="mt-1 text-sm font-semibold text-[#A5B4FC]">{progress}%</p>
        </div>
        <div className="rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2">
          <p className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
            Blockers
          </p>
          <p className={`mt-1 text-sm font-semibold ${blockerCount > 0 ? "text-[#FCA5A5]" : "text-[#86EFAC]"}`}>
            {blockerCount}
          </p>
        </div>
        <div className="rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2">
          <p className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
            Repo
          </p>
          <p className="mt-1 truncate text-sm font-semibold text-[#D4D4D4]">
            {repoStatus}
          </p>
        </div>
        <div className="rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2">
          <p className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
            Deploy
          </p>
          <p className="mt-1 truncate text-sm font-semibold text-[#D4D4D4]">
            {deployStatus}
          </p>
        </div>
      </div>

      <p className="mt-4 truncate text-xs text-[#666]">
        Last activity: {lastActivity}
      </p>
    </Link>
  );
}
