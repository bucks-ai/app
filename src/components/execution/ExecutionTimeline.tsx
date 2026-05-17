import { SectionLabel } from "@/components/ui/SectionLabel";
import { ExecutionStatusPill } from "@/components/execution/ExecutionStatusPill";
import type { ExecutionTimelineEvent } from "@/types/execution-ui";

type ExecutionTimelineProps = {
  events: ExecutionTimelineEvent[];
};

function formatCategory(category: string) {
  return category
    .split(/[_\s-]+/)
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function metadataSummary(metadata: Record<string, unknown> | null | undefined) {
  if (!metadata) return null;

  const entries = Object.entries(metadata).filter(([, value]) => {
    return typeof value === "string" || typeof value === "number" || typeof value === "boolean";
  });

  if (entries.length === 0) return null;

  return entries
    .slice(0, 3)
    .map(([key, value]) => `${formatCategory(key)}: ${String(value)}`)
    .join(" | ");
}

export function ExecutionTimeline({ events }: ExecutionTimelineProps) {
  const orderedEvents = [...events].sort(
    (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
  );

  return (
    <div className="rounded-lg border border-[#1C1C1C] bg-[#080808] p-5">
      <SectionLabel>Run history</SectionLabel>
      <div className="mt-4 space-y-3">
        {orderedEvents.length > 0 ? (
          orderedEvents.map((event) => {
            const summary = metadataSummary(event.metadata);

            return (
              <div
                key={event.id}
                className="rounded-md border border-[#1C1C1C] bg-[#0F0F0F] p-4"
              >
                <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                  <div>
                    <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#444444]">
                      {new Date(event.createdAt).toLocaleString()}
                    </p>
                    <h3 className="mt-2 text-sm font-semibold text-[#F0F0F0]">
                      {event.title}
                    </h3>
                  </div>
                  <ExecutionStatusPill label={formatCategory(event.category)} />
                </div>
                {event.message && event.message !== event.title ? (
                  <p className="mt-3 text-sm leading-6 text-[#888888]">{event.message}</p>
                ) : null}
                <div className="mt-3 flex flex-wrap gap-2 text-xs leading-5 text-[#666666]">
                  {event.actor ? <span>Actor: {event.actor}</span> : null}
                  {event.status ? <span>Status: {event.status}</span> : null}
                  {summary ? <span className="break-words">{summary}</span> : null}
                </div>
              </div>
            );
          })
        ) : (
          <p className="rounded-md border border-[#1C1C1C] bg-[#0F0F0F] p-4 text-sm leading-6 text-[#888888]">
            No execution events recorded yet.
          </p>
        )}
      </div>
    </div>
  );
}
