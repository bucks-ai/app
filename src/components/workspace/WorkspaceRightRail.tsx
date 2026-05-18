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

type WorkspaceRightRailProps = {
  business: DashboardBusiness;
  executionStatus?: BusinessExecutionStatus | null;
  onTabChange: (tab: TabKey) => void;
};

export function WorkspaceRightRail({
  business,
  executionStatus,
  onTabChange,
}: WorkspaceRightRailProps) {
  const nextActions = executionStatus?.nextActions ?? [];
  const blockers = executionStatus?.blockers ?? [];
  const pendingApprovals =
    business.humanActionItems ?? [];
  const recentActivity = executionStatus?.timeline?.slice(0, 3) ?? [];
  const assets = executionStatus?.assets ?? [];

  const keyAssets = assets.filter(
    (a) =>
      a.type === "github_repo" ||
      a.type === "vercel_project" ||
      a.type === "deployment_url"
  );

  return (
    <aside className="space-y-4">
      {/* Next action */}
      {nextActions.length > 0 ? (
        <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
            Next action
          </p>
          <div className="mt-3 space-y-2">
            {nextActions.slice(0, 3).map((action) => (
              <div
                key={action.id}
                className="flex items-start justify-between gap-2 rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2.5"
              >
                <div className="min-w-0">
                  <p className="truncate text-xs font-medium text-[#F0F0F0]">
                    {action.title}
                  </p>
                  <p className="mt-0.5 font-mono text-[10px] uppercase tracking-widest text-[#444]">
                    {action.actor === "founder" ? "Needs you" : "bucks.ai"}
                  </p>
                </div>
                {action.actor === "founder" ? (
                  <span className="shrink-0 rounded border border-[#F59E0B]/30 bg-[#F59E0B]/10 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest text-[#FCD34D]">
                    You
                  </span>
                ) : (
                  <span className="shrink-0 rounded border border-[#4F46E5]/30 bg-[#4F46E5]/10 px-1.5 py-0.5 font-mono text-[10px] uppercase tracking-widest text-[#A5B4FC]">
                    Auto
                  </span>
                )}
              </div>
            ))}
          </div>
        </div>
      ) : null}

      {/* Blockers */}
      {blockers.length > 0 ? (
        <div className="rounded-lg border border-[#EF4444]/20 bg-[#0F0F0F] p-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#FCA5A5]">
            Blockers
          </p>
          <div className="mt-3 space-y-2">
            {blockers.slice(0, 3).map((blocker) => (
              <div
                key={blocker.id}
                className="rounded border border-[#EF4444]/20 bg-[#EF4444]/5 px-3 py-2"
              >
                <p className="text-xs font-medium text-[#F0F0F0]">
                  {blocker.title}
                </p>
                {blocker.description ? (
                  <p className="mt-0.5 text-xs leading-5 text-[#888]">
                    {blocker.description}
                  </p>
                ) : null}
              </div>
            ))}
            {blockers.length > 3 ? (
              <button
                type="button"
                onClick={() => onTabChange("actions")}
                className="w-full text-left font-mono text-[10px] uppercase tracking-widest text-[#444] transition-colors hover:text-[#888]"
              >
                +{blockers.length - 3} more
              </button>
            ) : null}
          </div>
        </div>
      ) : null}

      {/* Pending approvals */}
      {pendingApprovals.length > 0 ? (
        <div className="rounded-lg border border-[#F59E0B]/20 bg-[#0F0F0F] p-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#FCD34D]">
            Pending approvals
          </p>
          <div className="mt-3 space-y-2">
            {pendingApprovals.slice(0, 3).map((action) => (
              <button
                key={`${action.business}-${action.title}`}
                type="button"
                onClick={() => onTabChange("actions")}
                className="w-full rounded border border-[#F59E0B]/20 bg-[#F59E0B]/5 px-3 py-2 text-left transition-colors hover:border-[#F59E0B]/40"
              >
                <p className="text-xs font-medium text-[#F0F0F0]">
                  {action.title}
                </p>
              </button>
            ))}
          </div>
        </div>
      ) : null}

      {/* Key assets */}
      {keyAssets.length > 0 ? (
        <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
            Assets
          </p>
          <div className="mt-3 space-y-1.5">
            {keyAssets.map((asset) => (
              <div key={asset.id} className="flex items-center justify-between gap-2">
                <span className="truncate text-xs text-[#888]">{asset.label}</span>
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

      {/* Recent activity */}
      {recentActivity.length > 0 ? (
        <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
          <div className="flex items-center justify-between">
            <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
              Recent activity
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
              <div key={event.id} className="flex items-start gap-2">
                <div className="mt-1.5 h-1 w-1 shrink-0 rounded-full bg-[#333]" />
                <p className="text-xs leading-5 text-[#666]">{event.title}</p>
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </aside>
  );
}
