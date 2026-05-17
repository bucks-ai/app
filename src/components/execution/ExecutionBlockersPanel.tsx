import Link from "next/link";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { ExecutionStatusPill } from "@/components/execution/ExecutionStatusPill";
import type { ExecutionBlocker } from "@/types/execution-ui";

type ExecutionBlockersPanelProps = {
  blockers: ExecutionBlocker[];
};

function ownerLabel(owner: ExecutionBlocker["owner"]) {
  return owner === "founder" ? "Founder" : "bucks.ai";
}

export function ExecutionBlockersPanel({ blockers }: ExecutionBlockersPanelProps) {
  return (
    <div className="rounded-lg border border-[#1C1C1C] bg-[#080808] p-5">
      <div className="flex items-center justify-between gap-3">
        <SectionLabel tone={blockers.length > 0 ? "warning" : "muted"}>
          Blockers
        </SectionLabel>
        <ExecutionStatusPill
          label={blockers.length > 0 ? `${blockers.length} active` : "Clear"}
          status={blockers.length > 0 ? "warning" : "success"}
        />
      </div>

      <div className="mt-4 space-y-3">
        {blockers.length > 0 ? (
          blockers.map((blocker) => (
            <div
              key={blocker.id}
              className="rounded-md border border-[#F59E0B]/25 bg-[#F59E0B]/10 p-4"
            >
              <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                <div>
                  <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#FCD34D]">
                    {ownerLabel(blocker.owner)}
                  </p>
                  <h3 className="mt-2 text-sm font-semibold text-[#F0F0F0]">
                    {blocker.title}
                  </h3>
                </div>
                <ExecutionStatusPill label={blocker.severity} status={blocker.severity} />
              </div>
              {blocker.description ? (
                <p className="mt-3 text-sm leading-6 text-[#FDE68A]">
                  {blocker.description}
                </p>
              ) : null}
              {blocker.href ? (
                <Link
                  href={blocker.href}
                  className="mt-4 inline-flex rounded-md border border-[#F59E0B]/35 px-3 py-2 text-sm font-semibold text-[#FCD34D] transition-colors hover:border-[#FCD34D]/70 hover:text-[#FEF3C7]"
                >
                  Review blocker
                </Link>
              ) : null}
            </div>
          ))
        ) : (
          <p className="rounded-md border border-[#1C1C1C] bg-[#0F0F0F] p-4 text-sm leading-6 text-[#888888]">
            No active blockers are recorded.
          </p>
        )}
      </div>
    </div>
  );
}
