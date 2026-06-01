"use client";

import { useMemo, useState } from "react";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type {
  BusinessExecutionStatus,
  ExecutionTimelineEvent,
} from "@/types/execution-ui";

type FilterKey = "all" | "runs" | "tools" | "github" | "vercel" | "human";

type CompactActivityCenterProps = {
  business: DashboardBusiness;
  executionStatus?: BusinessExecutionStatus | null;
  maxRows?: number;
  compact?: boolean;
};

const filters: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "runs", label: "Runs" },
  { key: "tools", label: "Tools" },
  { key: "github", label: "GitHub" },
  { key: "vercel", label: "Vercel" },
  { key: "human", label: "Human" },
];

function matchesFilter(event: ExecutionTimelineEvent, filter: FilterKey) {
  if (filter === "all") return true;
  const haystack = `${event.category} ${event.title} ${event.actor ?? ""} ${event.status ?? ""}`.toLowerCase();
  if (filter === "runs") return haystack.includes("run") || haystack.includes("execution");
  if (filter === "tools") return haystack.includes("tool") || haystack.includes("permission");
  if (filter === "github") return haystack.includes("github") || haystack.includes("repo");
  if (filter === "vercel") return haystack.includes("vercel") || haystack.includes("deploy");
  return haystack.includes("human") || haystack.includes("approval") || haystack.includes("founder");
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

function fallbackEvents(business: DashboardBusiness): ExecutionTimelineEvent[] {
  if (business.activityLogs && business.activityLogs.length > 0) {
    return business.activityLogs.map((log, index) => ({
      id: `${log.activityType}-${log.createdAt}-${index}`,
      category: log.activityType,
      title: log.message,
      message: log.message,
      actor: log.activityType,
      status: "log",
      createdAt: log.createdAt,
      metadata: log.metadata,
    }));
  }

  return business.activity.map((item, index) => ({
    id: `legacy-${index}`,
    category: item.statusLabel ?? item.tone ?? "activity",
    title: item.event,
    message: item.event,
    actor: item.actor,
    status: item.statusLabel ?? item.tone ?? "log",
    createdAt: new Date().toISOString(),
    metadata: { time: item.time },
  }));
}

export function CompactActivityCenter({
  business,
  executionStatus,
  maxRows,
  compact = false,
}: CompactActivityCenterProps) {
  const [filter, setFilter] = useState<FilterKey>("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const events = useMemo(() => {
    const source =
      executionStatus?.timeline && executionStatus.timeline.length > 0
        ? executionStatus.timeline
        : fallbackEvents(business);

    return [...source].sort(
      (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
    );
  }, [business, executionStatus]);

  const filtered = events.filter((event) => matchesFilter(event, filter));
  const visible = typeof maxRows === "number" ? filtered.slice(0, maxRows) : filtered;

  return (
    <div className="space-y-3">
      {!compact ? (
        <div className="flex gap-1.5 overflow-x-auto pb-1" style={{ scrollbarWidth: "none" }}>
          {filters.map((item) => (
            <button
              key={item.key}
              type="button"
              onClick={() => setFilter(item.key)}
              className={`shrink-0 rounded border px-2.5 py-1.5 font-mono text-[10px] uppercase tracking-widest transition-colors ${
                filter === item.key
                  ? "border-accent/40 bg-accent/10 text-accent"
                  : "border-border bg-background text-muted hover:text-secondary"
              }`}
            >
              {item.label}
            </button>
          ))}
        </div>
      ) : null}

      {visible.length === 0 ? (
        <p className="rounded border border-border bg-background px-3 py-3 text-xs leading-5 text-muted">
          No activity has been recorded for this view yet.
        </p>
      ) : (
        <div className="space-y-1.5">
          {visible.map((event) => {
            const expanded = expandedId === event.id;

            return (
              <button
                key={event.id}
                type="button"
                onClick={() => setExpandedId(expanded ? null : event.id)}
                className="w-full rounded border border-border bg-background px-3 py-2 text-left transition-colors hover:border-accent/35"
              >
                <div className="flex items-start gap-2.5">
                  <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />
                  <div className="min-w-0 flex-1">
                    <div className="flex items-center justify-between gap-2">
                      <p className="truncate text-xs font-medium text-secondary">
                        {event.title}
                      </p>
                      <p className="shrink-0 font-mono text-[10px] text-muted">
                        {formatDate(event.createdAt)}
                      </p>
                    </div>
                    <p className="mt-0.5 font-mono text-[10px] uppercase tracking-widest text-muted">
                      {event.category}
                    </p>
                    {expanded ? (
                      <p className="mt-2 text-xs leading-5 text-secondary">
                        {event.message && event.message !== event.title
                          ? event.message
                          : event.actor
                            ? `Actor: ${event.actor}`
                            : "No additional event detail recorded."}
                      </p>
                    ) : null}
                  </div>
                </div>
              </button>
            );
          })}
        </div>
      )}
    </div>
  );
}
