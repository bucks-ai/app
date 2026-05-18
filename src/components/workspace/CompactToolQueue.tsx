"use client";

import { useMemo, useState } from "react";
import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import { toolRegistry } from "@/lib/tool-registry";

type CompactToolQueueProps = {
  business: DashboardBusiness;
  maxRows?: number;
  full?: boolean;
  onOpenTools?: () => void;
};

type ToolRow = {
  id: string;
  name: string;
  status: string;
  risk: "low" | "medium" | "high" | "critical";
  purpose: string;
  cta: string;
};

const statusPriority: Record<string, number> = {
  blocked: 0,
  rejected: 1,
  human_required: 2,
  approval_requested: 3,
  not_connected: 4,
  approved_by_founder: 5,
  approved: 6,
  connected_demo: 7,
};

function normalizeRisk(value?: string): ToolRow["risk"] {
  if (value === "low" || value === "medium" || value === "high" || value === "critical") {
    return value;
  }
  return "medium";
}

function statusLabel(status: string) {
  return status
    .split("_")
    .filter(Boolean)
    .map((word) => word.charAt(0).toUpperCase() + word.slice(1))
    .join(" ");
}

function statusTone(status: string) {
  if (status === "blocked" || status === "rejected") {
    return "border-[#EF4444]/30 bg-[#EF4444]/10 text-[#FCA5A5]";
  }
  if (status === "human_required" || status === "approval_requested") {
    return "border-[#F59E0B]/30 bg-[#F59E0B]/10 text-[#FCD34D]";
  }
  if (status === "approved" || status === "approved_by_founder" || status === "connected_demo") {
    return "border-[#22C55E]/25 bg-[#22C55E]/10 text-[#86EFAC]";
  }
  return "border-[#1C1C1C] bg-[#141414] text-[#888]";
}

function riskTone(risk: ToolRow["risk"]) {
  if (risk === "critical") return "border-[#EF4444]/30 bg-[#EF4444]/10 text-[#FCA5A5]";
  if (risk === "high" || risk === "medium") return "border-[#F59E0B]/25 bg-[#F59E0B]/10 text-[#FCD34D]";
  return "border-[#22C55E]/25 bg-[#22C55E]/10 text-[#86EFAC]";
}

function buildRows(business: DashboardBusiness): ToolRow[] {
  if (business.toolPermissions && business.toolPermissions.length > 0) {
    return business.toolPermissions.map((permission) => {
      const registryTool = toolRegistry.find((tool) => tool.id === permission.toolId);
      const status = permission.setupStatus ?? permission.status;

      return {
        id: permission.toolId,
        name: registryTool?.name ?? permission.toolId,
        status,
        risk: normalizeRisk(registryTool?.riskLevel?.toLowerCase()),
        purpose: registryTool?.purpose ?? "External tool access requested for this business.",
        cta:
          status === "approved" ||
          status === "approved_by_founder" ||
          status === "connected_demo"
            ? "Ready"
            : status === "blocked" || status === "rejected"
              ? "Resolve"
              : "Review",
      };
    });
  }

  return business.permissions.map((permission) => ({
    id: permission.tool,
    name: permission.tool,
    status: permission.access.toLowerCase().replace(/[^a-z0-9]+/g, "_"),
    risk: permission.tone === "danger" ? "critical" : permission.tone === "warning" ? "high" : "medium",
    purpose: permission.note,
    cta: permission.tone === "warning" || permission.tone === "danger" ? "Review" : "View",
  }));
}

export function CompactToolQueue({
  business,
  maxRows = 4,
  full = false,
  onOpenTools,
}: CompactToolQueueProps) {
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const rows = useMemo(
    () =>
      buildRows(business).sort(
        (a, b) => (statusPriority[a.status] ?? 9) - (statusPriority[b.status] ?? 9)
      ),
    [business]
  );
  const visible = full ? rows : rows.slice(0, maxRows);

  if (rows.length === 0) {
    return (
      <div className="rounded border border-[#1C1C1C] bg-[#080808] px-3 py-3">
        <p className="text-xs leading-5 text-[#666]">
          No tool approvals have been queued yet.
        </p>
        {onOpenTools ? (
          <button
            type="button"
            onClick={onOpenTools}
            className="mt-2 font-mono text-[10px] uppercase tracking-widest text-[#A5B4FC]"
          >
            Open tools
          </button>
        ) : null}
      </div>
    );
  }

  return (
    <div className="space-y-1.5">
      {visible.map((row) => {
        const expanded = expandedId === row.id;

        return (
          <div key={row.id} className="rounded border border-[#1C1C1C] bg-[#080808]">
            <button
              type="button"
              onClick={() => setExpandedId(expanded ? null : row.id)}
              className="flex w-full items-center gap-2 px-3 py-2 text-left"
            >
              <div className="min-w-0 flex-1">
                <div className="flex flex-wrap items-center gap-1.5">
                  <p className="truncate text-xs font-semibold text-[#F0F0F0]">
                    {row.name}
                  </p>
                  <span
                    className={`rounded border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-widest ${statusTone(row.status)}`}
                  >
                    {statusLabel(row.status)}
                  </span>
                  <span
                    className={`rounded border px-1.5 py-0.5 font-mono text-[9px] uppercase tracking-widest ${riskTone(row.risk)}`}
                  >
                    {row.risk}
                  </span>
                </div>
                <p className="mt-0.5 truncate text-xs text-[#666]">{row.purpose}</p>
              </div>
              <span className="shrink-0 rounded border border-[#1C1C1C] bg-[#141414] px-2 py-1 font-mono text-[10px] uppercase tracking-widest text-[#888]">
                {row.cta}
              </span>
            </button>
            {expanded ? (
              <div className="border-t border-[#1C1C1C] px-3 py-2 text-xs leading-5 text-[#888]">
                {row.purpose}
              </div>
            ) : null}
          </div>
        );
      })}

      {!full && rows.length > visible.length && onOpenTools ? (
        <button
          type="button"
          onClick={onOpenTools}
          className="w-full rounded border border-[#1C1C1C] bg-[#0F0F0F] px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-[#666] transition-colors hover:border-[#4F46E5]/35 hover:text-[#A5B4FC]"
        >
          View {rows.length - visible.length} more tools
        </button>
      ) : null}
    </div>
  );
}
