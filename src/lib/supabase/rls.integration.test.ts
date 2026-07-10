// Live RLS verification suite.
//
// Unlike the rest of the test suite, this hits a real Supabase project: it
// signs in as TEST_USER_EMAIL / TEST_USER_PASSWORD via the anon client, seeds
// "victim" rows owned by a throwaway second user (via the service-role admin
// client), and asserts the signed-in user cannot select, update, or delete
// those rows on businesses, missions, mission_tasks, and agent_runs.
//
// Requires a full credential set. Skips cleanly (with the missing var names
// in the suite name) everywhere those aren't provisioned — local dev, CI, etc.

import { randomUUID } from "node:crypto";
import { createClient, type SupabaseClient } from "@supabase/supabase-js";
import { afterAll, beforeAll, describe, expect, it } from "vitest";

const SUPABASE_URL = process.env.NEXT_PUBLIC_SUPABASE_URL;
const SUPABASE_ANON_KEY = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
const SERVICE_ROLE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY;
const TEST_USER_EMAIL = process.env.TEST_USER_EMAIL;
const TEST_USER_PASSWORD = process.env.TEST_USER_PASSWORD;

const missingCreds = (
  [
    ["NEXT_PUBLIC_SUPABASE_URL", SUPABASE_URL],
    ["NEXT_PUBLIC_SUPABASE_ANON_KEY", SUPABASE_ANON_KEY],
    ["SUPABASE_SERVICE_ROLE_KEY", SERVICE_ROLE_KEY],
    ["TEST_USER_EMAIL", TEST_USER_EMAIL],
    ["TEST_USER_PASSWORD", TEST_USER_PASSWORD],
  ] as const
)
  .filter(([, value]) => !value)
  .map(([name]) => name);

const canRun = missingCreds.length === 0;

const suiteName = canRun
  ? "RLS: cross-tenant access is denied"
  : `RLS: cross-tenant access is denied (skipped — set ${missingCreds.join(", ")} to run against a live Supabase project)`;

