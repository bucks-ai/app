import Link from "next/link";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { BusinessExecutionStatus } from "@/types/execution-ui";

type WorkspaceHeaderProps = {
  business: DashboardBusiness;
  executionStatus?: BusinessExecutionStatus | null;
  onBlueprintOpen?: () => void;
};

function phaseLabel(phase: string): string {
  return phase
    .split("_")
    .map((w) => w.charAt(0).toUpperCase() + w.slice(1))
    .join(" ");
}

const assetLink =
  "hidden min-h-11 items-center rounded-lg border border-border bg-elevated px-3 py-2 font-mono text-[11px] uppercase tracking-[0.16em] text-foreground-secondary transition-colors hover:border-accent/40 hover:text-accent md:inline-flex";

export function WorkspaceHeader({
  business,
  executionStatus,
  onBlueprintOpen,
}: WorkspaceHeaderProps) {
  const phase = executionStatus?.currentPhase ?? "blueprint";
  const progress = executionStatus?.progressPercent ?? 0;

  return (
    <div className="px-4 py-3 sm:px-6">
      <div className="flex items-center justify-between gap-3">
        {/* Left: identity */}
        <div className="flex min-w-0 items-center gap-2.5">
          <Link
            href="/dashboard"
            aria-label="Back to Mission Control"
            className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg border border-border bg-elevated text-foreground-secondary transition-colors hover:border-accent/40 hover:text-foreground"
          >
            <span aria-hidden="true">&#8592;</span>
          </Link>
          <div className="min-w-0">
            <h1 className="truncate text-sm font-semibold tracking-tight text-foreground sm:text-base">
              {business.name}
            </h1>
            <p className="mt-0.5 truncate font-mono text-[10px] uppercase tracking-[0.18em] text-muted-foreground">
              {phaseLabel(phase)} &middot; {progress}%
            </p>
          </div>
        </div>

        {/* Right: asset shortcuts + blueprint */}
        <div className="flex shrink-0 items-center gap-1.5">
          {business.githubRepo ? (
            <a
              href={business.githubRepo.repoUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={assetLink}
            >
              GitHub
            </a>
          ) : null}
          {business.vercelProject?.dashboardUrl ? (
            <a
              href={business.vercelProject.dashboardUrl}
              target="_blank"
              rel="noopener noreferrer"
              className={assetLink}
            >
              Vercel
            </a>
          ) : null}
          {business.vercelProject?.deploymentUrl ? (
            <a
              href={business.vercelProject.deploymentUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="hidden min-h-11 items-center rounded-lg border border-success/30 bg-success/10 px-3 py-2 font-mono text-[11px] uppercase tracking-[0.16em] text-success transition-colors hover:border-success/50 sm:inline-flex"
            >
              Live
            </a>
          ) : null}
          {onBlueprintOpen ? (
            <button
              type="button"
              onClick={onBlueprintOpen}
              className="inline-flex min-h-11 items-center rounded-lg border border-border bg-elevated px-3 py-2 font-mono text-[11px] uppercase tracking-[0.16em] text-foreground-secondary transition-colors hover:border-accent/40 hover:text-accent"
            >
              Blueprint
            </button>
          ) : null}
        </div>
      </div>
    </div>
  );
}
