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
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
          Hypotheses
        </p>
        <span className="font-mono text-[10px] uppercase tracking-widest text-muted">
          {hypotheses.length} tracked
        </span>
      </div>

      {error ? (
        <p className="mt-3 rounded border border-error/30 bg-error/10 px-3 py-2 text-sm leading-6 text-error">
          {error}
        </p>
      ) : null}

      <div className="mt-3 space-y-2">
        {hypotheses.length > 0 ? (
          hypotheses.map((hypothesis) => (
            <div
              key={hypothesis.id}
              className="rounded border border-border bg-background p-3"
            >
              <div className="flex flex-col gap-3 md:flex-row md:items-start md:justify-between">
                <div className="min-w-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm font-semibold text-foreground">
                      {hypothesis.title}
                    </p>
                    <ValidationStatusBadge value={hypothesis.priority} />
                  </div>
                  {hypothesis.assumption ? (
                    <p className="mt-1 text-xs leading-5 text-secondary">
                      {hypothesis.assumption}
                    </p>
                  ) : null}
                  {hypothesis.success_criteria ? (
                    <p className="mt-1 text-xs leading-5 text-muted">
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
                    className="min-h-9 rounded border border-border bg-elevated px-2.5 py-2 text-xs text-secondary outline-none transition-colors focus:border-accent/70 disabled:opacity-60"
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
          <p className="rounded border border-border bg-background px-3 py-4 text-sm text-muted">
            No hypotheses yet.
          </p>
        )}
      </div>
    </div>
  );
}
