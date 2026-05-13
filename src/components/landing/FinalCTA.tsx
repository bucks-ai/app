import Link from "next/link";

export function FinalCTA() {
  return (
    <section className="py-32" style={{ background: "#080808" }}>
      <div className="mx-auto max-w-3xl px-6 text-center">
        <div
          className="mb-6 inline-flex items-center gap-2 rounded-full border px-3 py-1.5 font-mono text-xs"
          style={{
            borderColor: "#1C1C1C",
            background: "#0F0F0F",
            color: "#888888",
          }}
        >
          <div
            className="h-1.5 w-1.5 rounded-full"
            style={{ background: "#4F46E5" }}
          />
          Ready to operate
        </div>

        <h2
          className="mb-6 text-4xl font-semibold leading-tight tracking-tight lg:text-5xl"
          style={{ color: "#F0F0F0" }}
        >
          Your company doesn&apos;t need you
          <br />
          to manage it.
        </h2>

        <p
          className="mx-auto mb-12 max-w-lg text-lg leading-relaxed"
          style={{ color: "#888888" }}
        >
          Submit your idea. Set your budget. Define your limits. bucks.ai
          handles the rest — and escalates only when it has to.
        </p>

        <div className="flex flex-col items-center justify-center gap-4 sm:flex-row">
          <Link
            href="/intake"
            className="inline-flex items-center gap-2 rounded-lg px-8 py-3.5 text-sm font-medium transition-opacity hover:opacity-90"
            style={{ background: "#4F46E5", color: "#F0F0F0" }}
          >
            Submit your idea
            <span className="opacity-70">&#8594;</span>
          </Link>
          <Link
            href="/tools"
            className="inline-flex items-center gap-2 rounded-lg border px-8 py-3.5 text-sm font-medium text-[#888888] transition-colors hover:text-[#F0F0F0]"
            style={{
              borderColor: "#1C1C1C",
              background: "#0F0F0F",
            }}
          >
            View the tool layer
          </Link>
        </div>
      </div>
    </section>
  );
}
