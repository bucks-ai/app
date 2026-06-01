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
    <div className="rounded-lg border border-border bg-surface p-5 sm:p-6">
      <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
        Customer validation
      </p>
      <h2 className="mt-3 text-xl font-semibold text-foreground">
        Create the validation workspace
      </h2>
      <p className="mt-2 max-w-2xl text-sm leading-6 text-secondary">
        Seed founder-ready personas, testable hypotheses, and starter lead targets from the saved blueprint.
      </p>
      <button
        type="button"
        onClick={onSeed}
        disabled={loading}
        className="mt-4 inline-flex max-w-full items-center justify-center rounded-md border border-accent/45 bg-accent/15 px-4 py-2.5 text-sm font-semibold text-accent transition-colors hover:border-accent/70 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {loading ? "Creating..." : "Create validation workspace"}
      </button>
      {error ? (
        <p className="mt-3 rounded border border-error/30 bg-error/10 px-3 py-2 text-sm leading-6 text-error">
          {error}
        </p>
      ) : null}
    </div>
  );
}
