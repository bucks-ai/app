import {
  ApprovalCheckpoint,
  type CheckpointData,
} from "@/components/landing/ApprovalCheckpoint";
import { ToolTile, type ToolTileData } from "@/components/landing/ToolTile";
import { Reveal } from "@/components/ui/Reveal";
import { SectionHeader } from "@/components/ui/SectionHeader";

const checkpoints: CheckpointData[] = [
  {
    title: "Public preview release",
    body: "The Deploy Agent has a Vercel preview built and checked. Making it public is a side effect, so it stops here.",
    state: "Awaiting approval",
    risk: "medium",
    riskLabel: "customer facing",
    permissionPrompt: "deploy.promote(preview → public)",
    rollback: "Preview stays internal; deployment reverts to the last approved build in one step.",
    featured: true,
  },
  {
    title: "First outbound interview batch",
    body: "Validation drafted 12 interview invites. Outbound messaging never sends without a founder reading it first.",
    state: "Awaiting approval",
    risk: "high",
    riskLabel: "outbound contact",
    permissionPrompt: "outreach.send(batch=12, channel=email)",
    rollback: "Drafts stay queued; recipients are never contacted and the list is discarded on reject.",
  },
  {
    title: "Repo scaffold write",
    body: "Build asked to create the starter repository. Code writes inside the workspace are low-risk, so this cleared automatically under the constitution.",
    state: "Auto-approved",
    risk: "low",
    riskLabel: "workspace write",
    permissionPrompt: "github.create(repo, scaffold=next-starter)",
    rollback: "Repository is disposable until first deploy; delete restores a clean slate.",
  },
];

const tools: ToolTileData[] = [
  {
    name: "GitHub",
    role: "Issues, repo scaffolds, acceptance criteria, and implementation handoff.",
    access: "Approval gated",
    signal: "preview task prepared",
  },
  {
    name: "Vercel",
    role: "Preview deployment state, build readiness, and release checkpoint.",
    access: "Preview",
    signal: "deployment ready",
  },
  {
    name: "Supabase",
    role: "Saved businesses, auth state, execution records, and dashboard persistence.",
    access: "Read only",
    signal: "session-aware",
  },
  {
    name: "OpenAI",
    role: "Blueprint generation, agent reasoning, and validation prompt synthesis.",
    access: "Connected",
    signal: "route configured",
  },
  {
    name: "Stripe",
    role: "Billing rails for paid pilots — human-only until payment terms are approved.",
    access: "Approval gated",
    signal: "founder controlled",
  },
  {
    name: "PostHog",
    role: "Product telemetry feeding the learning loop: activation, conversion, retention.",
    access: "Preview",
    signal: "events mapped",
  },
];

export function SystemPreview() {
  return (
    <section className="relative overflow-hidden px-6 py-20 sm:py-28">
      <div aria-hidden className="grid-backdrop pointer-events-none absolute inset-0 opacity-40" />
      <div className="relative mx-auto max-w-6xl space-y-24">
        <div>
          <Reveal>
            <SectionHeader
              eyebrow="Human Checkpoints"
              title="Autonomy with brakes, not vibes"
              description="Every risky action surfaces as a checkpoint: the exact permission the agent asked for, the risk label, and the rollback path if you say no. Low-risk workspace writes clear automatically; side effects wait for you."
            />
          </Reveal>
          <div className="mt-10 grid gap-4 md:grid-cols-4">
            {checkpoints.map((checkpoint, index) => (
              <Reveal
                key={checkpoint.title}
                delay={index * 80}
                className={checkpoint.featured ? "md:col-span-2" : ""}
              >
                <ApprovalCheckpoint checkpoint={checkpoint} />
              </Reveal>
            ))}
          </div>
        </div>

        <div>
          <Reveal>
            <SectionHeader
              eyebrow="Tool Mesh"
              title="Connected tools behave like controlled infrastructure"
              description="bucks.ai coordinates the tools a software business actually runs on, with access mode and current signal visible on every tile."
            />
          </Reveal>
          {/* Was a 6-column track with the first two tiles spanning 3 and the
              rest spanning 2, which left the sixth tool alone in its own row
              beside an L-shaped void. Six equal tiles fill two clean rows. */}
          <div className="mt-10 grid gap-4 md:grid-cols-2 xl:grid-cols-3">
            {tools.map((tool, index) => (
              <Reveal
                key={tool.name}
                delay={index * 55}
              >
                <ToolTile
                  tool={tool}
                  className={index < 2 ? "min-h-[13.5rem]" : "min-h-[12rem]"}
                />
              </Reveal>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}
