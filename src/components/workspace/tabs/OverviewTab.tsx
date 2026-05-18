import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { BusinessExecutionStatus } from "@/types/execution-ui";

type TabKey =
  | "overview"
  | "actions"
  | "build"
  | "deploy"
  | "tools"
  | "activity"
  | "settings";

type OverviewTabProps = {
  business: DashboardBusiness;
  executionStatus?: BusinessExecutionStatus | null;
  onTabChange: (tab: TabKey) => void;
  onBlueprintOpen?: () => void;
};

export function OverviewTab({
  business,
  executionStatus,
  onTabChange,
  onBlueprintOpen,
}: OverviewTabProps) {
  const milestones = executionStatus?.milestones ?? [];
  const nextActions = executionStatus?.nextActions?.slice(0, 3) ?? [];
  const recentActivity = executionStatus?.timeline?.slice(0, 3) ?? [];
  const assets = executionStatus?.assets ?? [];
  const progress = executionStatus?.progressPercent ?? 0;

  const keyAssets = assets.filter(
    (a) =>
      a.type === "github_repo" ||
      a.type === "vercel_project" ||
      a.type === "deployment_url"
  );

  return (
    <div className="space-y-5">
      {/* Execution summary strip */}
      <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#444]">
            Progress
          </p>
          <p className="mt-1.5 text-xl font-semibold text-[#F0F0F0]">{progress}%</p>
        </div>
        <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#444]">
            Milestones
          </p>
          <p className="mt-1.5 text-xl font-semibold text-[#F0F0F0]">
            {milestones.filter((m) => m.status === "complete").length}
            <span className="ml-1 text-sm text-[#444]">/ {milestones.length}</span>
          </p>
        </div>
        <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#444]">
            Approvals
          </p>
          <p className="mt-1.5 text-xl font-semibold text-[#F0F0F0]">
            {business.humanActions.length}
          </p>
        </div>
        <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-3">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#444]">
            Blockers
          </p>
          <p className="mt-1.5 text-xl font-semibold text-[#F0F0F0]">
            {executionStatus?.blockers?.length ?? 0}
          </p>
        </div>
      </div>

      {/* Milestone stepper */}
      {milestones.length > 0 ? (
        <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
            Milestones
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {milestones.map((milestone) => (
              <div
                key={milestone.id}
                className="flex items-center gap-1.5 rounded border border-[#1C1C1C] bg-[#080808] px-2.5 py-1.5"
              >
                <span
                  className={`h-2 w-2 rounded-full ${
                    milestone.status === "complete"
                      ? "bg-[#22C55E]"
                      : milestone.status === "in_progress"
                        ? "bg-[#4F46E5]"
                        : milestone.status === "blocked"
                          ? "bg-[#EF4444]"
                          : "bg-[#1C1C1C]"
                  }`}
                />
                <span
                  className={`text-xs ${
                    milestone.status === "complete"
                      ? "text-[#86EFAC]"
                      : milestone.status === "in_progress"
                        ? "text-[#A5B4FC]"
                        : milestone.status === "blocked"
                          ? "text-[#FCA5A5]"
                          : "text-[#444]"
                  }`}
                >
                  {milestone.label}
                </span>
              </div>
            ))}
          </div>
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-2">
        {/* Blueprint summary card */}
        {business.blueprintSummary ? (
          <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
            <div className="flex items-center justify-between">
              <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
                Blueprint summary
              </p>
              {onBlueprintOpen ? (
                <button
                  type="button"
                  onClick={onBlueprintOpen}
                  className="font-mono text-[10px] uppercase tracking-widest text-[#444] transition-colors hover:text-[#888]"
                >
                  Full view
                </button>
              ) : null}
            </div>
            <p className="mt-3 text-sm leading-6 text-[#888]">
              {business.blueprintSummary.length > 320
                ? `${business.blueprintSummary.slice(0, 320)}...`
                : business.blueprintSummary}
            </p>
          </div>
        ) : null}

        {/* Next actions */}
        {nextActions.length > 0 ? (
          <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
            <div className="flex items-center justify-between">
              <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
                Next actions
              </p>
              <button
                type="button"
                onClick={() => onTabChange("actions")}
                className="font-mono text-[10px] uppercase tracking-widest text-[#444] transition-colors hover:text-[#888]"
              >
                All
              </button>
            </div>
            <div className="mt-3 space-y-2">
              {nextActions.map((action) => (
                <div
                  key={action.id}
                  className="flex items-center justify-between gap-2 rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2"
                >
                  <p className="min-w-0 truncate text-xs text-[#D4D4D4]">
                    {action.title}
                  </p>
                  <span
                    className={`shrink-0 rounded px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest ${
                      action.actor === "founder"
                        ? "border border-[#F59E0B]/30 bg-[#F59E0B]/10 text-[#FCD34D]"
                        : "border border-[#4F46E5]/30 bg-[#4F46E5]/10 text-[#A5B4FC]"
                    }`}
                  >
                    {action.actor === "founder" ? "You" : "Auto"}
                  </span>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        {/* Asset quick links */}
        {keyAssets.length > 0 ? (
          <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
            <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
              Assets
            </p>
            <div className="mt-3 space-y-2">
              {keyAssets.map((asset) => (
                <div
                  key={asset.id}
                  className="flex items-center justify-between gap-2 rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2"
                >
                  <p className="min-w-0 truncate text-xs text-[#D4D4D4]">
                    {asset.label}
                  </p>
                  {asset.url ? (
                    <a
                      href={asset.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="shrink-0 font-mono text-[10px] uppercase tracking-widest text-[#4F46E5] transition-colors hover:text-[#A5B4FC]"
                    >
                      Open
                    </a>
                  ) : (
                    <span className="shrink-0 font-mono text-[10px] uppercase tracking-widest text-[#333]">
                      Pending
                    </span>
                  )}
                </div>
              ))}
            </div>
          </div>
        ) : null}

        {/* Latest activity (max 3) */}
        {recentActivity.length > 0 ? (
          <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
            <div className="flex items-center justify-between">
              <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
                Latest activity
              </p>
              <button
                type="button"
                onClick={() => onTabChange("activity")}
                className="font-mono text-[10px] uppercase tracking-widest text-[#444] transition-colors hover:text-[#888]"
              >
                All
              </button>
            </div>
            <div className="mt-3 space-y-2">
              {recentActivity.map((event) => (
                <div
                  key={event.id}
                  className="flex items-start gap-2.5 rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2"
                >
                  <div className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#333]" />
                  <div className="min-w-0">
                    <p className="truncate text-xs text-[#D4D4D4]">{event.title}</p>
                    <p className="font-mono text-[10px] text-[#444]">
                      {new Date(event.createdAt).toLocaleDateString("en-US", {
                        month: "short",
                        day: "2-digit",
                        hour: "2-digit",
                        minute: "2-digit",
                      })}
                    </p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        ) : null}
      </div>
    </div>
  );
}
