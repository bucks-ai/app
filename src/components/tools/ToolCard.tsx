import type { RiskLevel, SetupStatus, ToolRegistryItem, ToolStatus } from "@/types/tools";
import { ToolStatusBadge } from "@/components/tools/ToolStatusBadge";

function getStatusVariant(status: ToolStatus) {
  switch (status) {
    case "Preferred":
      return "preferred" as const;
    case "Approved":
      return "approved" as const;
    case "External Approval Required":
      return "external" as const;
    case "Blocked":
      return "blocked" as const;
    case "Human Only":
      return "human" as const;
  }
}

function getRiskVariant(riskLevel: RiskLevel) {
  switch (riskLevel) {
    case "Low":
      return "low" as const;
    case "Medium":
      return "medium" as const;
    case "High":
      return "high" as const;
    case "Critical":
      return "critical" as const;
  }
}

function getSetupVariant(setupStatus: SetupStatus) {
  switch (setupStatus) {
    case "Fully Completed":
      return "success" as const;
    case "Awaiting Human Legal Step":
      return "warning" as const;
    case "Requires Identity Or Payment Step":
      return "warning" as const;
    case "Blocked By Verification":
      return "danger" as const;
    case "Rejected By Policy":
      return "danger" as const;
    case "Not Connected":
      return "neutral" as const;
  }
}

export function ToolCard({ tool }: { tool: ToolRegistryItem }) {
  const requirementBadges = [
    tool.requiresTermsAcceptance ? "Terms" : null,
    tool.requiresIdentityVerification ? "Identity" : null,
    tool.requiresPaymentSetup ? "Payment" : null,
  ].filter(Boolean) as string[];

  return (
    <article className="flex h-full flex-col rounded-[1.75rem] border border-white/10 bg-[linear-gradient(180deg,rgba(255,255,255,0.08),rgba(255,255,255,0.03))] p-6 shadow-[0_24px_80px_rgba(0,0,0,0.3)] backdrop-blur-sm">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-emerald-400/75">
            {tool.category}
          </p>
          <h3 className="mt-2 text-xl font-semibold text-white">{tool.name}</h3>
        </div>
        <ToolStatusBadge
          label={tool.status}
          variant={getStatusVariant(tool.status)}
        />
      </div>

      <p className="mt-4 text-sm leading-6 text-neutral-300">{tool.purpose}</p>
      <p className="mt-3 text-sm leading-6 text-neutral-500">{tool.typicalUse}</p>

      <div className="mt-5 flex flex-wrap gap-2">
        <ToolStatusBadge
          label={`${tool.riskLevel} risk`}
          variant={getRiskVariant(tool.riskLevel)}
        />
        <ToolStatusBadge
          label={tool.setupStatus}
          variant={getSetupVariant(tool.setupStatus)}
        />
        <ToolStatusBadge
          label={tool.canAiSetupFully ? "AI setup ready" : "Human step required"}
          variant={tool.canAiSetupFully ? "success" : "neutral"}
        />
      </div>

      <div className="mt-6 grid gap-4 border-t border-white/8 pt-5">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-neutral-500">
            Default permissions
          </p>
          <ul className="mt-3 space-y-2">
            {tool.defaultPermissions.map((permission) => (
              <li
                key={permission}
                className="rounded-2xl border border-white/8 bg-black/25 px-3 py-2 text-sm text-neutral-300"
              >
                {permission}
              </li>
            ))}
          </ul>
        </div>

        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-neutral-500">
            Human gates
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            {requirementBadges.length > 0 ? (
              requirementBadges.map((requirement) => (
                <ToolStatusBadge
                  key={requirement}
                  label={requirement}
                  variant="warning"
                />
              ))
            ) : (
              <ToolStatusBadge label="None by default" variant="success" />
            )}
          </div>
        </div>

        {tool.humanOnlyReasons.length > 0 ? (
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-neutral-500">
              Human-only reasons
            </p>
            <ul className="mt-3 space-y-2">
              {tool.humanOnlyReasons.map((reason) => (
                <li
                  key={reason}
                  className="rounded-2xl border border-amber-500/15 bg-amber-500/8 px-3 py-2 text-sm leading-6 text-neutral-300"
                >
                  {reason}
                </li>
              ))}
            </ul>
          </div>
        ) : null}
      </div>
    </article>
  );
}
