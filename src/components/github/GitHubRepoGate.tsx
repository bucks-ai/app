import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";

type GitHubRepoGateProps = {
  setupQueueHref?: string;
};

export function GitHubRepoGate({
  setupQueueHref = "#tool-setup-queue",
}: GitHubRepoGateProps) {
  return (
    <div className="rounded-lg border border-warning/30 bg-warning/10 p-5">
      <div className="flex flex-wrap items-center gap-3">
        <SectionLabel tone="warning">GitHub permission required</SectionLabel>
        <StatusPill label="Founder approval" variant="warning" />
      </div>
      <h3 className="mt-4 text-2xl font-semibold tracking-tight text-foreground">
        Approve GitHub before repo creation.
      </h3>
      <p className="mt-3 text-sm leading-7 text-warning">
        This is the first real external action in the operator flow. bucks.ai
        will not create external assets without founder approval.
      </p>
      <p className="mt-3 text-sm leading-7 text-secondary">
        Approve GitHub in the Tool Setup Queue first, then return here to create
        a private repository with the server-side development token.
      </p>
      <a
        href={setupQueueHref}
        className="mt-5 inline-flex rounded-md border border-warning/40 bg-background px-4 py-3 text-sm font-semibold text-warning transition-colors hover:border-warning/70 hover:text-warning"
      >
        Go to Tool Setup Queue
      </a>
    </div>
  );
}
