// Server-side PostHog capture for API routes.
//
// Complete no-op when POSTHOG_KEY is unset — no client is constructed, no
// network calls are made. Never throws and never blocks the response: the
// capture call itself only enqueues the event, and the network flush is
// deferred to `after()` (see instrumentation.md) so it runs once the
// response has already been sent.

import { after } from "next/server";
import { PostHog } from "posthog-node";
import { ANALYTICS_EVENTS, type AnalyticsEventKey } from "@/lib/analytics/events";

let client: PostHog | null | undefined;

function getClient(): PostHog | null {
  if (client !== undefined) return client;

  const apiKey = process.env.POSTHOG_KEY;
  if (!apiKey) {
    client = null;
    return client;
  }

  client = new PostHog(apiKey, {
    host: process.env.POSTHOG_HOST || "https://us.i.posthog.com",
  });
  return client;
}

/**
 * Captures a server-side analytics event from the canonical catalog
 * (see `@/lib/analytics/events`). Fire-and-forget: does not throw, does not
 * await the network request, and does not block the caller.
 */
export function capture(
  eventKey: AnalyticsEventKey,
  distinctId: string,
  properties: Record<string, unknown> = {},
): void {
  try {
    const posthog = getClient();
    if (!posthog) return;

    const event = ANALYTICS_EVENTS[eventKey];
    posthog.capture({ distinctId, event: event.name, properties });

    after(async () => {
      try {
        await posthog.flush();
      } catch {
        // Never let a flush failure surface to the caller or the request lifecycle.
      }
    });
  } catch {
    // Analytics must never break the request it's instrumenting.
  }
}
