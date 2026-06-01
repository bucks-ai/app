"use client";

import { useMemo, useState } from "react";
import { PermissionControlRoom } from "@/components/tools/PermissionControlRoom";
import { OperatorPanel } from "@/components/ui/OperatorPanel";
import { SectionLabel } from "@/components/ui/SectionLabel";
import type { BusinessPermissionOption } from "@/types/tool-permission-ui";

type BusinessPermissionSelectorProps = {
  businesses: BusinessPermissionOption[];
};

export function BusinessPermissionSelector({
  businesses,
}: BusinessPermissionSelectorProps) {
  const [selectedBusinessId, setSelectedBusinessId] = useState(
    businesses[0]?.id ?? ""
  );

  const selectedBusiness = useMemo(
    () => businesses.find((business) => business.id === selectedBusinessId),
    [businesses, selectedBusinessId]
  );

  if (businesses.length === 0) return null;

  return (
    <div className="space-y-6">
      <OperatorPanel className="p-5">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <SectionLabel>Saved business</SectionLabel>
            <h3 className="mt-2 text-xl font-semibold text-foreground">
              Choose a setup queue
            </h3>
            <p className="mt-2 max-w-2xl text-sm leading-6 text-secondary">
              Permission state is scoped to a saved business. Pick the project
              bucks.ai should prepare tools for.
            </p>
          </div>

          <label className="grid gap-2 text-sm text-secondary">
            <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-secondary">
              Business
            </span>
            <select
              value={selectedBusinessId}
              onChange={(event) => setSelectedBusinessId(event.target.value)}
              className="min-h-11 w-full rounded-md border border-border bg-background px-3 py-2 text-sm text-foreground outline-none transition-colors focus:border-accent lg:min-w-80"
            >
              {businesses.map((business) => (
                <option key={business.id} value={business.id}>
                  {business.name}
                </option>
              ))}
            </select>
          </label>
        </div>
      </OperatorPanel>

      <PermissionControlRoom
        businessId={selectedBusinessId}
        businessName={selectedBusiness?.name}
      />
    </div>
  );
}
