import { StatusPill } from "@/components/ui/StatusPill";
import type { VercelProjectResult as VercelProjectResultData } from "@/types/vercel-ui";

type VercelProjectResultProps = {
  result: VercelProjectResultData;
  warning?: string | null;
  description?: string;
};

export function VercelProjectResult({
  result,
  warning,
  description = "The Vercel project is recorded for this business. No custom domain, payments, emails, or production customer data were created.",
}: VercelProjectResultProps) {
  return (
    <div className="rounded-md border border-[#22C55E]/25 bg-[#22C55E]/10 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <StatusPill label="Vercel project created" variant="success" />
          <h3 className="mt-3 text-lg font-semibold text-[#F0F0F0]">
            {result.projectName}
          </h3>
        </div>
        {result.repoFullName ? (
          <StatusPill label={result.repoFullName} variant="neutral" />
        ) : null}
      </div>
      <p className="mt-3 text-sm leading-6 text-[#D4D4D4]">{description}</p>
      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        <a
          href={result.dashboardUrl}
          target="_blank"
          rel="noreferrer"
          className="inline-flex max-w-full break-all rounded-md border border-[#22C55E]/30 bg-[#080808] px-3 py-2 text-sm font-semibold text-[#86EFAC] transition-colors hover:border-[#22C55E]/60 hover:text-[#BBF7D0]"
        >
          Open Vercel dashboard
        </a>
        {result.deploymentUrl ? (
          <a
            href={result.deploymentUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex max-w-full break-all rounded-md border border-[#1C1C1C] bg-[#080808] px-3 py-2 text-sm font-semibold text-[#D4D4D4] transition-colors hover:border-[#4F46E5]/60 hover:text-[#F0F0F0]"
          >
            Open deployment URL
          </a>
        ) : null}
      </div>
      {warning ? (
        <p className="mt-4 rounded-md border border-[#F59E0B]/30 bg-[#F59E0B]/10 p-3 text-sm leading-6 text-[#FDE68A]">
          {warning}
        </p>
      ) : null}
    </div>
  );
}
