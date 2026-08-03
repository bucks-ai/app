// Idempotently provisions the core PostHog funnel dashboard from code.
//
// Usage: npm run analytics:provision
//
// Reads POSTHOG_PERSONAL_API_KEY + POSTHOG_PROJECT_ID (and optional
// POSTHOG_HOST, default https://us.posthog.com) from the environment (loads
// .env.local via dotenv). Skips cleanly, printing a message and exiting 0,
// when either required var is absent — this script never prompts for or
// requests credential values.
//
// Creates/updates by exact name match (never duplicates on re-run):
//   1. A funnel insight over the canonical signup -> deploy funnel
//      (see src/lib/analytics/events.ts).
//   2. A weekly trend of unique users who fired `deploy_succeeded`.
//   3. A dashboard named "bucks.ai core funnel" containing both insights.

import "dotenv/config";
import { ANALYTICS_EVENTS } from "../../src/lib/analytics/events";

const DASHBOARD_NAME = "bucks.ai core funnel";
const FUNNEL_INSIGHT_NAME = "Core signup -> deploy funnel";
const TRENDS_INSIGHT_NAME = "Weekly unique users who deployed";

const FUNNEL_EVENT_KEYS = [
  "USER_SIGNED_UP",
  "INTAKE_SUBMITTED",
  "BLUEPRINT_SAVED",
  "TOOL_APPROVED",
  "REPO_CREATED",
  "DEPLOY_SUCCEEDED",
] as const;

interface PostHogInsight {
  id: number;
  name: string;
  dashboards?: number[];
}

interface PostHogDashboard {
  id: number;
  name: string;
}

interface PostHogListResponse<T> {
  results: T[];
}

interface Env {
  apiKey: string;
  projectId: string;
  host: string;
}

function readEnv(): Env | null {
  const apiKey = process.env.POSTHOG_PERSONAL_API_KEY;
  const projectId = process.env.POSTHOG_PROJECT_ID;
  const host = process.env.POSTHOG_HOST || "https://us.posthog.com";

  if (!apiKey || !projectId) {
    console.log(
      "Skipping PostHog dashboard provisioning: POSTHOG_PERSONAL_API_KEY and/or " +
        "POSTHOG_PROJECT_ID are not set.",
    );
    return null;
  }

  return { apiKey, projectId, host };
}

async function phFetch<T>(env: Env, path: string, init: RequestInit = {}): Promise<T> {
  const res = await fetch(`${env.host}${path}`, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      Authorization: `Bearer ${env.apiKey}`,
      ...init.headers,
    },
  });

  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`PostHog API ${init.method ?? "GET"} ${path} failed: ${res.status} ${body}`);
  }

  return res.json() as Promise<T>;
}

async function findInsightByName(env: Env, name: string): Promise<PostHogInsight | null> {
  const data = await phFetch<PostHogListResponse<PostHogInsight>>(
    env,
    `/api/projects/${env.projectId}/insights/?search=${encodeURIComponent(name)}`,
  );
  return data.results.find((insight) => insight.name === name) ?? null;
}

async function upsertInsight(
  env: Env,
  name: string,
  query: Record<string, unknown>,
): Promise<PostHogInsight> {
  const existing = await findInsightByName(env, name);

  if (existing) {
    const updated = await phFetch<PostHogInsight>(
      env,
      `/api/projects/${env.projectId}/insights/${existing.id}/`,
      { method: "PATCH", body: JSON.stringify({ name, query }) },
    );
    console.log(`Updated insight "${name}" (id=${updated.id})`);
    return updated;
  }

  const created = await phFetch<PostHogInsight>(env, `/api/projects/${env.projectId}/insights/`, {
    method: "POST",
    body: JSON.stringify({ name, query }),
  });
  console.log(`Created insight "${name}" (id=${created.id})`);
  return created;
}

async function findDashboardByName(env: Env, name: string): Promise<PostHogDashboard | null> {
  const data = await phFetch<PostHogListResponse<PostHogDashboard>>(
    env,
    `/api/projects/${env.projectId}/dashboards/?search=${encodeURIComponent(name)}`,
  );
  return data.results.find((dashboard) => dashboard.name === name) ?? null;
}

async function upsertDashboard(env: Env, name: string): Promise<PostHogDashboard> {
  const existing = await findDashboardByName(env, name);
  if (existing) {
    console.log(`Found existing dashboard "${name}" (id=${existing.id})`);
    return existing;
  }

  const created = await phFetch<PostHogDashboard>(env, `/api/projects/${env.projectId}/dashboards/`, {
    method: "POST",
    body: JSON.stringify({ name }),
  });
  console.log(`Created dashboard "${name}" (id=${created.id})`);
  return created;
}

async function attachInsightToDashboard(
  env: Env,
  insight: PostHogInsight,
  dashboardId: number,
): Promise<void> {
  const dashboards = insight.dashboards ?? [];
  if (dashboards.includes(dashboardId)) {
    console.log(`Insight "${insight.name}" already on dashboard id=${dashboardId}`);
    return;
  }

  await phFetch(env, `/api/projects/${env.projectId}/insights/${insight.id}/`, {
    method: "PATCH",
    body: JSON.stringify({ dashboards: [...dashboards, dashboardId] }),
  });
  console.log(`Attached insight "${insight.name}" to dashboard id=${dashboardId}`);
}

async function main() {
  const env = readEnv();
  if (!env) return;

  const funnelSeries = FUNNEL_EVENT_KEYS.map((key) => {
    const event = ANALYTICS_EVENTS[key];
    return { kind: "EventsNode", event: event.name, name: event.name };
  });

  const funnelQuery = {
    kind: "InsightVizNode",
    source: {
      kind: "FunnelsQuery",
      series: funnelSeries,
      funnelsFilter: { funnelVizType: "steps" },
    },
  };

  const trendsQuery = {
    kind: "InsightVizNode",
    source: {
      kind: "TrendsQuery",
      series: [
        {
          kind: "EventsNode",
          event: ANALYTICS_EVENTS.DEPLOY_SUCCEEDED.name,
          name: ANALYTICS_EVENTS.DEPLOY_SUCCEEDED.name,
          math: "dau",
        },
      ],
      interval: "week",
      dateRange: { date_from: "-90d" },
    },
  };

  const funnelInsight = await upsertInsight(env, FUNNEL_INSIGHT_NAME, funnelQuery);
  const trendsInsight = await upsertInsight(env, TRENDS_INSIGHT_NAME, trendsQuery);
  const dashboard = await upsertDashboard(env, DASHBOARD_NAME);

  await attachInsightToDashboard(env, funnelInsight, dashboard.id);
  await attachInsightToDashboard(env, trendsInsight, dashboard.id);

  console.log("PostHog dashboard provisioning complete.");
}

main().catch((error) => {
  console.error("provision-dashboards failed:", error instanceof Error ? error.message : error);
  process.exit(1);
});
