// Deterministic AI fixture mode for E2E tests.
//
// When E2E_FAKE_AI=true and NODE_ENV is not "production", AI-calling routes
// exercised by E2E (currently just /api/generate-blueprint) skip the real
// model call and return a fixture built from generateMockBlueprint instead,
// so intake-to-blueprint E2E runs are fast, free, and deterministic.
//
// The flag is ignored outright in production: a misconfigured env can never
// serve fixture data to real users.

import type { AutonomyPreference, BusinessTypeGuess, StartupIdea } from "@/types/startup";
import type { GenerateBlueprintBody } from "@/lib/schemas/generate-blueprint";
import { generateMockBlueprint } from "@/lib/mock-blueprint";

const DEFAULT_BUSINESS_TYPE_GUESS: BusinessTypeGuess = "Unsure";
const DEFAULT_AUTONOMY_PREFERENCE: AutonomyPreference = "Ask before major actions";

export function isFakeAiEnabled(): boolean {
  if (process.env.E2E_FAKE_AI !== "true") return false;

  // Never on a deployed environment: Vercel sets VERCEL=1 on every deploy.
  // A misconfigured env can never serve fixture data to real users.
  if (process.env.VERCEL) {
    console.warn(
      "E2E_FAKE_AI is set but this is a Vercel deployment; ignoring the flag and using the real AI provider.",
    );
    return false;
  }

  // `next build && next start` sets NODE_ENV=production even for a local/CI
  // production build, so CI must opt in explicitly to use the fixture there.
  // (The CI e2e job sets E2E_FAKE_AI_ALLOW_PRODUCTION_BUILD=true; deployed
  // production is already excluded by the VERCEL check above.)
  if (
    process.env.NODE_ENV === "production" &&
    process.env.E2E_FAKE_AI_ALLOW_PRODUCTION_BUILD !== "true"
  ) {
    console.warn(
      "E2E_FAKE_AI is set but NODE_ENV=production; ignoring the flag and using the real AI provider.",
    );
    return false;
  }

  return true;
}

// generateBlueprintBodySchema leaves most fields optional, but
// generateMockBlueprint expects the fully-populated StartupIdea shape the
// intake wizard always sends client-side, so fill in the same defaults here.
function toStartupIdea(body: GenerateBlueprintBody): StartupIdea {
  return {
    ideaName: body.ideaName,
    oneLineIdea: body.oneLineIdea,
    ideaDescription: body.ideaDescription ?? "",
    targetCustomer: body.targetCustomer ?? "",
    businessTypeGuess: body.businessTypeGuess ?? DEFAULT_BUSINESS_TYPE_GUESS,
    primaryGoal: body.primaryGoal,
    successMetric: body.successMetric ?? "",
    budget: body.budget,
    timeline: body.timeline,
    autonomyPreference: body.autonomyPreference ?? DEFAULT_AUTONOMY_PREFERENCE,
    spendingLimit: body.spendingLimit ?? "",
    hardConstraints: body.hardConstraints ?? "",
    humanOnlyActions: body.humanOnlyActions ?? "",
    forbiddenActions: body.forbiddenActions ?? "",
    preferredTools: body.preferredTools ?? "",
  };
}

export function buildFakeBlueprint(body: GenerateBlueprintBody) {
  return generateMockBlueprint(toStartupIdea(body));
}
