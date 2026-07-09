import { describe, expect, it, vi } from "vitest";
import { ANALYTICS_EVENTS } from "@/lib/analytics/events";
import { captureIntakeStartedOnce, captureIntakeSubmitted } from "./intake-client";

describe("intake client analytics helpers", () => {
  it("captures intake_started only once for the provided mount state", () => {
    const capture = vi.fn();
    const state = { current: false };

    expect(captureIntakeStartedOnce(state, capture)).toBe(true);
    expect(captureIntakeStartedOnce(state, capture)).toBe(false);

    expect(capture).toHaveBeenCalledTimes(1);
    expect(capture).toHaveBeenCalledWith(ANALYTICS_EVENTS.INTAKE_STARTED.name);
    expect(state.current).toBe(true);
  });

  it("captures intake_submitted using the canonical event name", () => {
    const capture = vi.fn();

    captureIntakeSubmitted(capture);

    expect(capture).toHaveBeenCalledTimes(1);
    expect(capture).toHaveBeenCalledWith(ANALYTICS_EVENTS.INTAKE_SUBMITTED.name);
  });
});
