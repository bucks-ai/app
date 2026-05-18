import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import type { BusinessExecutionStatus } from "@/types/execution-ui";
import { CompactActivityCenter } from "@/components/workspace/CompactActivityCenter";

type ActivityTabProps = {
  business: DashboardBusiness;
  executionStatus?: BusinessExecutionStatus | null;
};

export function ActivityTab({ business, executionStatus }: ActivityTabProps) {
  return (
    <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4 sm:p-5">
      <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
            Activity
          </p>
          <h2 className="mt-1 text-lg font-semibold text-[#F0F0F0]">
            Run history and operating log
          </h2>
        </div>
        <p className="max-w-md text-xs leading-5 text-[#666]">
          Logs stay here so the overview remains focused on the next decision.
        </p>
      </div>
      <CompactActivityCenter business={business} executionStatus={executionStatus} />
    </div>
  );
}
