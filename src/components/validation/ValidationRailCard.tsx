"use client";

import { useEffect, useState } from "react";
import { fetchValidationWorkspace } from "@/lib/validation-client";
import type { ValidationWorkspace } from "@/types/validation-ui";
import { resolveValidationNextAction } from "@/components/validation/ValidationNextActionCard";
import { ValidationStatusBadge } from "@/components/validation/ValidationStatusBadge";

type ValidationRailCardProps = {
  businessId: string;
  onOpenValidation: () => void;
};

export function ValidationRailCard({
  businessId,
  onOpenValidation,
}: ValidationRailCardProps) {
  const [workspace, setWorkspace] = useState<ValidationWorkspace | null>(null);
  const [message, setMessage] = useState("Not set up yet.");

  useEffect(() => {
    let ignore = false;

    async function load() {
      const result = await fetchValidationWorkspace(businessId);
      if (ignore) return;

      if (!result.ok) {
        setWorkspace(null);
        setMessage("Not set up yet.");
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

  const action = resolveValidationNextAction(workspace);

  return (
    <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
      <div className="flex items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
          Validation
        </p>
        {workspace ? <ValidationStatusBadge value={workspace.summary.status} /> : null}
      </div>
      <button
        type="button"
        onClick={onOpenValidation}
        className="mt-3 w-full rounded border border-[#1C1C1C] bg-[#080808] px-3 py-2 text-left transition-colors hover:border-[#4F46E5]/45"
      >
        <p className="truncate text-xs font-semibold text-[#D4D4D4]">
          {workspace ? action.title : message}
        </p>
        {workspace ? (
          <p className="mt-1 text-xs leading-5 text-[#666]">{action.description}</p>
        ) : null}
      </button>
    </div>
  );
}
