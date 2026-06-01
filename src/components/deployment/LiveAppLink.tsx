type LiveAppLinkProps = {
  href?: string | null;
  label?: string;
  className?: string;
};

export function LiveAppLink({
  href,
  label = "Open live app",
  className = "",
}: LiveAppLinkProps) {
  if (!href) {
    return (
      <span
        className={`inline-flex items-center justify-center rounded-md border border-border bg-background px-4 py-2.5 text-sm font-semibold text-muted ${className}`}
      >
        Live URL pending
      </span>
    );
  }

  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className={`inline-flex items-center justify-center rounded-md border border-success/30 bg-success/12 px-4 py-2.5 text-sm font-semibold text-success transition-colors hover:border-success/60 hover:text-success ${className}`}
    >
      {label}
    </a>
  );
}
