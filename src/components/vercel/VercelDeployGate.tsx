import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";

type VercelDeployGateProps = {
  title: string;
  description: string;
  actionLabel?: string;
  actionHref?: string;
};

export function VercelDeployGate({
  title,
  description,
  actionLabel,
  actionHref,
}: VercelDeployGateProps) {
  return (
    <div className="rounded-lg border border-warning/30 bg-warning/10 p-5">
      <div className="flex flex-wrap items-center gap-3">
        <SectionLabel tone="warning">Deployment gate</SectionLabel>
        <StatusPill label="Founder approval" variant="warning" />
      </div>
      <h3 className="mt-4 text-2xl font-semibold tracking-tight text-foreground">
        {title}
      </h3>
      <p className="mt-3 text-sm leading-7 text-warning">{description}</p>
      <p className="mt-3 text-sm leading-7 text-secondary">
        Vercel deployment is approval-gated because it creates a real external
        project using a server-side Vercel token.
      </p>
      {actionLabel && actionHref ? (
        <a
          href={actionHref}
          className="mt-5 inline-flex rounded-md border border-warning/40 bg-background px-4 py-3 text-sm font-semibold text-warning transition-colors hover:border-warning/70 hover:text-warning"
        >
          {actionLabel}
        </a>
      ) : null}
    </div>
  );
}
