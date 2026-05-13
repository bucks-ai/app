import { StatusPill } from "@/components/ui/StatusPill";
import type { ActivityItem } from "@/components/dashboard/mock-data";

type ActivityLogProps = {
  items: ActivityItem[];
};

export function ActivityLog({ items }: ActivityLogProps) {
  return (
    <div className="space-y-3">
      {items.map((item) => (
        <div
          key={`${item.time}-${item.actor}-${item.event}`}
          className="rounded-md border border-[#1C1C1C] bg-[#080808] p-4"
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#444444]">
                {item.time}
              </p>
              <p className="mt-2 text-sm font-medium text-[#F0F0F0]">{item.actor}</p>
            </div>
            <StatusPill
              label={item.statusLabel ?? item.tone ?? "log"}
              variant={item.tone ?? "neutral"}
            />
          </div>
          <p className="mt-3 text-sm leading-6 text-[#888888]">{item.event}</p>
        </div>
      ))}
    </div>
  );
}
