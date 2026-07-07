import Link from "next/link";
import { Reveal } from "@/components/ui/Reveal";
import { GlassCard } from "@/components/ui/GlassCard";

export function ClosingCTA() {
  return (
    <section className="px-6 pb-24 pt-8 sm:pb-32">
      {/* the rail hands the page off into the CTA */}
      <div aria-hidden className="mx-auto mb-8 h-14 w-px flow-line-y" />

      <Reveal>
        <GlassCard
          className="mx-auto max-w-4xl px-6 py-16 text-center sm:px-12"
          innerClassName="relative"
        >
          <div>
            <h2 className="text-balance text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
              Start with your idea
            </h2>
            <p className="text-balance mx-auto mt-4 max-w-md text-base leading-relaxed text-secondary">
              Hand bucks.ai a sentence and a budget. Get back research, a
              blueprint, a live deploy, and a team of agents.
            </p>
            <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Link
                href="/intake"
                className="inline-flex min-h-12 w-full cursor-pointer items-center justify-center gap-2 rounded-lg bg-accent px-6 py-3 text-sm font-semibold text-accent-contrast shadow-soft transition-colors duration-200 hover:bg-accent-hover sm:w-auto"
              >
                Start building
                <span aria-hidden className="opacity-80">
                  &#8594;
                </span>
              </Link>
              <Link
                href="/dashboard"
                className="inline-flex min-h-12 w-full cursor-pointer items-center justify-center rounded-lg border border-border bg-background/70 px-6 py-3 text-sm font-medium text-secondary transition-colors duration-200 hover:border-border-strong hover:text-foreground sm:w-auto"
              >
                Open dashboard
              </Link>
            </div>
          </div>
        </GlassCard>
      </Reveal>
    </section>
  );
}
