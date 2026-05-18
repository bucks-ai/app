"use client";

import { useState } from "react";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { BusinessExecutionStatus } from "@/types/execution-ui";

type ActivityTabProps = {
  business: DashboardBusiness;
  executionStatus?: BusinessExecutionStatus | null;
};

type FilterKey = "all" | "runs" | "tools" | "github" | "vercel" | "human";

const FILTERS: { key: FilterKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "runs", label: "Runs" },
  { key: "tools", label: "Tools" },
  { key: "github", label: "GitHub" },
  { key: "vercel", label: "Vercel" },
  { key: "human", label: "Human" },
];

function matchesFilter(category: string, filter: FilterKey): boolean {
  if (filter === "all") return true;
  const cat = category.toLowerCase();
  if (filter === "runs") return cat.includes("run") || cat.includes("execution");
  if (filter === "tools") return cat.includes("tool") || cat.includes("permission");
  if (filter === "github") return cat.includes("github") || cat.includes("repo");
  if (filter === "vercel") return cat.includes("vercel") || cat.includes("deploy");
  if (filter === "human") return cat.includes("human") || cat.includes("approval") || cat.includes("founder");
  return true;
}

function formatEventDate(iso: string) {
  return new Intl.DateTimeFormat("en-US", {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(iso));
}

export function ActivityTab({ business, executionStatus }: ActivityTabProps) {
  const [filter, setFilter] = useState<FilterKey>("all");

  const timelineEvents = executionStatus?.timeline ?? [];
  const legacyActivity = business.activity ?? [];

  const allItems =
    timelineEvents.length > 0
      ? timelineEvents
      : legacyActivity.map((item, i) => ({
          id: `legacy-${i}`,
          category: item.statusLabel ?? item.tone ?? "activity",
          title: item.event,
          message: item.event,
          actor: item.actor,
          status: item.statusLabel ?? item.tone ?? "log",
          createdAt: new Date().toISOString(),
          metadata: { time: item.time } as Record<string, unknown>,
        }));

  const filtered = allItems.filter((item) =>
    matchesFilter(item.category ?? "", filter)
  );

  return (
    <div className="space-y-4">
      {/* Filter tabs */}
      <div className="flex flex-wrap gap-1.5">
        {FILTERS.map((f) => (
          <button
            key={f.key}
            type="button"
            onClick={() => setFilter(f.key)}
            className={`rounded border px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest transition-colors ${
              filter === f.key
                ? "border-[#4F46E5]/40 bg-[#4F46E5]/10 text-[#A5B4FC]"
                : "border-[#1C1C1C] bg-[#0F0F0F] text-[#444] hover:text-[#888]"
            }`}
          >
            {f.label}
          </button>
        ))}
      </div>

      {/* Activity list */}
      {filtered.length === 0 ? (
        <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-6 text-center">
          <p className="text-sm text-[#444]">No activity matching this filter.</p>
        </div>
      ) : (
        <div className="space-y-1.5">
          {filtered.map((event) => (
            <div
              key={event.id}
              className="flex items-start gap-3 rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] px-4 py-3"
            >
              <div className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-[#2A2A2A]" />
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="text-sm text-[#D4D4D4]">{event.title}</p>
                  <p className="shrink-0 font-mono text-[10px] text-[#444]">
                    {formatEventDate(event.createdAt)}
                  </p>
                </div>
                {event.actor ? (
                  <p className="mt-0.5 font-mono text-[10px] uppercase tracking-widest text-[#333]">
                    {event.actor}
                  </p>
                ) : null}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
