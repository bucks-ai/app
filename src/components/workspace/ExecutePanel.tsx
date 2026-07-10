"use client";

import { useCallback, useEffect, useState } from "react";
import { executeBusiness, fetchLatestMission } from "@/lib/execute-client";
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

const STATUS_TONE: Record<string, string> = {
  queued: "border-warning/30 bg-warning/10 text-warning",
  running: "border-accent/30 bg-accent/10 text-accent",
  completed: "border-success/30 bg-success/10 text-success",
  failed: "border-error/30 bg-error/10 text-error",
  cancelled: "border-border bg-background text-muted",
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
  const statusTone = mission ? (STATUS_TONE[mission.status] ?? STATUS_TONE.queued) : null;

  return (
    <div className="flex shrink-0 flex-col items-end gap-1.5">
      <div className="flex items-center gap-2">
        {statusLabel ? (
          <span
            className={`rounded border px-2 py-1 font-mono text-[10px] uppercase tracking-widest ${statusTone}`}
          >
            {statusLabel}
          </span>
        ) : null}
        <button
          type="button"
          onClick={handleExecute}
          disabled={executing}
          className="rounded-md bg-accent px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-accent-contrast transition-colors hover:bg-accent-hover disabled:opacity-50"
        >
          {executing ? "Executing..." : mission ? "Execute again" : "Execute"}
        </button>
      </div>
      {error ? <p className="max-w-xs text-right text-xs text-error">{error}</p> : null}
    </div>
  );
}
