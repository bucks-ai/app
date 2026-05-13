import { StatusPill } from "@/components/ui/StatusPill";
import type { HumanAction } from "@/components/dashboard/mock-data";

type HumanActionQueueProps = {
  actions: HumanAction[];
};

export function HumanActionQueue({ actions }: HumanActionQueueProps) {
  return (
    <div className="space-y-3">
      {actions.map((action) => (
        <div
          key={`${action.business}-${action.title}`}
          className="rounded-md border border-[#F59E0B]/25 bg-[#F59E0B]/10 p-4"
        >
          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#FCD34D]">
                {action.business}
              </p>
              <h3 className="mt-2 text-base font-semibold text-[#F0F0F0]">
                {action.title}
              </h3>
            </div>
            <StatusPill label={action.status} variant="warning" />
          </div>
          <p className="mt-3 text-sm leading-6 text-[#FDE68A]">{action.reason}</p>
        </div>
      ))}
    </div>
  );
}
