import type { ResearchWorkspace } from "@/types/research-ui";

type ResearchNextActionCardProps = {
  workspace: ResearchWorkspace | null;
  compact?: boolean;
  onCreateWorkspace?: () => void;
  onFocusRisks?: () => void;
  onFocusHypotheses?: () => void;
  onFocusCompetitors?: () => void;
  loading?: boolean;
};

export function resolveResearchNextAction(workspace: ResearchWorkspace | null) {
  if (!workspace) {
    return {
      title: "Generate research workspace",
      description: "Seed the opportunity thesis, market map, risks, and hypotheses.",
      cta: "Generate research workspace",
    };
  }

  if (workspace.summary.opportunityScore === null) {
    return {
      title: "Review opportunity score",
      description: "Score the opportunity before committing build energy.",
      cta: "Review score",
    };
  }

  const highPriorityRisk = workspace.risks.find(
    (risk) =>
      risk.priority === "high" ||
      risk.severity === "critical" ||
      risk.severity === "high"
  );
  if (highPriorityRisk) {
    return {
      title: "Validate highest-risk assumption",
      description: highPriorityRisk.title,
      cta: "Review risks",
    };
  }

  if (workspace.hypotheses.length > 0) {
    return {
      title: "Move research hypotheses into validation",
      description: "Promote the riskiest beliefs into customer validation tests.",
      cta: "Review hypotheses",
    };
  }

  if (workspace.competitors.length === 0) {
    return {
      title: "Add competitor examples",
      description: "Anchor the wedge against direct alternatives and status quo behavior.",
      cta: "Review competitors",
    };
  }

  return {
    title: "Review research and proceed to validation",
    description: "Use the strongest segment, budget signal, and risk map to set up validation.",
    cta: "Review research",
  };
}

export function ResearchNextActionCard({
  workspace,
  compact = false,
  onCreateWorkspace,
  onFocusRisks,
  onFocusHypotheses,
  onFocusCompetitors,
  loading = false,
}: ResearchNextActionCardProps) {
  const action = resolveResearchNextAction(workspace);
  const hasHighPriorityRisk = Boolean(
    workspace?.risks.find(
      (risk) =>
        risk.priority === "high" ||
        risk.severity === "critical" ||
        risk.severity === "high"
    )
  );
  const handleClick =
    !workspace && onCreateWorkspace
      ? onCreateWorkspace
      : hasHighPriorityRisk && onFocusRisks
        ? onFocusRisks
        : workspace && workspace.hypotheses.length > 0 && onFocusHypotheses
          ? onFocusHypotheses
          : workspace && workspace.competitors.length === 0 && onFocusCompetitors
            ? onFocusCompetitors
            : undefined;

  return (
    <div
      className={`rounded-lg border border-warning/25 bg-warning/8 ${
        compact ? "p-3" : "p-4"
      }`}
    >
      <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-warning">
        Next research action
      </p>
      <p className="mt-2 text-sm font-semibold text-foreground">{action.title}</p>
      <p className="mt-1 break-words text-xs leading-5 text-warning">
        {action.description}
      </p>
      {handleClick ? (
        <button
          type="button"
          onClick={handleClick}
          disabled={loading}
          className="mt-3 inline-flex max-w-full items-center justify-center whitespace-normal rounded-md border border-warning/35 bg-background px-3 py-2 text-xs font-semibold text-warning transition-colors hover:border-warning/60 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "Working..." : action.cta}
        </button>
      ) : null}
    </div>
  );
}
