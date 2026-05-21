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
        className={`inline-flex items-center justify-center rounded-md border border-[#1C1C1C] bg-[#080808] px-4 py-2.5 text-sm font-semibold text-[#555] ${className}`}
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
      className={`inline-flex items-center justify-center rounded-md border border-[#22C55E]/30 bg-[#22C55E]/12 px-4 py-2.5 text-sm font-semibold text-[#86EFAC] transition-colors hover:border-[#22C55E]/60 hover:text-[#DCFCE7] ${className}`}
    >
      {label}
    </a>
  );
}
