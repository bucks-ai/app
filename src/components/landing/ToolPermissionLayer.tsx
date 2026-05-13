import Link from "next/link";

type PermissionLevel = "auto" | "approval" | "human-only";

interface Tool {
  name: string;
  purpose: string;
  permission: PermissionLevel;
}

const TOOLS: Tool[] = [
  { name: "GitHub", purpose: "Commits, PRs, CI pipelines", permission: "auto" },
  { name: "Vercel", purpose: "Deploys, domain config, edge functions", permission: "auto" },
  { name: "Supabase", purpose: "Database schema, migrations, storage", permission: "auto" },
  { name: "PostHog", purpose: "Event tracking, funnel analysis", permission: "auto" },
  { name: "Resend", purpose: "Transactional and marketing email", permission: "auto" },
  { name: "Apollo", purpose: "Prospect sourcing, ICP enrichment", permission: "auto" },
  { name: "OpenAI", purpose: "Content generation, embeddings", permission: "auto" },
  { name: "Cloudflare", purpose: "DNS, CDN, edge routing", permission: "auto" },
  { name: "Gmail", purpose: "Outreach within approved limits", permission: "approval" },
  { name: "Stripe", purpose: "Billing setup, payment links", permission: "human-only" },
];

const PERMISSION_META: Record<PermissionLevel, { label: string; color: string }> = {
  auto: { label: "Auto", color: "#4F46E5" },
  approval: { label: "Approval", color: "#f59e0b" },
  "human-only": { label: "Human only", color: "#ef4444" },
};

export function ToolPermissionLayer() {
  return (
    <section className="py-24" style={{ background: "#080808" }}>
      <div className="mx-auto max-w-6xl px-6">
        <div className="mb-4">
          <span
            className="font-mono text-xs uppercase tracking-widest"
            style={{ color: "#4F46E5" }}
          >
            Tool Layer
          </span>
        </div>
        <h2
          className="mb-4 text-4xl font-semibold tracking-tight"
          style={{ color: "#F0F0F0" }}
        >
          Every tool wired in. Every permission explicit.
        </h2>
        <p className="mb-12 max-w-xl text-lg" style={{ color: "#888888" }}>
          bucks.ai operates through a typed tool registry. You grant access
          once — the system enforces scope automatically.
        </p>

        <div className="mb-6 flex flex-wrap gap-4">
          {(["auto", "approval", "human-only"] as PermissionLevel[]).map(
            (level) => (
              <div key={level} className="flex items-center gap-2">
                <div
                  className="h-2 w-2 rounded-full"
                  style={{ background: PERMISSION_META[level].color }}
                />
                <span className="text-xs" style={{ color: "#888888" }}>
                  {PERMISSION_META[level].label}
                </span>
              </div>
            )
          )}
        </div>

        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {TOOLS.map(({ name, purpose, permission }) => (
            <div
              key={name}
              className="flex items-start justify-between rounded-xl border p-4"
              style={{
                background: "#0F0F0F",
                borderColor:
                  permission === "human-only"
                    ? "#ef444420"
                    : permission === "approval"
                    ? "#f59e0b20"
                    : "#1C1C1C",
              }}
            >
              <div>
                <div
                  className="mb-0.5 text-sm font-medium"
                  style={{ color: "#F0F0F0" }}
                >
                  {name}
                </div>
                <div className="text-xs" style={{ color: "#888888" }}>
                  {purpose}
                </div>
              </div>
              <div
                className="ml-3 shrink-0 rounded px-2 py-0.5 font-mono text-xs"
                style={{
                  background: `${PERMISSION_META[permission].color}18`,
                  color: PERMISSION_META[permission].color,
                }}
              >
                {PERMISSION_META[permission].label}
              </div>
            </div>
          ))}
        </div>

        <div className="mt-8 text-center">
          <Link
            href="/tools"
            className="text-sm text-[#888888] transition-colors hover:text-[#F0F0F0]"
          >
            View full tool registry &#8594;
          </Link>
        </div>
      </div>
    </section>
  );
}
