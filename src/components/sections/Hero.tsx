import Link from "next/link";

export function Hero() {
  return (
    <section className="relative flex min-h-screen flex-col items-center justify-center overflow-hidden bg-black px-6 pt-20 text-center">
      {/* Subtle radial glow */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          background:
            "radial-gradient(ellipse 80% 50% at 50% -10%, rgba(16,185,129,0.15) 0%, transparent 70%)",
        }}
      />

      <div className="relative z-10 mx-auto max-w-4xl">
        {/* Badge */}
        <div className="mb-6 inline-flex items-center gap-2 rounded-full border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5 text-xs font-medium text-emerald-400">
          <span className="h-1.5 w-1.5 rounded-full bg-emerald-400" />
          Now accepting early-access founders
        </div>

        {/* Headline */}
        <h1 className="mb-6 text-5xl font-extrabold leading-tight tracking-tight text-white sm:text-6xl lg:text-7xl">
          The self-driving startup operator
          <br />
          <span className="text-emerald-400">for AI software businesses.</span>
        </h1>

        {/* Subheadline */}
        <p className="mx-auto mb-10 max-w-2xl text-lg text-neutral-400 sm:text-xl">
          Give bucks.ai an idea, goal, budget, and boundaries. It turns it into
          a launched MVP and first-customer pipeline — without you managing
          every step.
        </p>

        {/* CTAs */}
        <div className="flex flex-col items-center gap-4 sm:flex-row sm:justify-center">
          <Link
            href="/intake"
            className="rounded-full bg-emerald-500 px-8 py-3.5 text-base font-semibold text-black transition-colors hover:bg-emerald-400"
          >
            Launch your blueprint
          </Link>
          <a
            href="#how-it-works"
            className="rounded-full border border-white/20 px-8 py-3.5 text-base font-medium text-white transition-colors hover:border-white/40 hover:bg-white/5"
          >
            See how it works
          </a>
        </div>
      </div>

      {/* Bottom fade */}
      <div className="pointer-events-none absolute bottom-0 left-0 right-0 h-32 bg-gradient-to-t from-black to-transparent" />
    </section>
  );
}
