import { capture, type ClientAnalyticsEventName } from "@/lib/analytics/client";
import { ANALYTICS_EVENTS } from "@/lib/analytics/events";

type ClientCapture = (eventName: ClientAnalyticsEventName) => void;

export type IntakeStartedCaptureState = {
  current: boolean;
};

export function captureIntakeStartedOnce(
  state: IntakeStartedCaptureState,
  clientCapture: ClientCapture = capture,
): boolean {
  if (state.current) return false;

  state.current = true;
  clientCapture(ANALYTICS_EVENTS.INTAKE_STARTED.name);
  return true;
}

export function captureIntakeSubmitted(clientCapture: ClientCapture = capture): void {
  clientCapture(ANALYTICS_EVENTS.INTAKE_SUBMITTED.name);
}
