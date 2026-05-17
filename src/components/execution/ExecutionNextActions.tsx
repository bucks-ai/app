import Link from "next/link";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { ExecutionStatusPill } from "@/components/execution/ExecutionStatusPill";
import type { ExecutionNextAction } from "@/types/execution-ui";

type ExecutionNextActionsProps = {
  actions: ExecutionNextAction[];
};

function actorLabel(actor: ExecutionNextAction["actor"]) {
  return actor === "founder" ? "Founder" : "bucks.ai";
}

export function ExecutionNextActions({ actions }: ExecutionNextActionsProps) {
  return (
    <div className="rounded-lg border border-[#1C1C1C] bg-[#080808] p-5">
      <SectionLabel>Next recommended actions</SectionLabel>
      <div className="mt-4 space-y-3">
        {actions.length > 0 ? (
          actions.map((action) => (
            <div key={action.id} className="rounded-md border border-[#1C1C1C] bg-[#0F0F0F] p-4">
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#444444]">
                    {actorLabel(action.actor)}
                  </p>
                  <h3 className="mt-2 text-sm font-semibold text-[#F0F0F0]">
                    {action.title}
                  </h3>
                </div>
                <ExecutionStatusPill
                  label={actorLabel(action.actor)}
                  status={action.actor}
                />
              </div>
              {action.description ? (
                <p className="mt-3 text-sm leading-6 text-[#888888]">
                  {action.description}
                </p>
              ) : null}
              {action.href ? (
                <Link
                  href={action.href}
                  className="mt-4 inline-flex rounded-md border border-[#4F46E5]/35 px-3 py-2 text-sm font-semibold text-[#A5B4FC] transition-colors hover:border-[#818CF8]/70 hover:text-[#C7D2FE]"
                >
                  Open action
                </Link>
              ) : null}
            </div>
          ))
        ) : (
          <p className="rounded-md border border-[#1C1C1C] bg-[#0F0F0F] p-4 text-sm leading-6 text-[#888888]">
            No recommended actions are queued yet.
          </p>
        )}
      </div>
    </div>
  );
}
