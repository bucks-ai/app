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
      className="inline-flex items-center justify-center rounded-md border border-[#4F46E5]/35 bg-[#4F46E5]/10 px-4 py-2.5 text-sm font-semibold text-[#A5B4FC] transition-colors hover:border-[#4F46E5]/65 hover:text-[#E0E7FF] disabled:cursor-not-allowed disabled:opacity-55"
    >
      {loading ? "Refreshing..." : label}
    </button>
  );
}
