import Link from "next/link";

export function Navbar() {
  return (
    <nav className="fixed top-0 left-0 right-0 z-50 border-b border-white/10 bg-black/80 backdrop-blur-md">
      <div className="mx-auto flex max-w-6xl items-center justify-between px-6 py-4">
        <Link href="/" className="text-lg font-semibold tracking-tight text-white">
          bucks<span className="text-emerald-400">.ai</span>
        </Link>
        <div className="flex items-center gap-6">
          <a
            href="#how-it-works"
            className="text-sm text-neutral-400 transition-colors hover:text-white"
          >
            How it works
          </a>
          <a
            href="#early-access"
            className="rounded-full bg-emerald-500 px-4 py-2 text-sm font-medium text-black transition-colors hover:bg-emerald-400"
          >
            Get early access
          </a>
        </div>
      </div>
    </nav>
  );
}
