const steps = [
  {
    number: "01",
    title: "Give it your idea",
    description:
      "Fill out the Idea Intake: startup name, one-line idea, primary goal, budget, timeline, and hard constraints. Takes under 5 minutes.",
  },
  {
    number: "02",
    title: "Review the blueprint",
    description:
      "bucks.ai generates a Business Blueprint — proposed stack, feature list, cost breakdown, and a phased launch plan. You approve, reject, or adjust.",
  },
  {
    number: "03",
    title: "It executes",
    description:
      "Once approved, bucks.ai builds the codebase, deploys to production, creates the landing page, sets up analytics, and starts the outreach pipeline.",
  },
  {
    number: "04",
    title: "You stay in control",
    description:
      "Watch progress in Mission Control. Approve anything that needs your sign-off (legal, financial, live client actions). Everything else runs autonomously.",
  },
];

export function HowItWorks() {
  return (
    <section id="how-it-works" className="bg-neutral-950 px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <div className="mb-16 text-center">
          <h2 className="mb-4 text-3xl font-bold tracking-tight text-white sm:text-4xl">
            How it works
          </h2>
          <p className="mx-auto max-w-xl text-neutral-400">
            Four steps from raw idea to live, revenue-generating product.
          </p>
        </div>

        <div className="grid gap-8 sm:grid-cols-2 lg:grid-cols-4">
          {steps.map((step, i) => (
            <div key={step.number} className="relative">
              {/* Connector line */}
              {i < steps.length - 1 && (
                <div className="absolute top-6 left-full hidden h-px w-full -translate-y-1/2 bg-gradient-to-r from-emerald-500/40 to-transparent lg:block" />
              )}

              <div className="mb-4 inline-flex h-12 w-12 items-center justify-center rounded-full border border-emerald-500/40 bg-emerald-500/10 text-sm font-bold text-emerald-400">
                {step.number}
              </div>
              <h3 className="mb-2 font-semibold text-white">{step.title}</h3>
              <p className="text-sm leading-relaxed text-neutral-400">
                {step.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
