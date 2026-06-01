"use client";

import { useEffect, useState } from "react";
import { fetchResearchWorkspace } from "@/lib/research-client";
import type { ResearchWorkspace } from "@/types/research-ui";
import { resolveResearchNextAction } from "@/components/research/ResearchNextActionCard";
import { ResearchStatusBadge } from "@/components/research/ResearchStatusBadge";

type ResearchRailCardProps = {
  businessId: string;
  onOpenResearch: () => void;
};

export function ResearchRailCard({
  businessId,
  onOpenResearch,
}: ResearchRailCardProps) {
  const [workspace, setWorkspace] = useState<ResearchWorkspace | null>(null);
  const [message, setMessage] = useState("Not generated yet.");

  useEffect(() => {
    let ignore = false;

    async function load() {
      const result = await fetchResearchWorkspace(businessId);
      if (ignore) return;

      if (!result.ok || result.data.summary.canGenerate) {
        setWorkspace(null);
        setMessage("Not generated yet.");
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

  const action = resolveResearchNextAction(workspace);

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
          Research
        </p>
        {workspace ? <ResearchStatusBadge value={workspace.summary.status} /> : null}
      </div>
      <button
        type="button"
        onClick={onOpenResearch}
        className="mt-3 w-full rounded border border-border bg-background px-3 py-2 text-left transition-colors hover:border-accent/45"
      >
        <p className="truncate text-xs font-semibold text-secondary">
          {workspace
            ? `Opportunity ${workspace.summary.opportunityScore ?? "--"}`
            : message}
        </p>
        {workspace ? (
          <p className="mt-1 break-words text-xs leading-5 text-muted">
            {action.title}
          </p>
        ) : null}
      </button>
    </div>
  );
}
