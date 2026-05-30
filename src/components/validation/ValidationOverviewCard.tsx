"use client";

import { useEffect, useState } from "react";
import { fetchValidationWorkspace } from "@/lib/validation-client";
import type { ValidationSummary } from "@/types/validation-ui";
import { ValidationStatusBadge } from "@/components/validation/ValidationStatusBadge";

type ValidationOverviewCardProps = {
  businessId: string;
  onOpenValidation: () => void;
};

export function ValidationOverviewCard({
  businessId,
  onOpenValidation,
}: ValidationOverviewCardProps) {
  const [summary, setSummary] = useState<ValidationSummary | null>(null);
  const [message, setMessage] = useState("Checking validation...");

  useEffect(() => {
    let ignore = false;

    async function load() {
      const result = await fetchValidationWorkspace(businessId);
      if (ignore) return;

      if (!result.ok) {
        setSummary(null);
        setMessage("Validation not set up yet.");
        return;
      }

      setSummary(result.data.summary);
      setMessage("");
    }

    void load();

    return () => {
      ignore = true;
    };
  }, [businessId]);

  return (
    <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
          Validation
        </p>
        <button
          type="button"
          onClick={onOpenValidation}
          className="font-mono text-[10px] uppercase tracking-widest text-[#444] transition-colors hover:text-[#888]"
        >
          Open
        </button>
      </div>

      {summary ? (
        <div className="mt-3 flex flex-wrap items-center gap-2">
          <ValidationStatusBadge value={summary.status} />
          <span className="rounded border border-[#1C1C1C] bg-[#080808] px-2.5 py-1 text-xs text-[#888]">
            {summary.leadCount} leads
          </span>
          <span className="rounded border border-[#1C1C1C] bg-[#080808] px-2.5 py-1 text-xs text-[#888]">
            {summary.feedbackNoteCount} feedback
          </span>
        </div>
      ) : (
        <p className="mt-3 text-sm leading-6 text-[#666]">{message}</p>
      )}
    </div>
  );
}
