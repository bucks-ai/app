import { Reveal } from "@/components/ui/Reveal";
import { SectionHeader } from "@/components/ui/SectionHeader";
import { GlassCard } from "@/components/ui/GlassCard";

const steps = [
  {
    n: "01",
    title: "Enter your idea",
    body: "Describe the product, your goal, budget, and any boundaries. That's the whole brief.",
  },
  {
    n: "02",
    title: "Generate research + blueprint",
    body: "bucks.ai scans the market, sizes the opportunity, and drafts a strategy you can edit.",
  },
  {
    n: "03",
    title: "Build & deploy the workspace",
    body: "It scaffolds the starter repo and ships a live deploy on GitHub and Vercel.",
  },
  {
    n: "04",
    title: "Validate with customers",
    body: "Persona interviews and agent runs pressure-test the idea and surface the next move.",
  },
];

export function WorkflowSteps() {
  return (
    <section id="how-it-works" className="px-6 py-20 sm:py-28">
      <div className="mx-auto max-w-6xl">
        <Reveal>
          <SectionHeader
            eyebrow="How it works"
            title="From a sentence to a working workspace"
            description="Four steps run end to end. You stay in control and step in only where judgment is needed."
          />
        </Reveal>

        <div className="mt-14 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((step, i) => (
            <Reveal key={step.n} delay={i * 90}>
              <GlassCard
                interactive
                delay={i * 0.04}
                className={`h-full p-5 ${
                  i === 1 ? "lg:translate-y-6" : i === 2 ? "lg:-translate-y-4" : ""
                }`}
              >
                <div className="flex items-center">
                  <span className="flex h-10 w-10 flex-shrink-0 items-center justify-center rounded-full border border-accent/50 bg-accent-soft font-mono text-xs font-semibold text-accent-bright">
                    {step.n}
                  </span>
                  {i < steps.length - 1 ? (
                    <span
                      aria-hidden
                      className="ml-3 hidden h-px flex-1 flow-line-x lg:block"
                    />
                  ) : null}
                </div>
                <h3 className="mt-5 text-base font-semibold text-foreground">
                  {step.title}
                </h3>
                <p className="mt-2 text-sm leading-relaxed text-secondary">
                  {step.body}
                </p>
                <p className="mt-5 font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
                  {i < steps.length - 1 ? "Hands off to next step" : "Feeds Mission Control"}
                </p>
              </GlassCard>
            </Reveal>
          ))}
        </div>
      </div>
    </section>
  );
}
