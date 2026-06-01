type DeploymentRefreshButtonProps = {
  loading?: boolean;
  disabled?: boolean;
  label?: string;
  onRefresh: () => void;
};

export function DeploymentRefreshButton({
  loading = false,
  disabled = false,
  label = "Refresh status",
  onRefresh,
}: DeploymentRefreshButtonProps) {
  return (
    <button
      type="button"
      onClick={onRefresh}
      disabled={loading || disabled}
      className="inline-flex items-center justify-center rounded-md border border-accent/35 bg-accent/10 px-4 py-2.5 text-sm font-semibold text-accent transition-colors hover:border-accent/65 hover:text-accent disabled:cursor-not-allowed disabled:opacity-55"
    >
      {loading ? "Refreshing..." : label}
    </button>
  );
}
