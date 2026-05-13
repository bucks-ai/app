import Link from "next/link";
import { OperatorConsoleMockup } from "./OperatorConsoleMockup";

export function CommandHero() {
  return (
    <section
      className="relative min-h-screen pt-24 pb-20"
      style={{ background: "#080808" }}
    >
      {/* Subtle grid */}
      <div
        className="pointer-events-none absolute inset-0"
        style={{
          backgroundImage:
            "linear-gradient(rgba(79,70,229,0.03) 1px, transparent 1px), linear-gradient(90deg, rgba(79,70,229,0.03) 1px, transparent 1px)",
          backgroundSize: "64px 64px",
        }}
      />

      <div className="relative mx-auto max-w-6xl px-6">
        <div className="grid items-center gap-16 lg:grid-cols-2">
          {/* Left column */}
          <div>
            <div
              className="mb-6 inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-medium"
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
              Autonomous Startup Operator
            </div>

            <h1
              className="mb-6 text-5xl font-semibold leading-tight tracking-tight lg:text-6xl"
              style={{ color: "#F0F0F0" }}
            >
              Your startup,
              <br />
              <span style={{ color: "#4F46E5" }}>operating itself.</span>
            </h1>

            <p
              className="mb-10 max-w-xl text-lg leading-relaxed"
              style={{ color: "#888888" }}
            >
              bucks.ai is an autonomous execution system for AI software
              businesses. Give it an idea, budget, and limits — it builds,
              deploys, and runs the company. You handle what only humans can.
            </p>

            <div className="flex flex-col gap-3 sm:flex-row">
              <Link
                href="/intake"
                className="inline-flex items-center justify-center gap-2 rounded-lg px-6 py-3 text-sm font-medium transition-opacity hover:opacity-90"
                style={{ background: "#4F46E5", color: "#F0F0F0" }}
              >
                Start your company
                <span className="opacity-70">&#8594;</span>
              </Link>
              <a
                href="#execution-model"
                className="inline-flex items-center justify-center gap-2 rounded-lg border px-6 py-3 text-sm font-medium text-[#888888] transition-colors hover:text-[#F0F0F0]"
                style={{
                  borderColor: "#1C1C1C",
                  background: "#0F0F0F",
                }}
              >
                See it execute
              </a>
            </div>
          </div>

          {/* Right column — console mockup */}
          <div className="lg:pl-8">
            <OperatorConsoleMockup />
          </div>
        </div>
      </div>
    </section>
  );
}
