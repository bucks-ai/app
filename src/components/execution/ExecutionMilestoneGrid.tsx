import Link from "next/link";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { ExecutionStatusPill } from "@/components/execution/ExecutionStatusPill";
import type { ExecutionMilestone, ExecutionPhase } from "@/types/execution-ui";

type ExecutionMilestoneGridProps = {
  milestones: ExecutionMilestone[];
};

const defaultMilestones: Array<{ id: ExecutionPhase; label: string }> = [
  { id: "idea_captured", label: "Idea captured" },
  { id: "blueprint", label: "Blueprint" },
  { id: "permissions", label: "Permissions" },
  { id: "github", label: "GitHub" },
  { id: "scaffold", label: "Scaffold" },
  { id: "vercel", label: "Vercel" },
  { id: "deployment", label: "Deployment" },
  { id: "validation", label: "Validation" },
];

function statusLabel(status: ExecutionMilestone["status"]) {
  if (status === "in_progress") return "In progress";
  return status.charAt(0).toUpperCase() + status.slice(1);
}

export function ExecutionMilestoneGrid({ milestones }: ExecutionMilestoneGridProps) {
  const byId = new Map(milestones.map((milestone) => [milestone.id, milestone]));
  const orderedMilestones: ExecutionMilestone[] = defaultMilestones.map((milestone) => {
    const savedMilestone = byId.get(milestone.id);

    return {
      id: milestone.id,
      label: savedMilestone?.label ?? milestone.label,
      status: savedMilestone?.status ?? "pending",
      description: savedMilestone?.description,
      completedAt: savedMilestone?.completedAt,
      href: savedMilestone?.href,
    };
  });

  return (
    <div>
      <SectionLabel>Milestones</SectionLabel>
      <div className="mt-4 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
        {orderedMilestones.map((milestone) => {
          const body = (
            <div className="h-full rounded-lg border border-[#1C1C1C] bg-[#080808] p-4 transition-colors hover:border-[#4F46E5]/50">
              <div className="flex items-start justify-between gap-3">
                <h3 className="text-sm font-semibold text-[#F0F0F0]">{milestone.label}</h3>
                <ExecutionStatusPill
                  label={statusLabel(milestone.status)}
                  status={milestone.status}
                />
              </div>
              <p className="mt-3 min-h-12 text-sm leading-6 text-[#888888]">
                {milestone.description ?? "Awaiting execution signal from the backend."}
              </p>
              {milestone.completedAt ? (
                <p className="mt-3 font-mono text-[11px] uppercase tracking-[0.18em] text-[#444444]">
                  {new Date(milestone.completedAt).toLocaleString()}
                </p>
              ) : null}
            </div>
          );

          return milestone.href ? (
            <Link key={milestone.id} href={milestone.href}>
              {body}
            </Link>
          ) : (
            <div key={milestone.id}>{body}</div>
          );
        })}
      </div>
    </div>
  );
}
