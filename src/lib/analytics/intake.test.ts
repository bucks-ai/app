import { describe, expect, it, vi } from "vitest";
import { captureIntakeStarted, captureIntakeSubmitted } from "@/lib/analytics/intake";

describe("intake analytics helpers", () => {
  it("captures intake_started through the typed client event key", () => {
    const capture = vi.fn();

    captureIntakeStarted(capture);

    expect(capture).toHaveBeenCalledWith("INTAKE_STARTED");
  });

  it("captures intake_submitted through the typed client event key", () => {
    const capture = vi.fn();

    captureIntakeSubmitted(capture);

    expect(capture).toHaveBeenCalledWith("INTAKE_SUBMITTED");
  });
});
