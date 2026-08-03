"use client";

import { useCallback, useEffect, useState } from "react";
import { executeBusiness, fetchLatestMission } from "@/lib/execute-client";
import { StatusPill } from "@/components/ui/StatusPill";
import type { MissionRecord } from "@/types/database";

type ExecutePanelProps = {
  businessId: string;
};

const STATUS_LABEL: Record<string, string> = {
  queued: "Queued",
  running: "Running",
  completed: "Completed",
  failed: "Failed",
  cancelled: "Cancelled",
};

/* Mission status maps onto the shared chip vocabulary rather than a local
   set of outline+fill classes, so it matches every other status in the
   workspace. */
const STATUS_VARIANT: Record<
  string,
  "accent" | "success" | "warning" | "danger" | "neutral"
> = {
  queued: "warning",
  running: "accent",
  completed: "success",
  failed: "danger",
  cancelled: "neutral",
};

export function ExecutePanel({ businessId }: ExecutePanelProps) {
  const [mission, setMission] = useState<MissionRecord | null>(null);
  const [loading, setLoading] = useState(true);
  const [executing, setExecuting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const loadMission = useCallback(async () => {
    const result = await fetchLatestMission(businessId);
    if (!result.ok) {
      // api_unavailable (route not merged yet) degrades silently — the
      // Execute button just isn't available, not an error to surface.
      if (result.code !== "api_unavailable") {
        setError(result.error);
      }
      return;
    }
    setMission(result.data.data.mission);
  }, [businessId]);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoading(true);
      await loadMission();
      if (!cancelled) setLoading(false);
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [loadMission]);

  async function handleExecute() {
    setExecuting(true);
    setError(null);
    const result = await executeBusiness(businessId);
    setExecuting(false);

    if (!result.ok) {
      setError(result.error);
      return;
    }

    setMission(result.data.data.mission);
  }

  if (loading) return null;

  const statusLabel = mission ? (STATUS_LABEL[mission.status] ?? mission.status) : null;
  const statusVariant = mission
    ? (STATUS_VARIANT[mission.status] ?? "warning")
    : "neutral";

  return (
    <div className="flex w-full min-w-[16rem] shrink-0 flex-col gap-2.5 sm:w-auto lg:items-end">
      <div className="flex flex-wrap items-center gap-2.5">
        <button
          type="button"
          aria-label="Execute"
          onClick={handleExecute}
          disabled={executing}
          className="min-h-11 rounded-xl bg-accent bg-[image:var(--cta-gradient)] px-4 py-2.5 text-sm font-semibold text-accent-contrast shadow-[var(--shadow-cta)] transition-transform duration-200 hover:-translate-y-0.5 disabled:opacity-50 disabled:hover:translate-y-0"
        >
          {executing ? "Executing…" : "Execute"}
        </button>
        {statusLabel ? (
          <StatusPill label={statusLabel} variant={statusVariant} />
        ) : null}
      </div>
      <p className="max-w-xs text-xs leading-5 text-muted-foreground lg:text-right">
        Execute queues the runner to turn this business plan into shipped work.
      </p>
      {error ? (
        <p role="alert" className="max-w-xs text-right text-xs text-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
