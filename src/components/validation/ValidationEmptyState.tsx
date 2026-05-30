type ValidationEmptyStateProps = {
  onSeed: () => void;
  loading?: boolean;
  error?: string | null;
};

export function ValidationEmptyState({
  onSeed,
  loading = false,
  error,
}: ValidationEmptyStateProps) {
  return (
    <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-5 sm:p-6">
      <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
        Customer validation
      </p>
      <h2 className="mt-3 text-xl font-semibold text-[#F0F0F0]">
        Create the validation workspace
      </h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-[#888]">
        Seed founder-ready personas, testable hypotheses, and starter lead targets from the saved blueprint.
      </p>
      <button
        type="button"
        onClick={onSeed}
        disabled={loading}
        className="mt-4 inline-flex max-w-full items-center justify-center rounded-md border border-[#4F46E5]/45 bg-[#4F46E5]/15 px-4 py-2.5 text-sm font-semibold text-[#C7D2FE] transition-colors hover:border-[#4F46E5]/70 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "Creating..." : "Create validation workspace"}
      </button>
      {error ? (
        <p className="mt-3 rounded border border-[#EF4444]/30 bg-[#EF4444]/10 px-3 py-2 text-sm leading-6 text-[#FECACA]">
          {error}
        </p>
      ) : null}
    </div>
  );
}
