const profiles = [
  {
    title: "Solo AI founders",
    description:
      "You have the idea and the technical chops, but not enough hours. bucks.ai handles execution so you can stay in product mode.",
  },
  {
    title: "Small teams shipping fast",
    description:
      "2–5 person teams that want to run 3–4 products in parallel without hiring ops, devops, or growth staff.",
  },
  {
    title: "Technical builders going to market",
    description:
      "Engineers who can build but hate the go-to-market grind. bucks.ai handles landing pages, outreach, and analytics.",
  },
];

export function BuiltFor() {
  return (
    <section className="bg-neutral-950 px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <div className="mb-16 text-center">
          <h2 className="mb-4 text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Built for AI/software founders
          </h2>
          <p className="mx-auto max-w-xl text-neutral-400">
            Not for enterprises. Not for agencies. Built for the people who are
            building the next wave of AI software products.
          </p>
        </div>

        <div className="grid gap-6 sm:grid-cols-3">
          {profiles.map((profile) => (
            <div
              key={profile.title}
              className="rounded-2xl border border-white/10 bg-white/5 p-7"
            >
              <h3 className="mb-3 font-semibold text-white">{profile.title}</h3>
              <p className="text-sm leading-relaxed text-neutral-400">
                {profile.description}
              </p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}
