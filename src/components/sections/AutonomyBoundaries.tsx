const autonomous = [
  "Writing and deploying code",
  "Creating and managing GitHub repos",
  "Building and shipping landing pages",
  "Setting up analytics and tracking",
  "Running outreach campaigns",
  "Managing CI/CD pipelines",
  "Iterating on the product",
  "Filing bug reports and fixes",
];

const escalates = [
  "Legal agreements and contracts",
  "Financial transactions and payments",
  "Identity verification",
  "Live client communication",
  "Anything outside your defined boundaries",
];

export function AutonomyBoundaries() {
  return (
    <section className="bg-black px-6 py-24">
      <div className="mx-auto max-w-6xl">
        <div className="mb-16 text-center">
          <h2 className="mb-4 text-3xl font-bold tracking-tight text-white sm:text-4xl">
            Autonomy with boundaries
          </h2>
          <p className="mx-auto max-w-xl text-neutral-400">
            bucks.ai moves fast on the things you want automated. It always
            escalates on the things that matter most.
          </p>
        </div>

        <div className="grid gap-6 sm:grid-cols-2">
          {/* Autonomous */}
          <div className="rounded-2xl border border-emerald-500/20 bg-emerald-500/5 p-8">
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/20">
                <svg
                  className="h-4 w-4 text-emerald-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M13 10V3L4 14h7v7l9-11h-7z"
                  />
                </svg>
              </div>
              <h3 className="font-semibold text-emerald-400">
                Runs autonomously
              </h3>
            </div>
            <ul className="space-y-3">
              {autonomous.map((item) => (
                <li key={item} className="flex items-start gap-2.5 text-sm text-neutral-300">
                  <svg
                    className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-500"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M5 13l4 4L19 7"
                    />
                  </svg>
                  {item}
                </li>
              ))}
            </ul>
          </div>

          {/* Escalates */}
          <div className="rounded-2xl border border-amber-500/20 bg-amber-500/5 p-8">
            <div className="mb-6 flex items-center gap-3">
              <div className="flex h-8 w-8 items-center justify-center rounded-full bg-amber-500/20">
                <svg
                  className="h-4 w-4 text-amber-400"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={2}
                >
                  <path
                    strokeLinecap="round"
                    strokeLinejoin="round"
                    d="M12 9v2m0 4h.01M10.29 3.86L1.82 18a2 2 0 001.71 3h16.94a2 2 0 001.71-3L13.71 3.86a2 2 0 00-3.42 0z"
                  />
                </svg>
              </div>
              <h3 className="font-semibold text-amber-400">Always escalates</h3>
            </div>
            <ul className="space-y-3">
              {escalates.map((item) => (
                <li key={item} className="flex items-start gap-2.5 text-sm text-neutral-300">
                  <svg
                    className="mt-0.5 h-4 w-4 flex-shrink-0 text-amber-500"
                    fill="none"
                    viewBox="0 0 24 24"
                    stroke="currentColor"
                    strokeWidth={2}
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M12 9v2m0 4h.01"
                    />
                  </svg>
                  {item}
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
