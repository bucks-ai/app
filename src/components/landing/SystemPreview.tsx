import { BentoGrid } from "@/components/ui/BentoGrid";
import { GlassCard } from "@/components/ui/GlassCard";
import { Reveal } from "@/components/ui/Reveal";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { StatusChip } from "@/components/ui/StatusChip";

const parts = [
  {
    name: "Strategy",
    body: "Goals, scope, and the blueprint that guides every run.",
    reveal: "Founder goals stay visible as constraints for every agent.",
    status: "done" as const,
    className: "md:col-span-3 lg:col-span-2",
  },
  {
    name: "Research",
    body: "Market, competitor, and customer signal gathered up front.",
    reveal: "Segments, budgets, evidence, and risks become workspace data.",
    status: "done" as const,
    className: "md:col-span-3 lg:col-span-2",
  },
  {
    name: "Deployment",
    body: "GitHub repo and Vercel deploy wired and shipped.",
    reveal: "Repo, scaffold, deploy status, and live links stay connected.",
    status: "running" as const,
    className: "md:col-span-6 lg:col-span-2",
  },
  {
    name: "Validation",
    body: "Persona interviews and tests that confirm demand.",
    reveal: "The system turns assumptions into interview scripts and leads.",
    status: "queued" as const,
    className: "md:col-span-3",
  },
  {
    name: "Safety",
    body: "Tool permissions and limits that keep agents in bounds.",
    reveal: "Human approval gates stay explicit before side effects happen.",
    status: "pending" as const,
    className: "md:col-span-3",
  },
  {
    name: "Orchestration",
    body: "Agent runs coordinated toward the next action.",
    reveal:
      "Every working part reports into the same loop so the founder always sees the next move.",
    status: "running" as const,
    className: "md:col-span-6",
  },
];

export function SystemPreview() {
  return (
    <section className="relative overflow-hidden border-y border-border-subtle bg-surface px-6 py-20 sm:py-28">
      <div aria-hidden className="grid-backdrop pointer-events-none absolute inset-0 opacity-50" />
      <div
        aria-hidden
        className="pointer-events-none absolute inset-x-0 top-0 h-80"
        style={{ background: "var(--glow)" }}
      />
      <div className="relative mx-auto max-w-6xl">
        <Reveal>
          <SectionHeader
            eyebrow="The system"
            title="Six working parts, one operating loop"
            description="Each module owns a slice of the work and hands off cleanly to the next action engine."
          />
        </Reveal>

        <BentoGrid className="mt-14 lg:grid-cols-6">
          {parts.map((part, index) => (
            <Reveal key={part.name} delay={index * 70} className={part.className}>
              <GlassCard
                interactive
                delay={index * 0.04}
                className="group h-full p-5"
              >
                <div className="flex items-start justify-between gap-4">
                  <div>
                    <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
                      0{index + 1}
                    </p>
                    <h3 className="mt-3 text-xl font-semibold tracking-tight text-foreground">
                      {part.name}
                    </h3>
                  </div>
                  <StatusChip status={part.status} />
                </div>
                <p className="mt-4 text-sm leading-6 text-secondary">{part.body}</p>
                <div className="mt-5 translate-y-1 border-t border-border/70 pt-4 opacity-70 transition-all duration-200 group-hover:translate-y-0 group-hover:opacity-100">
                  <p className="text-sm leading-6 text-foreground">{part.reveal}</p>
                </div>
              </GlassCard>
            </Reveal>
          ))}
        </BentoGrid>
      </div>
    </section>
  );
}
