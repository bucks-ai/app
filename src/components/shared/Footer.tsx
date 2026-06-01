import Link from "next/link";

export function Footer() {
  return (
    <footer className="border-t border-border bg-background px-6 py-10">
      <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-6 sm:flex-row">
        <Link href="/" className="text-sm font-semibold text-foreground">
          bucks<span className="text-accent">.ai</span>
        </Link>
        <div className="flex items-center gap-6">
          <Link
            href="/intake"
            className="text-xs text-secondary transition-colors hover:text-foreground"
          >
            Start building
          </Link>
          <Link
            href="/tools"
            className="text-xs text-secondary transition-colors hover:text-foreground"
          >
            Tool registry
          </Link>
        </div>
        <span className="text-xs text-muted">
          © {new Date().getFullYear()} bucks.ai
        </span>
      </div>
    </footer>
  );
}
