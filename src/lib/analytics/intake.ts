import { capture, type ClientAnalyticsEventKey } from "@/lib/analytics/client";

type ClientCapture = (
  eventKey: ClientAnalyticsEventKey,
  properties?: Record<string, unknown>,
  email?: string | null,
) => void;

export function captureIntakeStarted(captureFn: ClientCapture = capture): void {
  captureFn("INTAKE_STARTED");
}

export function captureIntakeSubmitted(captureFn: ClientCapture = capture): void {
  captureFn("INTAKE_SUBMITTED");
}
