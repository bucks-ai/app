// Deterministic blueprint-to-mission compiler for the Execute button
// (POST /api/businesses/[id]/execute). No LLM call — this expands the
// sections of a saved launch blueprint (src/types/startup.ts BusinessBlueprint,
// stored as Record<string, unknown> since model output shape varies — see
// src/lib/schemas/save-blueprint.ts) into 3-5 concrete starter mission_tasks
// rows, following the task-shape conventions of the seeded M1-M3 missions
// (supabase/missions.sql, supabase/m4a-seed-mission.sql) and the Python
// compiler's slug/branch conventions (runner/langgraph/tools/mission_compiler.py).
//
// Every mission compiled here is runner_target: "business" (src/lib/missions.ts)
// and, once M4b's claim gate allows it, executes against that business's OWN
// freshly scaffolded repo (runner/langgraph/tools/foreign_repo_workspace.py) —
// never the bucks-ai repo. The three core sections below assume that fresh
// scaffold already exists (e.g. a Next.js starter template) and give the
// worker concrete, self-contained starter work — build the landing page,
// wire a starter analytics stub, deploy — rather than bucks-ai-specific tasks
// like scaffolding infrastructure or CI from nothing.
//
// Pure — no I/O. The caller (src/lib/missions.ts) handles inserting the
// compiled tasks into Supabase.

export const MISSION_TASK_TYPES = [
  "backend",
  "design",
  "docs",
  "frontend",
  "general",
  "infra",
  "polish",
  "test",
  "ui",
] as const;

export type MissionTaskType = (typeof MISSION_TASK_TYPES)[number];

export interface CompiledMissionTask {
  taskId: string;
  title: string;
  description?: string;
  type: MissionTaskType;
  branch: string;
  position: number;
}

const MAX_TASKS = 5;
const MIN_TASKS = 3;

export function slug(text: string, maxLen = 40): string {
  const cleaned = text
    .toLowerCase()
    .replace(/[^\w\s-]/g, "")
    .replace(/[\s_]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return cleaned.slice(0, maxLen).replace(/-+$/, "");
}

function asRecord(value: unknown): Record<string, unknown> | null {
  return typeof value === "object" && value !== null ? (value as Record<string, unknown>) : null;
}

function asString(value: unknown): string | null {
  return typeof value === "string" && value.trim() ? value.trim() : null;
}

function asStringArray(value: unknown): string[] {
  if (!Array.isArray(value)) return [];
  return value
    .map((item) => {
      if (typeof item === "string") return asString(item);
      const record = asRecord(item);
      if (!record) return null;
      return asString(record.name) ?? asString(record.title) ?? asString(record.tool);
    })
    .filter((item): item is string => !!item);
}

interface SectionSpec {
  title: string;
  description: string;
  type: MissionTaskType;
  branchSlug: string;
}

function buildLandingPageSection(blueprint: Record<string, unknown>): SectionSpec {
  const mvpScope = asStringArray(blueprint.mvpScope);
  const summary = asString(blueprint.businessSummary) ?? "the saved launch blueprint";
  const items = mvpScope.length > 0 ? mvpScope.slice(0, 3) : [summary];

  return {
    title: `Build landing page section: ${items[0]}`,
    description: `In the fresh scaffolded repo, build the landing page section(s) covering: ${items.join("; ")}.`,
    type: "frontend",
    branchSlug: "landing-page",
  };
}

function buildAnalyticsStubSection(blueprint: Record<string, unknown>): SectionSpec {
  const analyticsPlan = asRecord(blueprint.analyticsPlan);
  const northStar = asString(analyticsPlan?.northStarMetric);
  const events = asStringArray(analyticsPlan?.events);

  return {
    title: northStar ? `Wire analytics stub: ${northStar}` : "Wire analytics stub",
    description:
      events.length > 0
        ? `Wire a starter analytics stub capturing the blueprint's planned events: ${events.slice(0, 5).join(", ")}.`
        : "Wire a starter analytics stub (a single page-view or signup event is enough) so this fresh scaffold has working instrumentation from day one.",
    type: "backend",
    branchSlug: "analytics-stub",
  };
}

function buildDeploySection(blueprint: Record<string, unknown>): SectionSpec {
  const stack = asStringArray(blueprint.suggestedStack);
  const tools = asStringArray(blueprint.requiredTools);
  const items = stack.length > 0 ? stack : tools;

  return {
    title: "Deploy the scaffolded app",
    description:
      items.length > 0
        ? `Deploy the fresh scaffolded repo (${items.slice(0, 3).join(", ")}) to its Vercel project and verify the production build.`
        : "Deploy the fresh scaffolded repo to its Vercel project and verify the production build.",
    type: "infra",
    branchSlug: "deploy",
  };
}

function buildGoToMarketSection(blueprint: Record<string, unknown>): SectionSpec | null {
  const motion =
    asString(blueprint.goToMarketMotion) ?? asString(asRecord(blueprint.marketingPlan)?.motion);
  if (!motion) return null;

  return {
    title: `Execute go-to-market: ${motion}`,
    description: `Kick off the blueprint's go-to-market motion: ${motion}.`,
    type: "general",
    branchSlug: "go-to-market",
  };
}

function buildRiskSection(blueprint: Record<string, unknown>): SectionSpec | null {
  const risks = asStringArray(blueprint.risks);
  if (risks.length === 0) return null;

  return {
    title: `Mitigate top risk: ${risks[0]}`,
    description: `Address the highest-priority risk from the blueprint: ${risks[0]}.`,
    type: "docs",
    branchSlug: "risk-mitigation",
  };
}

/**
 * Compiles a saved business blueprint into an ordered list of 3-5 starter
 * mission tasks, assuming the mission executes against a FRESH scaffolded
 * repo (see the module-level comment above) rather than the bucks-ai repo.
 * Deterministic — the same blueprint always compiles to the same tasks.
 * `missionSlug` seeds branch names, mirroring the Python compiler's
 * `feature/{mission_slug}/{title_slug}` convention.
 */
export function compileBlueprintToMissionTasks(
  blueprint: Record<string, unknown>,
  missionSlug: string
): CompiledMissionTask[] {
  const core: SectionSpec[] = [
    buildLandingPageSection(blueprint),
    buildAnalyticsStubSection(blueprint),
    buildDeploySection(blueprint),
  ];
  const optional = [buildGoToMarketSection(blueprint), buildRiskSection(blueprint)].filter(
    (section): section is SectionSpec => section !== null
  );

  const sections = [...core, ...optional].slice(0, MAX_TASKS);
  // Core sections always produce output, so this floor is unreachable in
  // practice, but guards the documented 3-5 task contract explicitly.
  if (sections.length < MIN_TASKS) {
    throw new Error("Blueprint compiler produced fewer than the minimum 3 starter tasks.");
  }

  return sections.map((section, index) => {
    const position = index + 1;
    const titleSlug = slug(section.title, 30);
    return {
      taskId: `${missionSlug}-${position}`,
      title: section.title,
      description: section.description,
      type: section.type,
      branch: `feature/${missionSlug}/${section.branchSlug || titleSlug}`,
      position,
    };
  });
}
