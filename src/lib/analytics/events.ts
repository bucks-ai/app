// Canonical analytics event taxonomy for the core signup -> deploy funnel.
// This module defines event names and their property conventions only —
// no posthog.capture() calls live here. See docs/M3-EVENT-TAXONOMY.md for
// the funnel narrative and full property rules.

export interface AnalyticsEventDefinition {
  readonly name: string;
  readonly description: string;
  /** Property keys every capture() call for this event must include. */
  readonly requiredProperties: readonly string[];
}

function defineEvent(
  name: string,
  description: string,
  requiredProperties: readonly string[] = [],
): AnalyticsEventDefinition {
  return Object.freeze({ name, description, requiredProperties: Object.freeze([...requiredProperties]) });
}

export const ANALYTICS_EVENTS = Object.freeze({
  USER_SIGNED_UP: defineEvent(
    "user_signed_up",
    "A visitor completes account creation and becomes an authenticated user.",
  ),
  INTAKE_STARTED: defineEvent(
    "intake_started",
    "A user begins the founder intake wizard for a new business idea.",
  ),
  INTAKE_SUBMITTED: defineEvent(
    "intake_submitted",
    "A user submits the completed intake wizard, ready for blueprint generation.",
  ),
  BLUEPRINT_GENERATED: defineEvent(
    "blueprint_generated",
    "The AI pipeline returns a generated launch blueprint from intake data.",
  ),
  BLUEPRINT_SAVED: defineEvent(
    "blueprint_saved",
    "The founder approves the blueprint and it is persisted, creating the business record.",
    ["business_id"],
  ),
  TOOL_APPROVAL_REQUESTED: defineEvent(
    "tool_approval_requested",
    "A tool permission (e.g. GitHub, Vercel) enters the queue awaiting founder approval.",
    ["business_id"],
  ),
  TOOL_APPROVED: defineEvent(
    "tool_approved",
    "The founder approves a pending tool permission.",
    ["business_id"],
  ),
  REPO_CREATED: defineEvent(
    "repo_created",
    "A GitHub repository is provisioned for the business.",
    ["business_id"],
  ),
  SCAFFOLD_PREPARED: defineEvent(
    "scaffold_prepared",
    "A deployable Next.js scaffold is written to the business repository.",
    ["business_id"],
  ),
  VERCEL_PROJECT_CREATED: defineEvent(
    "vercel_project_created",
    "A Vercel project is created and linked to the business repository.",
    ["business_id"],
  ),
  DEPLOY_SUCCEEDED: defineEvent(
    "deploy_succeeded",
    "A deployment for the business completes successfully and is publicly reachable.",
    ["business_id"],
  ),
} as const);

export type AnalyticsEventKey = keyof typeof ANALYTICS_EVENTS;
export type AnalyticsEventName = (typeof ANALYTICS_EVENTS)[AnalyticsEventKey]["name"];

export const ALL_ANALYTICS_EVENTS: readonly AnalyticsEventDefinition[] = Object.freeze(
  Object.values(ANALYTICS_EVENTS),
);

/**
 * Property keys that must never appear in analytics event properties,
 * regardless of event. Identify users via business_id / distinct_id only.
 */
export const FORBIDDEN_PROPERTY_KEYS: readonly string[] = Object.freeze([
  "email",
  "name",
  "full_name",
  "phone",
  "phone_number",
  "address",
]);
