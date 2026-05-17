import { DataTile } from "@/components/ui/DataTile";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { ExecutionStatusPill } from "@/components/execution/ExecutionStatusPill";
import type { BusinessExecutionStatus, ExecutionPhase } from "@/types/execution-ui";

type ExecutionProgressHeaderProps = {
  status: BusinessExecutionStatus;
  backendMissing?: boolean;
};

const phaseLabels: Record<ExecutionPhase, string> = {
  idea_captured: "Idea captured",
  blueprint: "Blueprint",
  permissions: "Permissions",
  github: "GitHub",
  scaffold: "Scaffold",
  vercel: "Vercel",
  deployment: "Deployment",
  validation: "Validation",
  blocked: "Blocked",
  completed: "Completed",
};

function healthLabel(health: BusinessExecutionStatus["health"]) {
  if (health === "on_track") return "On track";
  if (health === "needs_attention") return "Needs attention";
  if (health === "blocked") return "Blocked";
  return "Complete";
}

function progressTone(status: BusinessExecutionStatus) {
  if (status.health === "blocked") return "danger";
  if (status.blockers.length > 0 || status.health === "needs_attention") return "warning";
  if (status.health === "complete") return "success";
  return "accent";
}

export function ExecutionProgressHeader({
  status,
  backendMissing = false,
}: ExecutionProgressHeaderProps) {
  const tone = progressTone(status);

  return (
    <div className="rounded-lg border border-[#1C1C1C] bg-[#080808] p-5">
      <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-3xl">
          <div className="flex flex-wrap items-center gap-3">
            <SectionLabel>Execution Command Center</SectionLabel>
            <ExecutionStatusPill label={healthLabel(status.health)} status={status.health} />
            {backendMissing ? (
              <ExecutionStatusPill label="Fallback mode" status="warning" />
            ) : null}
          </div>
          <h2 className="mt-4 text-3xl font-semibold tracking-tight text-[#F0F0F0]">
            {phaseLabels[status.currentPhase]}
          </h2>
          <p className="mt-3 text-sm leading-7 text-[#888888] sm:text-base">
            Live execution posture for this business: phase, milestones, blockers,
            recommended actions, external assets, and latest run history.
          </p>
        </div>

        <div className="w-full max-w-sm rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
          <div className="flex items-end justify-between gap-4">
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#444444]">
                Overall progress
              </p>
              <p className={`mt-2 text-4xl font-semibold tracking-tight ${
                tone === "danger"
                  ? "text-[#FCA5A5]"
                  : tone === "warning"
                    ? "text-[#FCD34D]"
                    : tone === "success"
                      ? "text-[#86EFAC]"
                      : "text-[#A5B4FC]"
              }`}
              >
                {status.progressPercent}%
              </p>
            </div>
            {status.updatedAt ? (
              <p className="pb-1 text-right text-xs leading-5 text-[#666666]">
                Updated {new Date(status.updatedAt).toLocaleString()}
              </p>
            ) : null}
          </div>
          <div className="mt-4 h-2 overflow-hidden rounded-full bg-[#1C1C1C]">
            <div
              className={`h-full rounded-full ${
                tone === "danger"
                  ? "bg-[#EF4444]"
                  : tone === "warning"
                    ? "bg-[#F59E0B]"
                    : tone === "success"
                      ? "bg-[#22C55E]"
                      : "bg-[#4F46E5]"
              }`}
              style={{ width: `${status.progressPercent}%` }}
            />
          </div>
        </div>
      </div>

      <div className="mt-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        <DataTile
          label="Current phase"
          value={phaseLabels[status.currentPhase]}
          detail="Primary execution lane"
          tone="accent"
        />
        <DataTile
          label="Health"
          value={healthLabel(status.health)}
          detail="Derived from blockers and milestone state"
          tone={tone}
        />
        <DataTile
          label="Blockers"
          value={String(status.blockers.length)}
          detail="Founder or bucks.ai intervention needed"
          tone={status.blockers.length > 0 ? "warning" : "success"}
        />
        <DataTile
          label="Assets"
          value={String(status.assets.length)}
          detail="Blueprint, permissions, repo, deploy targets"
          tone={status.assets.length > 0 ? "accent" : "neutral"}
        />
      </div>
    </div>
  );
}
