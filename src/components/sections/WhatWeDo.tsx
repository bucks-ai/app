const capabilities = [
  {
    icon: "🗺️",
    title: "Business planning",
    description:
      "Converts your idea into a structured plan: stack selection, feature set, cost estimate, and a week-by-week launch timeline.",
  },
  {
    icon: "⚙️",
    title: "MVP build & deploy",
    description:
      "Builds the codebase, sets up CI/CD, and deploys your MVP to production — from a blank repo to a live URL.",
  },
  {
    icon: "🌐",
    title: "Landing page & SEO",
    description:
      "Creates a conversion-optimized landing page with proper metadata, OG tags, and a waitlist or checkout flow.",
  },
  {
    icon: "📊",
    title: "Analytics setup",
    description:
      "Wires up product analytics, error tracking, and a basic dashboard so you know what's happening from day one.",
  },
  {
    icon: "📬",
    title: "Outreach pipeline",
    description:
      "Builds your first-customer pipeline: ICP identification, personalized copy, and outreach sequences ready to run.",
  },
  {
    icon: "🔄",
    title: "Continuous improvement",
    description:
      "Monitors metrics, identifies what to fix or ship next, and iterates — without waiting for you to file tickets.",
  },
];

export function WhatWeDo() {
  return (
    <section className="bg-black px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <div className="mb-16 text-center">
          <h2 className="mb-4 text-3xl font-bold tracking-tight text-white sm:text-4xl">
            What bucks.ai does
          </h2>
          <p className="mx-auto max-w-xl text-neutral-400">
            End-to-end startup execution — from raw idea to live product with
            paying customers in the pipeline.
          </p>
        </div>

        <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-3">
          {capabilities.map((cap) => (
            <div
              key={cap.title}
              className="rounded-2xl border border-white/10 bg-white/5 p-6 transition-colors hover:border-emerald-500/30 hover:bg-white/[0.07]"
            >
              <div className="mb-3 text-2xl">{cap.icon}</div>
              <h3 className="mb-2 font-semibold text-white">{cap.title}</h3>
              <p className="text-sm leading-relaxed text-neutral-400">
                {cap.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
