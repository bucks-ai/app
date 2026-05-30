"use client";

import { useState } from "react";
import type {
  ValidationHypothesisRecord,
  ValidationHypothesisStatus,
} from "@/types/validation-ui";
import { updateValidationHypothesis } from "@/lib/validation-client";
import { ValidationStatusBadge } from "@/components/validation/ValidationStatusBadge";

type HypothesisTrackerProps = {
  businessId: string;
  hypotheses: ValidationHypothesisRecord[];
  onChange: () => void;
};

const STATUSES: ValidationHypothesisStatus[] = [
  "untested",
  "testing",
  "supported",
  "rejected",
  "inconclusive",
];

export function HypothesisTracker({
  businessId,
  hypotheses,
  onChange,
}: HypothesisTrackerProps) {
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleStatusChange(id: string, status: ValidationHypothesisStatus) {
    setUpdatingId(id);
    setError(null);

    const result = await updateValidationHypothesis(businessId, { id, status });
    setUpdatingId(null);

    if (!result.ok) {
      setError(result.error);
      return;
    }

    onChange();
  }

  return (
    <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
          Hypotheses
        </p>
        <span className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
          {hypotheses.length} tracked
        </span>
      </div>

      {error ? (
        <p className="mt-3 rounded border border-[#EF4444]/30 bg-[#EF4444]/10 px-3 py-2 text-sm leading-6 text-[#FECACA]">
          {error}
        </p>
      ) : null}

      <div className="mt-3 space-y-2">
        {hypotheses.length > 0 ? (
          hypotheses.map((hypothesis) => (
            <div
              key={hypothesis.id}
              className="rounded border border-[#1C1C1C] bg-[#080808] p-3"
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-[#F0F0F0]">
                      {hypothesis.title}
                    </p>
                    <ValidationStatusBadge value={hypothesis.priority} />
                  </div>
                  {hypothesis.assumption ? (
                    <p className="mt-1 text-xs leading-5 text-[#888]">
                      {hypothesis.assumption}
                    </p>
                  ) : null}
                  {hypothesis.success_criteria ? (
                    <p className="mt-1 text-xs leading-5 text-[#666]">
                      Success: {hypothesis.success_criteria}
                    </p>
                  ) : null}
                </div>
                <div className="flex shrink-0 flex-wrap items-center gap-2">
                  <ValidationStatusBadge value={hypothesis.status} />
                  <select
                    value={hypothesis.status}
                    disabled={updatingId === hypothesis.id}
                    onChange={(event) =>
                      handleStatusChange(
                        hypothesis.id,
                        event.target.value as ValidationHypothesisStatus
                      )
                    }
                    className="min-h-9 rounded border border-[#1C1C1C] bg-[#141414] px-2.5 py-2 text-xs text-[#D4D4D4] outline-none transition-colors focus:border-[#4F46E5]/70 disabled:opacity-60"
                  >
                    {STATUSES.map((status) => (
                      <option key={status} value={status}>
                        {status.replaceAll("_", " ")}
                      </option>
                    ))}
                  </select>
                </div>
              </div>
            </div>
          ))
        ) : (
          <p className="rounded border border-[#1C1C1C] bg-[#080808] px-3 py-4 text-sm text-[#666]">
            No hypotheses yet.
          </p>
        )}
      </div>
    </div>
  );
}
