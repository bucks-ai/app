import { describe, expect, it } from "vitest";
import {
  ALL_ANALYTICS_EVENTS,
  ANALYTICS_EVENTS,
  FORBIDDEN_PROPERTY_KEYS,
} from "@/lib/analytics/events";

const SNAKE_CASE = /^[a-z][a-z0-9]*(_[a-z0-9]+)*$/;

describe("ANALYTICS_EVENTS", () => {
  it("contains the eleven canonical funnel events", () => {
    expect(ALL_ANALYTICS_EVENTS).toHaveLength(11);
  });

  it("has a unique name for every event", () => {
    const names = ALL_ANALYTICS_EVENTS.map((event) => event.name);
    expect(new Set(names).size).toBe(names.length);
  });

  it("uses snake_case for every event name", () => {
    for (const event of ALL_ANALYTICS_EVENTS) {
      expect(event.name).toMatch(SNAKE_CASE);
    }
  });

  it("gives every event a non-empty description", () => {
    for (const event of ALL_ANALYTICS_EVENTS) {
      expect(event.description.length).toBeGreaterThan(0);
    }
  });

  it("requires business_id on every event from blueprint_saved onward", () => {
    const businessScoped = [
      "BLUEPRINT_SAVED",
      "TOOL_APPROVAL_REQUESTED",
      "TOOL_APPROVED",
      "REPO_CREATED",
      "SCAFFOLD_PREPARED",
      "VERCEL_PROJECT_CREATED",
      "DEPLOY_SUCCEEDED",
    ] as const;
    for (const key of businessScoped) {
      expect(ANALYTICS_EVENTS[key].requiredProperties).toContain("business_id");
    }
  });

  it("does not require business_id before a business record exists", () => {
    const preBusiness = [
      "USER_SIGNED_UP",
      "INTAKE_STARTED",
      "INTAKE_SUBMITTED",
      "BLUEPRINT_GENERATED",
    ] as const;
    for (const key of preBusiness) {
      expect(ANALYTICS_EVENTS[key].requiredProperties).not.toContain("business_id");
    }
  });

  it("never lists a forbidden PII key as a required property", () => {
    for (const event of ALL_ANALYTICS_EVENTS) {
      for (const forbidden of FORBIDDEN_PROPERTY_KEYS) {
        expect(event.requiredProperties).not.toContain(forbidden);
      }
    }
  });

  it("is frozen at the catalog, event, and requiredProperties level", () => {
    expect(Object.isFrozen(ANALYTICS_EVENTS)).toBe(true);
    expect(Object.isFrozen(ALL_ANALYTICS_EVENTS)).toBe(true);
    for (const event of ALL_ANALYTICS_EVENTS) {
      expect(Object.isFrozen(event)).toBe(true);
      expect(Object.isFrozen(event.requiredProperties)).toBe(true);
    }
  });

  it("rejects attempts to mutate the catalog at runtime", () => {
    "use strict";
    expect(() => {
      // @ts-expect-error — intentional runtime mutation attempt against a readonly type
      ANALYTICS_EVENTS.USER_SIGNED_UP.name = "mutated";
    }).toThrow();
  });
});
