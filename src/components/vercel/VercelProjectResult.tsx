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
    <div className="rounded-md border border-success/25 bg-success/10 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <StatusPill label="Vercel project created" variant="success" />
          <h3 className="mt-3 text-lg font-semibold text-foreground">
            {result.projectName}
          </h3>
        </div>
        {result.repoFullName ? (
          <StatusPill label={result.repoFullName} variant="neutral" />
        ) : null}
      </div>
      <p className="mt-3 text-sm leading-6 text-secondary">{description}</p>
      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:flex-wrap">
        <a
          href={result.dashboardUrl}
          target="_blank"
          rel="noreferrer"
          className="inline-flex max-w-full break-all rounded-md border border-success/30 bg-background px-3 py-2 text-sm font-semibold text-success transition-colors hover:border-success/60 hover:text-success"
        >
          Open Vercel dashboard
        </a>
        {result.deploymentUrl ? (
          <a
            href={result.deploymentUrl}
            target="_blank"
            rel="noreferrer"
            className="inline-flex max-w-full break-all rounded-md border border-border bg-background px-3 py-2 text-sm font-semibold text-secondary transition-colors hover:border-accent/60 hover:text-foreground"
          >
            Open deployment URL
          </a>
        ) : null}
      </div>
      {warning ? (
        <p className="mt-4 rounded-md border border-warning/30 bg-warning/10 p-3 text-sm leading-6 text-warning">
          {warning}
        </p>
      ) : null}
    </div>
  );
}
