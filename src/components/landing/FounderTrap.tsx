const TRAP_ITEMS = [
  "Manually sourcing leads because the CRM isn't set up",
  "Writing Stripe webhooks instead of talking to customers",
  "Debugging deploys instead of deciding strategy",
  "Scheduling drip campaigns yourself because no one else will",
  "Copy-pasting analytics dashboards from templates",
];

const OPERATOR_ITEMS = [
  "Review the weekly metric digest in one minute",
  "Approve or veto agent proposals before they ship",
  "Join the calls only AI cannot close",
  "Sign the documents that require your identity",
  "Set the direction — the system executes it",
];

export function FounderTrap() {
  return (
    <section
      className="py-24"
      style={{ background: "#080808" }}
    >
      <div className="mx-auto max-w-6xl px-6">
        {/* Label */}
        <div className="mb-4">
          <span
            className="font-mono text-xs uppercase tracking-widest"
            style={{ color: "#4F46E5" }}
          >
            The Founder Trap
          </span>
        </div>

        <h2
          className="mb-4 max-w-2xl text-4xl font-semibold leading-tight tracking-tight"
          style={{ color: "#F0F0F0" }}
        >
          Most founders become the operator of their own startup.
        </h2>
        <p className="mb-16 max-w-xl text-lg" style={{ color: "#888888" }}>
          bucks.ai makes you the CEO, not the operator.
        </p>

        <div className="grid gap-8 lg:grid-cols-2">
          {/* Without bucks.ai */}
          <div
            className="rounded-xl border p-6"
            style={{ background: "#0F0F0F", borderColor: "#1C1C1C" }}
          >
            <div
              className="mb-4 inline-block rounded px-2 py-0.5 font-mono text-xs"
              style={{ background: "#1C1C1C", color: "#888888" }}
            >
              Without bucks.ai
            </div>
            <ul className="space-y-3">
              {TRAP_ITEMS.map((item) => (
                <li key={item} className="flex items-start gap-3">
                  <span className="mt-0.5 text-sm" style={{ color: "#888888" }}>
                    —
                  </span>
                  <span className="text-sm" style={{ color: "#888888" }}>
                    {item}
                  </span>
                </li>
              ))}
            </ul>
          </div>

          {/* With bucks.ai */}
          <div
            className="rounded-xl border p-6"
            style={{
              background: "#0F0F0F",
              borderColor: "#4F46E5",
              boxShadow: "0 0 0 1px rgba(79,70,229,0.15)",
            }}
          >
            <div
              className="mb-4 inline-block rounded px-2 py-0.5 font-mono text-xs"
              style={{ background: "rgba(79,70,229,0.15)", color: "#4F46E5" }}
            >
              With bucks.ai
            </div>
            <ul className="space-y-3">
              {OPERATOR_ITEMS.map((item) => (
                <li key={item} className="flex items-start gap-3">
                  <span
                    className="mt-0.5 text-sm font-semibold"
                    style={{ color: "#4F46E5" }}
                  >
                    +
                  </span>
                  <span className="text-sm" style={{ color: "#F0F0F0" }}>
                    {item}
                  </span>
                </li>
              ))}
            </ul>
          </div>
        </div>
      </div>
    </section>
  );
}
