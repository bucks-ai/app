import { describe, expect, it } from "vitest";
import {
  compileBlueprintToMissionTasks,
  MISSION_TASK_TYPES,
} from "@/lib/mission-compiler";

const fullBlueprint = {
  businessSummary: "An AI-native tool for freelance designers.",
  mvpScope: ["Client intake form", "Project dashboard", "Invoice generator"],
  suggestedStack: ["Next.js", "Supabase", "Stripe"],
  requiredTools: ["GitHub", "Vercel"],
  goToMarketMotion: "Content-led organic acquisition",
  marketingPlan: { motion: "Content-led organic acquisition" },
  analyticsPlan: {
    northStarMetric: "Weekly active designers",
    events: ["signup", "project_created", "invoice_sent"],
  },
  risks: ["Low initial trust from freelancers", "Slow onboarding"],
};

const minimalBlueprint = {
  businessSummary: "A minimal viable idea with no other sections filled in.",
};

describe("compileBlueprintToMissionTasks", () => {
  it("compiles a full blueprint into 3-5 tasks", () => {
    const tasks = compileBlueprintToMissionTasks(fullBlueprint, "acme-mission");
    expect(tasks.length).toBeGreaterThanOrEqual(3);
    expect(tasks.length).toBeLessThanOrEqual(5);
  });

  it("compiles a minimal blueprint (only businessSummary) into at least 3 tasks", () => {
    const tasks = compileBlueprintToMissionTasks(minimalBlueprint, "acme-mission");
    expect(tasks.length).toBeGreaterThanOrEqual(3);
  });

  it("produces sequential 1-based positions", () => {
    const tasks = compileBlueprintToMissionTasks(fullBlueprint, "acme-mission");
    tasks.forEach((task, index) => {
      expect(task.position).toBe(index + 1);
    });
  });

  it("produces unique task ids seeded from the mission slug", () => {
    const tasks = compileBlueprintToMissionTasks(fullBlueprint, "acme-mission");
    const ids = tasks.map((t) => t.taskId);
    expect(new Set(ids).size).toBe(ids.length);
    ids.forEach((id) => expect(id.startsWith("acme-mission-")).toBe(true));
  });

  it("produces branch names scoped under feature/<missionSlug>/", () => {
    const tasks = compileBlueprintToMissionTasks(fullBlueprint, "acme-mission");
    tasks.forEach((task) => {
      expect(task.branch.startsWith("feature/acme-mission/")).toBe(true);
    });
  });

  it("only uses valid mission task types", () => {
    const tasks = compileBlueprintToMissionTasks(fullBlueprint, "acme-mission");
    tasks.forEach((task) => {
      expect(MISSION_TASK_TYPES).toContain(task.type);
    });
  });

  it("every task has a non-empty title and description", () => {
    const tasks = compileBlueprintToMissionTasks(fullBlueprint, "acme-mission");
    tasks.forEach((task) => {
      expect(task.title.length).toBeGreaterThan(0);
      expect(task.description?.length ?? 0).toBeGreaterThan(0);
    });
  });

  it("includes an analytics task when analyticsPlan data is present", () => {
    const tasks = compileBlueprintToMissionTasks(fullBlueprint, "acme-mission");
    expect(tasks.some((t) => t.title.toLowerCase().includes("analytics"))).toBe(true);
  });

  it("omits the analytics task when analyticsPlan data is absent", () => {
    const tasks = compileBlueprintToMissionTasks(minimalBlueprint, "acme-mission");
    expect(tasks.some((t) => t.title.toLowerCase().includes("analytics"))).toBe(false);
  });

  it("is deterministic for the same input", () => {
    const first = compileBlueprintToMissionTasks(fullBlueprint, "acme-mission");
    const second = compileBlueprintToMissionTasks(fullBlueprint, "acme-mission");
    expect(first).toEqual(second);
  });

  it("caps output at 5 tasks even with all optional sections present", () => {
    const tasks = compileBlueprintToMissionTasks(fullBlueprint, "acme-mission");
    expect(tasks.length).toBeLessThanOrEqual(5);
  });
});