describe.skipIf(!canRun)(suiteName, () => {
  let admin: SupabaseClient;
  let anon: SupabaseClient;
  let testUserId: string;
  let otherUserId: string;
  let otherBusinessId: string;
  let otherMissionId: string;
  let otherMissionTaskId: string;
  let otherAgentRunId: string;
  let otherApprovalId: string;
  // supabase/m4a-approvals-queue.sql is an additive migration applied
  // manually via the Supabase SQL Editor (see that file's header) — not
  // auto-applied like the rest of this repo's ad-hoc supabase/*.sql files.
  // Until Arnav runs it against this project, `approvals` won't exist yet;
  // that must not fail the whole beforeAll (and so every other table's RLS
  // assertions below) — it only skips the one approvals-specific test.
  let approvalsTableExists = true;

  beforeAll(async () => {
    admin = createClient(SUPABASE_URL as string, SERVICE_ROLE_KEY as string, {
      auth: { autoRefreshToken: false, persistSession: false },
    });
    anon = createClient(SUPABASE_URL as string, SUPABASE_ANON_KEY as string, {
      auth: { autoRefreshToken: false, persistSession: false },
    });

    const { data: signIn, error: signInError } = await anon.auth.signInWithPassword({
      email: TEST_USER_EMAIL as string,
      password: TEST_USER_PASSWORD as string,
    });
    if (signInError || !signIn.user) {
      throw new Error(`Failed to sign in as TEST_USER_EMAIL: ${signInError?.message ?? "no user returned"}`);
    }
    testUserId = signIn.user.id;

    // Throwaway second user who owns every "victim" row below. Created via
    // the admin API so it needs no separate credential set of its own.
    const { data: otherUser, error: otherUserError } = await admin.auth.admin.createUser({
      email: `rls-fixture-${randomUUID()}@example.com`,
      password: randomUUID(),
      email_confirm: true,
    });
    if (otherUserError || !otherUser.user) {
      throw new Error(`Failed to create fixture user: ${otherUserError?.message ?? "no user returned"}`);
    }
    otherUserId = otherUser.user.id;

    const { data: business, error: businessError } = await admin
      .from("businesses")
      .insert({ user_id: otherUserId, idea_name: "RLS fixture business" })
      .select("id")
      .single();
    if (businessError || !business) {
      throw new Error(`Failed to seed fixture business: ${businessError?.message ?? "no row returned"}`);
    }
    otherBusinessId = business.id;

    const { data: mission, error: missionError } = await admin
      .from("missions")
      .insert({ business_id: otherBusinessId, user_id: otherUserId, name: "RLS fixture mission" })
      .select("id")
      .single();
    if (missionError || !mission) {
      throw new Error(`Failed to seed fixture mission: ${missionError?.message ?? "no row returned"}`);
    }
    otherMissionId = mission.id;

    const { data: missionTask, error: missionTaskError } = await admin
      .from("mission_tasks")
      .insert({
        mission_id: otherMissionId,
        business_id: otherBusinessId,
        user_id: otherUserId,
        task_id: "rls-fixture-task",
        title: "RLS fixture mission task",
        branch: "feature/rls-fixture",
        position: 1,
      })
      .select("id")
      .single();
    if (missionTaskError || !missionTask) {
      throw new Error(`Failed to seed fixture mission task: ${missionTaskError?.message ?? "no row returned"}`);
    }
    otherMissionTaskId = missionTask.id;

    const { data: agentRun, error: agentRunError } = await admin
      .from("agent_runs")
      .insert({
        business_id: otherBusinessId,
        user_id: otherUserId,
        agent_id: "rls-fixture-agent",
        node_id: "rls-fixture-node",
        title: "RLS fixture agent run",
      })
      .select("id")
      .single();
    if (agentRunError || !agentRun) {
      throw new Error(`Failed to seed fixture agent run: ${agentRunError?.message ?? "no row returned"}`);
    }
    otherAgentRunId = agentRun.id;

    // approvals is not business-scoped (owner-only RLS — see
    // supabase/m4a-approvals-queue.sql), so this fixture only needs user_id.
    const { data: approval, error: approvalError } = await admin
      .from("approvals")
      .insert({
        user_id: otherUserId,
        request_type: "merge_approval",
        request_id: "rls-fixture-task",
        source_file: "rls-fixture-task_merge_approval_request.txt",
        title: "RLS fixture approval",
        body: "fixture body",
      })
      .select("id")
      .single();
    if (approvalError || !approval) {
      approvalsTableExists = false;
    } else {
      otherApprovalId = approval.id;
    }
  });

  afterAll(async () => {
    // Deleting the fixture business cascades to its mission, mission_tasks,
    // and agent_runs rows. approvals has no business_id, so it's deleted
    // explicitly (it cascades from the fixture user instead).
    if (otherApprovalId) {
      await admin.from("approvals").delete().eq("id", otherApprovalId);
    }
    if (otherBusinessId) {
      await admin.from("businesses").delete().eq("id", otherBusinessId);
    }
    if (otherUserId) {
      await admin.auth.admin.deleteUser(otherUserId);
    }
    await anon.auth.signOut();
  });

  it("signs in as a user distinct from the fixture owner", () => {
    expect(testUserId).toBeTruthy();
    expect(otherUserId).toBeTruthy();
    expect(testUserId).not.toBe(otherUserId);
  });

  it("cannot select, update, or delete another user's business", async () => {
    const { data: selected, error: selectError } = await anon
      .from("businesses")
      .select("id")
      .eq("id", otherBusinessId);
    expect(selectError).toBeNull();
    expect(selected).toEqual([]);

    const { data: updated } = await anon
      .from("businesses")
      .update({ idea_name: "hijacked" })
      .eq("id", otherBusinessId)
      .select("id");
    expect(updated).toEqual([]);

    const { data: deleted } = await anon.from("businesses").delete().eq("id", otherBusinessId).select("id");
    expect(deleted).toEqual([]);

    const { data: stillThere } = await admin.from("businesses").select("idea_name").eq("id", otherBusinessId).single();
    expect(stillThere?.idea_name).toBe("RLS fixture business");
  });

  it("cannot select, update, or delete another user's mission", async () => {
    const { data: selected, error: selectError } = await anon
      .from("missions")
      .select("id")
      .eq("id", otherMissionId);
    expect(selectError).toBeNull();
    expect(selected).toEqual([]);

    const { data: updated } = await anon
      .from("missions")
      .update({ name: "hijacked" })
      .eq("id", otherMissionId)
      .select("id");
    expect(updated).toEqual([]);

    const { data: deleted } = await anon.from("missions").delete().eq("id", otherMissionId).select("id");
    expect(deleted).toEqual([]);

    const { data: stillThere } = await admin.from("missions").select("name").eq("id", otherMissionId).single();
    expect(stillThere?.name).toBe("RLS fixture mission");
  });

  it("cannot select, update, or delete another user's mission task", async () => {
    const { data: selected, error: selectError } = await anon
      .from("mission_tasks")
      .select("id")
      .eq("id", otherMissionTaskId);
    expect(selectError).toBeNull();
    expect(selected).toEqual([]);

    const { data: updated } = await anon
      .from("mission_tasks")
      .update({ title: "hijacked" })
      .eq("id", otherMissionTaskId)
      .select("id");
    expect(updated).toEqual([]);

    const { data: deleted } = await anon.from("mission_tasks").delete().eq("id", otherMissionTaskId).select("id");
    expect(deleted).toEqual([]);

    const { data: stillThere } = await admin
      .from("mission_tasks")
      .select("title")
      .eq("id", otherMissionTaskId)
      .single();
    expect(stillThere?.title).toBe("RLS fixture mission task");
  });

  it("cannot select, update, or delete another user's agent run", async () => {
    const { data: selected, error: selectError } = await anon
      .from("agent_runs")
      .select("id")
      .eq("id", otherAgentRunId);
    expect(selectError).toBeNull();
    expect(selected).toEqual([]);

    const { data: updated } = await anon
      .from("agent_runs")
      .update({ title: "hijacked" })
      .eq("id", otherAgentRunId)
      .select("id");
    expect(updated).toEqual([]);

    const { data: deleted } = await anon.from("agent_runs").delete().eq("id", otherAgentRunId).select("id");
    expect(deleted).toEqual([]);

    const { data: stillThere } = await admin
      .from("agent_runs")
      .select("title")
      .eq("id", otherAgentRunId)
      .single();
    expect(stillThere?.title).toBe("RLS fixture agent run");
  });

  it("cannot select, update, or delete another user's approval", async (ctx) => {
    // approvalsTableExists is only known after beforeAll runs, so this can't
    // be an it.skipIf (evaluated at collection time, before the fixture
    // seeding above has had a chance to run) — skip at runtime instead.
    if (!approvalsTableExists) {
      ctx.skip();
      return;
    }

    const { data: selected, error: selectError } = await anon
      .from("approvals")
      .select("id")
      .eq("id", otherApprovalId);
    expect(selectError).toBeNull();
    expect(selected).toEqual([]);

    const { data: updated } = await anon
      .from("approvals")
      .update({ status: "approved" })
      .eq("id", otherApprovalId)
      .select("id");
    expect(updated).toEqual([]);

    const { data: deleted } = await anon.from("approvals").delete().eq("id", otherApprovalId).select("id");
    expect(deleted).toEqual([]);

    const { data: stillThere } = await admin
      .from("approvals")
      .select("status")
      .eq("id", otherApprovalId)
      .single();
    expect(stillThere?.status).toBe("pending");
  });
});
