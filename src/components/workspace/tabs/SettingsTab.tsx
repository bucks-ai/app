import type { DashboardBusiness } from "@/components/dashboard/mock-data";
import { SandboxStatusPanel } from "@/components/workspace/SandboxStatusPanel";

type SettingsTabProps = {
  business: DashboardBusiness;
};

const AUTONOMY_BOUNDARIES = [
  {
    id: "no_deploy_without_approval",
    label: "No deployment without founder approval",
    description:
      "bucks.ai cannot push to production or create live deployments without explicit founder sign-off.",
    enforced: true,
  },
  {
    id: "no_external_spend",
    label: "No external spend without approval",
    description:
      "Purchases, subscriptions, or paid tool provisioning require founder approval.",
    enforced: true,
  },
  {
    id: "no_repo_delete",
    label: "Repositories cannot be deleted autonomously",
    description:
      "Source repositories are protected. Deletion requires manual founder action.",
    enforced: true,
  },
  {
    id: "no_credential_exposure",
    label: "Credentials are never logged or exposed",
    description:
      "API keys, tokens, and secrets are never printed in activity logs or surfaced in the UI.",
    enforced: true,
  },
];

export function SettingsTab({ business }: SettingsTabProps) {
  return (
    <div className="space-y-5">
      {/* Business info */}
      <div className="rounded-lg border border-border bg-surface p-4">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
          Business
        </p>
        <div className="mt-3 grid gap-3 sm:grid-cols-2">
          <div>
            <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
              Name
            </p>
            <p className="mt-1 text-sm text-secondary">{business.name}</p>
          </div>
          <div>
            <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
              Type
            </p>
            <p className="mt-1 text-sm text-secondary">{business.businessType}</p>
          </div>
          <div>
            <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
              Goal
            </p>
            <p className="mt-1 text-sm text-secondary">{business.goal}</p>
          </div>
          <div>
            <p className="font-mono text-[10px] uppercase tracking-widest text-muted">
              Created
            </p>
            <p className="mt-1 text-sm text-secondary">{business.created}</p>
          </div>
        </div>
      </div>

      {/* Autonomy boundaries */}
      <div className="rounded-lg border border-border bg-surface p-4">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
          Safety boundaries
        </p>
        <p className="mt-2 text-xs text-muted">
          These constraints are enforced by bucks.ai and cannot be overridden by
          AI execution.
        </p>
        <div className="mt-4 space-y-2">
          {AUTONOMY_BOUNDARIES.map((rule) => (
            <div
              key={rule.id}
              className="flex items-start gap-3 rounded border border-border bg-background px-3 py-3"
            >
              <div className="mt-0.5 flex h-4 w-4 shrink-0 items-center justify-center rounded-full bg-success/20">
                <div className="h-1.5 w-1.5 rounded-full bg-success" />
              </div>
              <div>
                <p className="text-xs font-medium text-secondary">{rule.label}</p>
                <p className="mt-0.5 text-xs leading-5 text-muted">
                  {rule.description}
                </p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Sandbox configuration */}
      <SandboxStatusPanel businessId={business.id} />
    </div>
  );
}
