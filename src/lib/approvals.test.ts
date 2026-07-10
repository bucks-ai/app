// Unit tests for src/lib/approvals.ts — specifically the decision idempotency
// logic in updateApprovalDecision, which is the app-side half of the
// idempotency guarantee described in the M4a task: whichever channel
// (this API route, or the Slack daemon via the runner) resolves a request
// first wins. On the app side that means a decision only takes effect while
// the row is still "pending" (a compare-and-swap via a second .eq("status",
// "pending") filter on the UPDATE) — a second decision attempt is a no-op
// that returns the already-decided row rather than erroring.

import { beforeEach, describe, expect, it, vi } from "vitest";

const { createSupabaseServerClientMock } = vi.hoisted(() => ({
  createSupabaseServerClientMock: vi.fn(),
}));

vi.mock("@/lib/supabase/server", () => ({
  createSupabaseServerClient: createSupabaseServerClientMock,
}));

import { updateApprovalDecision } from "@/lib/approvals";

type SingleResponse = { data: unknown; error: unknown };

function makeSupabaseStub(singleResponses: SingleResponse[]) {
  let call = 0;
  const next = () => Promise.resolve(singleResponses[call++] ?? { data: null, error: { message: "no more stubbed responses" } });

  const builder = {
    from: vi.fn(() => builder),
    select: vi.fn(() => builder),
    update: vi.fn(() => builder),
    eq: vi.fn(() => builder),
    order: vi.fn(() => builder),
    single: vi.fn(() => next()),
  };
  return builder;
}

const PENDING_ROW = {
  id: "approval-1",
  user_id: "user-1",
  request_type: "merge_approval",
  request_id: "task-1",
  status: "pending",
};

describe("updateApprovalDecision", () => {
  beforeEach(() => {
    createSupabaseServerClientMock.mockReset();
  });

  it("returns not_found when the approval does not exist", async () => {
    createSupabaseServerClientMock.mockResolvedValue(
      makeSupabaseStub([{ data: null, error: { message: "no rows", code: "PGRST116" } }])
    );

    const result = await updateApprovalDecision({
      id: "approval-1",
      action: "approve",
      userId: "user-1",
      decidedBy: "founder@example.com",
    });

    expect(result.error).toBeTruthy();
    expect(result.code).toBe("not_found");
  });

  it("returns forbidden when the approval belongs to another user", async () => {
    createSupabaseServerClientMock.mockResolvedValue(
      makeSupabaseStub([{ data: { ...PENDING_ROW, user_id: "someone-else" }, error: null }])
    );

    const result = await updateApprovalDecision({
      id: "approval-1",
      action: "approve",
      userId: "user-1",
      decidedBy: "founder@example.com",
    });

    expect(result.code).toBe("forbidden");
  });

  it("flips a pending row to approved and stamps decided_by/decided_at", async () => {
    const updated = { ...PENDING_ROW, status: "approved", decided_by: "founder@example.com" };
    createSupabaseServerClientMock.mockResolvedValue(
      makeSupabaseStub([
        { data: PENDING_ROW, error: null }, // getApprovalById
        { data: updated, error: null }, // update().select().single()
      ])
    );

    const result = await updateApprovalDecision({
      id: "approval-1",
      action: "approve",
      userId: "user-1",
      decidedBy: "founder@example.com",
    });

    expect(result.error).toBeNull();
    expect(result.data?.status).toBe("approved");
  });

  it("is idempotent: a row already decided is returned as-is without re-updating", async () => {
    const alreadyApproved = { ...PENDING_ROW, status: "approved", decided_by: "slack:arnav" };
    const stub = makeSupabaseStub([{ data: alreadyApproved, error: null }]);
    createSupabaseServerClientMock.mockResolvedValue(stub);

    const result = await updateApprovalDecision({
      id: "approval-1",
      action: "reject",
      userId: "user-1",
      decidedBy: "founder@example.com",
    });

    expect(result.error).toBeNull();
    expect(result.data).toEqual(alreadyApproved);
    // Only the getApprovalById lookup ran — no update() call for an already-decided row.
    expect(stub.update).not.toHaveBeenCalled();
  });

  it("resolves a lost compare-and-swap race by returning the row's current state", async () => {
    const decidedElsewhere = { ...PENDING_ROW, status: "rejected", decided_by: "slack:arnav" };
    createSupabaseServerClientMock.mockResolvedValue(
      makeSupabaseStub([
        { data: PENDING_ROW, error: null }, // getApprovalById sees "pending"
        { data: null, error: { message: "no rows matched" } }, // update() loses the race (status changed underneath)
        { data: decidedElsewhere, error: null }, // refetch after losing the race
      ])
    );

    const result = await updateApprovalDecision({
      id: "approval-1",
      action: "approve",
      userId: "user-1",
      decidedBy: "founder@example.com",
    });

    expect(result.error).toBeNull();
    expect(result.data).toEqual(decidedElsewhere);
  });
});
