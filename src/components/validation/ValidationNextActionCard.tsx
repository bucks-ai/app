import type { ValidationWorkspace } from "@/types/validation-ui";

type ValidationNextActionCardProps = {
  workspace: ValidationWorkspace | null;
  compact?: boolean;
  onCreateWorkspace?: () => void;
  onFocusLeads?: () => void;
  onFocusFeedback?: () => void;
  loading?: boolean;
};

export function resolveValidationNextAction(workspace: ValidationWorkspace | null) {
  if (!workspace) {
    return {
      title: "Create validation workspace",
      description: "Seed personas, hypotheses, and the first lead targets.",
      cta: "Create workspace",
    };
  }

  if (workspace.summary.leadCount === 0) {
    return {
      title: "Add first 5 leads",
      description: "Capture real customer names before sending outreach.",
      cta: "Add lead",
    };
  }

  if (workspace.summary.feedbackNoteCount === 0) {
    return {
      title: "Record first interview feedback",
      description: "Turn the first customer conversation into evidence.",
      cta: "Add feedback",
    };
  }

  if (
    workspace.hypotheses.length > 0 &&
    workspace.hypotheses.every((hypothesis) => hypothesis.status === "untested")
  ) {
    return {
      title: "Start testing highest-priority hypothesis",
      description: "Move one belief into testing so feedback has a target.",
      cta: "Review hypotheses",
    };
  }

  return {
    title: "Review validation signal",
    description: "Compare feedback against hypotheses and decide the next validation move.",
    cta: "Review signal",
  };
}

export function ValidationNextActionCard({
  workspace,
  compact = false,
  onCreateWorkspace,
  onFocusLeads,
  onFocusFeedback,
  loading = false,
}: ValidationNextActionCardProps) {
  const action = resolveValidationNextAction(workspace);
  const handleClick =
    !workspace && onCreateWorkspace
      ? onCreateWorkspace
      : workspace?.summary.leadCount === 0 && onFocusLeads
        ? onFocusLeads
        : onFocusFeedback;

  return (
    <div
      className={`rounded-lg border border-[#F59E0B]/25 bg-[#F59E0B]/8 ${
        compact ? "p-3" : "p-4"
      }`}
    >
      <p className="font-mono text-[10px] uppercase tracking-[0.22em] text-[#FCD34D]">
        Next validation action
      </p>
      <p className="mt-2 text-sm font-semibold text-[#F0F0F0]">{action.title}</p>
      <p className="mt-1 text-xs leading-5 text-[#FDE68A]">{action.description}</p>
      {handleClick ? (
        <button
          type="button"
          onClick={handleClick}
          disabled={loading}
          className="mt-3 inline-flex max-w-full items-center justify-center rounded-md border border-[#F59E0B]/35 bg-[#080808] px-3 py-2 text-xs font-semibold text-[#FCD34D] transition-colors hover:border-[#F59E0B]/60 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {loading ? "Working..." : action.cta}
        </button>
      ) : null}
    </div>
  );
}
