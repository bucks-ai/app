import Link from "next/link";

export function Navbar() {
  return (
    <nav
      className="fixed left-0 right-0 top-0 z-50 border-b backdrop-blur-md"
      style={{
        borderColor: "#1C1C1C",
        background: "rgba(8,8,8,0.85)",
      }}
    >
      <div className="mx-auto flex max-w-6xl items-center justify-between gap-4 px-5 py-4 sm:px-6">
        <Link
          href="/"
          className="text-lg font-semibold tracking-tight"
          style={{ color: "#F0F0F0" }}
        >
          bucks<span style={{ color: "#4F46E5" }}>.ai</span>
        </Link>
        <div className="flex items-center gap-3 sm:gap-5">
          <Link
            href="/dashboard"
            className="hidden text-sm text-[#888888] transition-colors hover:text-[#F0F0F0] md:inline"
          >
            Dashboard
          </Link>
          <Link
            href="/tools"
            className="text-sm text-[#888888] transition-colors hover:text-[#F0F0F0]"
          >
            Tools
          </Link>
          <Link
            href="/#execution-model"
            className="hidden text-sm text-[#888888] transition-colors hover:text-[#F0F0F0] sm:inline"
          >
            How it works
          </Link>
          <Link
            href="/login"
            className="text-sm text-[#888888] transition-colors hover:text-[#F0F0F0]"
          >
            Sign in
          </Link>
          <Link
            href="/intake"
            className="rounded-md px-3 py-2 text-sm font-medium transition-colors hover:bg-[#6366F1] sm:px-4"
            style={{ background: "#4F46E5", color: "#F0F0F0" }}
          >
            <span className="hidden sm:inline">Start your company</span>
            <span className="sm:hidden">Start</span>
          </Link>
        </div>
      </div>
    </nav>
  );
}
