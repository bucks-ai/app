"use client";

import { useEffect, useState } from "react";
import { fetchResearchWorkspace } from "@/lib/research-client";
import type { ResearchWorkspace } from "@/types/research-ui";
import { ResearchStatusBadge } from "@/components/research/ResearchStatusBadge";

type ResearchOverviewCardProps = {
  businessId: string;
  onOpenResearch: () => void;
};

export function ResearchOverviewCard({
  businessId,
  onOpenResearch,
}: ResearchOverviewCardProps) {
  const [workspace, setWorkspace] = useState<ResearchWorkspace | null>(null);
  const [message, setMessage] = useState("Checking research...");

  useEffect(() => {
    let ignore = false;

    async function load() {
      const result = await fetchResearchWorkspace(businessId);
      if (ignore) return;

      if (!result.ok || result.data.summary.canGenerate) {
        setWorkspace(null);
        setMessage("Research not generated yet.");
        return;
      }

      setWorkspace(result.data);
      setMessage("");
    }

    void load();

    return () => {
      ignore = true;
    };
  }, [businessId]);

  const topSegment = workspace?.segments[0]?.name;
  const targetCustomer = workspace?.report?.target_customer;

  return (
    <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
          Research
        </p>
        <button
          type="button"
          onClick={onOpenResearch}
          className="font-mono text-[10px] uppercase tracking-widest text-[#444] transition-colors hover:text-[#888]"
        >
          Open
        </button>
      </div>

      {workspace ? (
        <div className="mt-3 space-y-3">
          <div className="flex flex-wrap items-center gap-2">
            <ResearchStatusBadge value={workspace.summary.status} />
            <span className="rounded border border-[#1C1C1C] bg-[#080808] px-2.5 py-1 text-xs text-[#888]">
              Score {workspace.summary.opportunityScore ?? "--"}
            </span>
          </div>
          <p className="break-words text-sm leading-6 text-[#D4D4D4]">
            {topSegment ?? targetCustomer ?? "Target customer not captured yet."}
          </p>
        </div>
      ) : (
        <p className="mt-3 text-sm leading-6 text-[#666]">{message}</p>
      )}
    </div>
  );
}
