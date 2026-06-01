import type { GitHubRepoResult as GitHubRepoResultData } from "@/types/github-ui";
import { StatusPill } from "@/components/ui/StatusPill";

type GitHubRepoResultProps = {
  result: GitHubRepoResultData;
  label?: string;
  description?: string;
  warning?: string | null;
};

export function GitHubRepoResult({
  result,
  label = "GitHub repo created",
  description = "The repository now exists in GitHub. No deployment or production app code generation was triggered.",
  warning,
}: GitHubRepoResultProps) {
  return (
    <div className="rounded-md border border-success/25 bg-success/10 p-4">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <StatusPill label={label} variant="success" />
          <h3 className="mt-3 text-lg font-semibold text-foreground">
            {result.fullName}
          </h3>
        </div>
        <StatusPill label={result.private ? "Private" : "Public"} variant="neutral" />
      </div>
      <p className="mt-3 text-sm leading-6 text-secondary">{description}</p>
      <a
        href={result.repoUrl}
        target="_blank"
        rel="noreferrer"
        className="mt-4 inline-flex max-w-full break-all rounded-md border border-success/30 bg-background px-3 py-2 text-sm font-semibold text-success transition-colors hover:border-success/60 hover:text-success"
      >
        {result.repoUrl}
      </a>
      {warning ? (
        <p className="mt-4 rounded-md border border-warning/30 bg-warning/10 p-3 text-sm leading-6 text-warning">
          {warning}
        </p>
      ) : null}
    </div>
  );
}
