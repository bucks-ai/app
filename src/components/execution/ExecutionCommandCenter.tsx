"use client";

import { useCallback, useEffect, useState } from "react";
import { ExecutionAssetsPanel } from "@/components/execution/ExecutionAssetsPanel";
import { ExecutionBlockersPanel } from "@/components/execution/ExecutionBlockersPanel";
import { ExecutionMilestoneGrid } from "@/components/execution/ExecutionMilestoneGrid";
import { ExecutionNextActions } from "@/components/execution/ExecutionNextActions";
import { ExecutionProgressHeader } from "@/components/execution/ExecutionProgressHeader";
import { ExecutionTimeline } from "@/components/execution/ExecutionTimeline";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";
import {
  fetchBusinessExecutionStatus,
  fetchExecutionTimeline,
} from "@/lib/execution-client";
import type { BusinessExecutionStatus } from "@/types/execution-ui";

type ExecutionCommandCenterProps = {
  businessId: string;
  initialStatus?: BusinessExecutionStatus | null;
};

type LoadState = "loading" | "ready" | "backend_missing" | "error";

const BACKEND_MISSING =
  "Execution status backend is not available yet. Merge backend branch first.";

export function ExecutionCommandCenter({
  businessId,
  initialStatus = null,
}: ExecutionCommandCenterProps) {
  const [status, setStatus] = useState<BusinessExecutionStatus | null>(initialStatus);
  const [loadState, setLoadState] = useState<LoadState>(
    initialStatus ? "ready" : "loading"
  );
  const [message, setMessage] = useState<string | null>(null);

  const loadExecution = useCallback(async () => {
    const result = await fetchBusinessExecutionStatus(businessId);

    if (!result.ok) {
      if (result.code === "api_unavailable" && initialStatus) {
        setStatus(initialStatus);
        setLoadState("backend_missing");
        setMessage(BACKEND_MISSING);
        return;
      }

      if (result.code === "api_unavailable") {
        setLoadState("backend_missing");
        setMessage(BACKEND_MISSING);
        return;
      }

      setLoadState("error");
      setMessage(result.error);
      return;
    }

    const timelineResult = await fetchExecutionTimeline(businessId);
    const timeline =
      timelineResult.ok && timelineResult.data.length > 0
        ? timelineResult.data
        : result.data.timeline;

    setStatus({
      ...result.data,
      timeline,
    });
    setLoadState("ready");
    setMessage(result.warning ?? null);
  }, [businessId, initialStatus]);

  useEffect(() => {
    const timeout = window.setTimeout(() => {
      void loadExecution();
    }, 0);

    return () => window.clearTimeout(timeout);
  }, [loadExecution]);

  const isRefreshing = loadState === "loading" && Boolean(status);

  function handleRefresh() {
    setLoadState("loading");
    setMessage(null);
    void loadExecution();
  }

  return (
    <OperatorPanel
      id="execution-command-center"
      className="scroll-mt-28 p-6 shadow-[0_30px_120px_rgba(0,0,0,0.34)] sm:p-8"
      elevated
    >
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-center lg:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-3">
            <SectionLabel>Operating system layer</SectionLabel>
            {loadState === "backend_missing" ? (
              <StatusPill label="Backend pending" variant="warning" />
            ) : null}
          </div>
          <p className="mt-3 max-w-3xl text-sm leading-7 text-[#888888]">
            Command view for where this business stands, what is complete, what
            is blocked, and what should happen next.
          </p>
        </div>
        <button
          type="button"
          onClick={handleRefresh}
          disabled={loadState === "loading"}
          className="w-full rounded-md border border-[#1C1C1C] bg-[#080808] px-4 py-3 text-sm font-semibold text-[#D4D4D4] transition-colors hover:border-[#4F46E5]/60 hover:text-[#F0F0F0] disabled:cursor-not-allowed disabled:opacity-50 sm:w-auto"
        >
          {isRefreshing ? "Refreshing..." : "Refresh status"}
        </button>
      </div>

      {loadState === "loading" && !status ? (
        <div className="rounded-lg border border-[#1C1C1C] bg-[#080808] p-5">
          <StatusPill label="Loading" variant="accent" />
          <p className="mt-4 text-sm leading-6 text-[#888888]">
            Loading execution status and timeline.
          </p>
        </div>
      ) : null}

      {loadState === "error" ? (
        <div className="rounded-lg border border-[#EF4444]/30 bg-[#EF4444]/10 p-5">
          <StatusPill label="Execution status unavailable" variant="danger" />
          <p className="mt-4 text-sm leading-6 text-[#FECACA]">
            {message ?? "Execution status could not be loaded."}
          </p>
        </div>
      ) : null}

      {loadState === "backend_missing" ? (
        <div className="mb-5 rounded-lg border border-[#F59E0B]/30 bg-[#F59E0B]/10 p-5">
          <StatusPill label="Fallback mode" variant="warning" />
          <p className="mt-4 text-sm leading-6 text-[#FDE68A]">
            {message ?? BACKEND_MISSING} Showing a compact status inferred from
            existing blueprint, permissions, assets, and activity logs.
          </p>
        </div>
      ) : null}

      {status ? (
        <div className="space-y-6">
          <ExecutionProgressHeader
            status={status}
            backendMissing={loadState === "backend_missing"}
          />
          <ExecutionMilestoneGrid milestones={status.milestones} />
          <div className="grid gap-6 xl:grid-cols-2">
            <ExecutionBlockersPanel blockers={status.blockers} />
            <ExecutionNextActions actions={status.nextActions} />
          </div>
          <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
            <ExecutionAssetsPanel assets={status.assets} />
            <ExecutionTimeline events={status.timeline} />
          </div>
        </div>
      ) : null}
    </OperatorPanel>
  );
}
