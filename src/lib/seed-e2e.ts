// Core reset logic for the E2E test user + demo business, used by
// scripts/seed-e2e.ts. Kept framework-agnostic (just a SupabaseClient) so
// it can be unit-tested with a mocked client — see src/lib/seed-e2e.test.ts.
//
// Safety invariant: every write here is scoped to the single test user id
// resolved from the given email. It never touches rows owned by anyone else.

import type { SupabaseClient } from "@supabase/supabase-js";
import type { BusinessBlueprintOutput } from "@/lib/schemas/blueprint-output";
import { businessBlueprintOutputSchema } from "@/lib/schemas/blueprint-output";
import type { NewBusinessInput } from "@/types/database";

export interface SeedE2EConfig {
  email: string;
  password: string;
}

export interface SeedE2EResult {
  userId: string;
  businessId: string;
}

// Deterministic demo business — every field is fixed so re-running the seed
// always produces byte-identical rows (aside from generated ids/timestamps).
export const DEMO_BUSINESS: Omit<NewBusinessInput, "user_id"> = {
  idea_name: "Seeded Demo Co",
  one_line_idea: "A demo business seeded for E2E tests.",
  idea_description:
    "A deterministic demo business created by scripts/seed-e2e.ts for Playwright E2E specs to exercise the dashboard and business detail views against known data.",
  target_customer: "Indie founders validating a new product idea.",
  business_type: "B2C",
  primary_goal: "Validate the E2E dashboard and business-detail flows.",
  success_metric: "All seeded E2E specs pass.",
  budget: "$0 (test fixture)",
  timeline: "N/A (test fixture)",
  autonomy_preference: "Recommend only",
  spending_limit: "$0",
  hard_constraints: "None — this is test fixture data.",
  human_only_actions: "None",
  forbidden_actions: "None",
  preferred_tools: "None",
  status: "blueprint_created",
};

export const DEMO_BLUEPRINT: BusinessBlueprintOutput = businessBlueprintOutputSchema.parse({
  businessSummary:
    "Seeded Demo Co helps indie founders validate new product ideas before building them.",
  businessType: "B2C",
  targetCustomer: "Indie founders validating a new product idea.",
  painHypothesis: "Founders waste months building things nobody wants.",
  mvpScope: ["Landing page with waitlist", "Single validation survey flow"],
  differentiation: ["Deterministic, seeded, and free of real AI calls"],
  suggestedStack: ["Next.js", "Supabase"],
  requiredTools: [
    { name: "Supabase", category: "Build", purpose: "Store validation responses." },
  ],
  requiredPermissions: [
    { title: "Read business data", reason: "Render the dashboard.", level: "Required" },
  ],
  goToMarketMotion: "Self-serve signup via the landing page.",
  marketingPlan: {
    motion: "Content-led waitlist growth.",
    channels: ["Twitter/X"],
    launchAssets: ["Landing page"],
    experiments: ["Waitlist headline A/B test"],
  },
  salesPlan: {
    motion: "Self-serve, no sales team.",
    channels: ["In-product upgrade prompt"],
    enablement: ["Pricing page"],
    sequence: ["Signup", "Activation", "Upgrade prompt"],
  },
  analyticsPlan: {
    northStarMetric: "Weekly active validators",
    events: ["waitlist_signup", "survey_submitted"],
    dashboards: ["Activation funnel"],
    reviewCadence: ["Weekly"],
  },
  humanRequiredActions: [
    { title: "Approve production deploy", reason: "Safety gate.", owner: "Founder" },
  ],
  nextAutonomousActions: [
    { title: "Send validation survey", detail: "Email the waitlist a five-question survey.", phase: "Validation" },
  ],
  risks: ["Low signal from a small waitlist"],
  successMetrics: ["100 waitlist signups", "20 survey responses"],
  killCriteria: ["Fewer than 5 survey responses after 2 weeks"],
});

// Exported for reuse by e2e/auth.spec.ts, which needs to confirm a
// freshly-signed-up user via the admin API on projects where email
// confirmation is required.
export async function findUserIdByEmail(admin: SupabaseClient, email: string): Promise<string | null> {
  const perPage = 200;
  for (let page = 1; ; page++) {
    const { data, error } = await admin.auth.admin.listUsers({ page, perPage });
    if (error) {
      throw new Error(`Failed to list users while looking up ${email}: ${error.message}`);
    }
    const match = data.users.find((user) => user.email === email);
    if (match) return match.id;
    if (data.users.length < perPage) return null;
  }
}

// Idempotently ensures exactly one auth user exists for `email` with `password`,
// creating it on first run and resetting its password on subsequent runs.
export async function upsertTestUser(admin: SupabaseClient, email: string, password: string): Promise<string> {
  const existingId = await findUserIdByEmail(admin, email);

  if (existingId) {
    const { error } = await admin.auth.admin.updateUserById(existingId, {
      password,
      email_confirm: true,
    });
    if (error) {
      throw new Error(`Failed to reset password for existing test user ${email}: ${error.message}`);
    }
    return existingId;
  }

  const { data, error } = await admin.auth.admin.createUser({
    email,
    password,
    email_confirm: true,
  });
  if (error || !data.user) {
    throw new Error(`Failed to create test user ${email}: ${error?.message ?? "no user returned"}`);
  }
  return data.user.id;
}

// Deletes every business owned by `userId` (cascading to blueprints, tool
// permissions, etc. per the FK constraints in supabase/schema.sql), then
// inserts one fresh deterministic demo business with a saved blueprint.
// Scoped strictly to `userId` — never touches another user's rows.
export async function resetDemoBusiness(admin: SupabaseClient, userId: string): Promise<string> {
  const { error: deleteError } = await admin.from("businesses").delete().eq("user_id", userId);
  if (deleteError) {
    throw new Error(`Failed to clear existing businesses for test user: ${deleteError.message}`);
  }

  const { data: business, error: insertError } = await admin
    .from("businesses")
    .insert({ ...DEMO_BUSINESS, user_id: userId })
    .select("id")
    .single();
  if (insertError || !business) {
    throw new Error(`Failed to insert demo business: ${insertError?.message ?? "no row returned"}`);
  }

  const { error: blueprintError } = await admin.from("business_blueprints").insert({
    business_id: business.id,
    user_id: userId,
    blueprint: DEMO_BLUEPRINT,
  });
  if (blueprintError) {
    throw new Error(`Failed to insert demo blueprint: ${blueprintError.message}`);
  }

  return business.id;
}

export async function seedE2E(admin: SupabaseClient, config: SeedE2EConfig): Promise<SeedE2EResult> {
  const userId = await upsertTestUser(admin, config.email, config.password);
  const businessId = await resetDemoBusiness(admin, userId);
  return { userId, businessId };
}
