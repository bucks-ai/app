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
    <div className="rounded-lg border border-[#F59E0B]/30 bg-[#F59E0B]/10 p-5">
      <div className="flex flex-wrap items-center gap-3">
        <SectionLabel tone="warning">Deployment gate</SectionLabel>
        <StatusPill label="Founder approval" variant="warning" />
      </div>
      <h3 className="mt-4 text-2xl font-semibold tracking-tight text-[#F0F0F0]">
        {title}
      </h3>
      <p className="mt-3 text-sm leading-7 text-[#FDE68A]">{description}</p>
      <p className="mt-3 text-sm leading-7 text-[#D4D4D4]">
        Vercel deployment is approval-gated because it creates a real external
        project using a server-side Vercel token.
      </p>
      {actionLabel && actionHref ? (
        <a
          href={actionHref}
          className="mt-5 inline-flex rounded-md border border-[#F59E0B]/40 bg-[#080808] px-4 py-3 text-sm font-semibold text-[#FDE68A] transition-colors hover:border-[#F59E0B]/70 hover:text-[#FEF3C7]"
        >
          {actionLabel}
        </a>
      ) : null}
    </div>
  );
}
