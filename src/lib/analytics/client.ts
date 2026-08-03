// Client-side PostHog capture wrapper. Every future client-side capture()
// point should go through this module (not posthog-js directly) so it
// inherits the E2E/seeded-test-traffic guard in ./guard.ts. See
// docs/M3-EVENT-TAXONOMY.md for the full contract.

import posthog from "@/app/posthog";
import { ANALYTICS_EVENTS, type AnalyticsEventKey } from "@/lib/analytics/events";
import { guardCapture } from "@/lib/analytics/guard";

export type ClientAnalyticsEventKey = AnalyticsEventKey | "$pageview";

/**
 * Captures a client-side PostHog event (a canonical event name from
 * `@/lib/analytics/events`, or a posthog-js special event like `$pageview`).
 * `email`, when known, is checked against the test-traffic guard.
 */
export function capture(
  eventKey: ClientAnalyticsEventKey,
  properties: Record<string, unknown> = {},
  email?: string | null,
): void {
  const guard = guardCapture(email, properties);
  if (!guard.allow) return;

  if (!process.env.NEXT_PUBLIC_POSTHOG_KEY) return;

  const eventName = eventKey === "$pageview" ? eventKey : ANALYTICS_EVENTS[eventKey].name;
  posthog.capture(eventName, guard.properties);
}
