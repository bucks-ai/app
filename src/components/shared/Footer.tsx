import Link from "next/link";

export function Footer() {
  return (
    <footer
      className="border-t px-6 py-10"
      style={{ borderColor: "#1C1C1C", background: "#080808" }}
    >
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 sm:flex-row">
        <Link
          href="/"
          className="text-sm font-semibold"
          style={{ color: "#F0F0F0" }}
        >
          bucks<span style={{ color: "#4F46E5" }}>.ai</span>
        </Link>
        <div className="flex items-center gap-6">
          <Link
            href="/intake"
            className="text-xs text-[#888888] transition-colors hover:text-[#F0F0F0]"
          >
            Start intake
          </Link>
          <Link
            href="/tools"
            className="text-xs text-[#888888] transition-colors hover:text-[#F0F0F0]"
          >
            Tool registry
          </Link>
        </div>
        <span className="text-xs" style={{ color: "#888888" }}>
          © {new Date().getFullYear()} bucks.ai
        </span>
      </div>
    </footer>
  );
}
