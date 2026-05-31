type ResearchEmptyStateProps = {
  onGenerate: () => void;
  loading?: boolean;
  error?: string | null;
};

export function ResearchEmptyState({
  onGenerate,
  loading = false,
  error,
}: ResearchEmptyStateProps) {
  return (
    <div className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-5 sm:p-6">
      <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
        Research mode
      </p>
      <h2 className="mt-3 text-xl font-semibold text-[#F0F0F0]">
        Find where the money is
      </h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-[#888]">
        Generate a founder-ready research workspace from the saved blueprint: segments,
        buyers, competitors, monetization, channels, risks, hypotheses, and evidence.
      </p>
      <button
        type="button"
        onClick={onGenerate}
        disabled={loading}
        className="mt-4 inline-flex max-w-full items-center justify-center whitespace-normal rounded-md border border-[#4F46E5]/45 bg-[#4F46E5]/15 px-4 py-2.5 text-sm font-semibold text-[#C7D2FE] transition-colors hover:border-[#4F46E5]/70 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "Generating..." : "Generate research workspace"}
      </button>
      {error ? (
        <p className="mt-3 rounded border border-[#EF4444]/30 bg-[#EF4444]/10 px-3 py-2 text-sm leading-6 text-[#FECACA]">
          {error}
        </p>
      ) : null}
    </div>
  );
}
