// Centralized guard against E2E/seeded-test traffic polluting analytics.
// Every capture helper (src/lib/analytics/server.ts, src/lib/analytics/client.ts)
// runs its call through guardCapture() so future capture points inherit this
// behavior automatically. See docs/M3-EVENT-TAXONOMY.md for the full contract.

import { isFakeAiEnabled } from "@/lib/e2e-fake-ai";

// process.env.E2E_FAKE_AI / process.env.M3_VERIFY are never inlined into the
// client bundle (only NEXT_PUBLIC_-prefixed vars are), so posthog-js capture
// in the browser (e.g. PostHogProvider's automatic $pageview) also honors
// these NEXT_PUBLIC_ mirrors. They only need to be set during local/E2E-CI
// builds -- a real deploy never defines them.
function isE2ETestModeEnabled(): boolean {
  return isFakeAiEnabled() || process.env.NEXT_PUBLIC_E2E_FAKE_AI === "true";
}

/**
 * The explicit override used once by m3-10 to re-enable capture during an
 * E2E verification run while stamping every event with verification_run:
 * true, so the run's events can be found (and told apart from real traffic)
 * afterward.
 */
export function isVerifyRunEnabled(): boolean {
  return process.env.M3_VERIFY === "true" || process.env.NEXT_PUBLIC_M3_VERIFY === "true";
}

/**
 * True when the current request/session is E2E or seeded-test traffic that
 * must not pollute analytics: E2E_FAKE_AI is enabled, or the given email
 * matches TEST_USER_EMAIL.
 */
export function isTestTraffic(email?: string | null): boolean {
  if (isE2ETestModeEnabled()) return true;

  const testEmail = process.env.TEST_USER_EMAIL;
  return Boolean(testEmail && email && email === testEmail);
}

export interface CaptureGuardResult {
  /** false means the caller must no-op the capture entirely -- no network call. */
  allow: boolean;
  /** Properties to send; carries verification_run when M3_VERIFY is enabled. */
  properties: Record<string, unknown>;
}

/**
 * Runs a capture call through the test-traffic guard. Test traffic is
 * dropped entirely unless isVerifyRunEnabled(), in which case capture is
 * re-enabled and every event -- test traffic or not -- is stamped with
 * verification_run: true.
 */
export function guardCapture(
  email: string | null | undefined,
  properties: Record<string, unknown> = {},
): CaptureGuardResult {
  if (isVerifyRunEnabled()) {
    return { allow: true, properties: { ...properties, verification_run: true } };
  }

  if (isTestTraffic(email)) {
    return { allow: false, properties };
  }

  return { allow: true, properties };
}
