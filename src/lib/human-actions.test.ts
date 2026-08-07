// Unit tests for src/lib/human-actions.ts — the open/closed status vocabulary
// shared by the Actions tab and the execution-status blockers, plus the
// decision write behind PATCH /api/human-actions/[id].

import { beforeEach, describe, expect, it, vi } from "vitest";

const { createSupabaseServerClientMock } = vi.hoisted(() => ({
  createSupabaseServerClientMock: vi.fn(),
}));

vi.mock("@/lib/supabase/server", () => ({
  createSupabaseServerClient: createSupabaseServerClientMock,
}));

import { isHumanActionOpen, updateHumanActionDecision } from "@/lib/human-actions";

describe("isHumanActionOpen", () => {
  it("treats the producer statuses as open work", () => {
    for (const status of ["pending", "open", "required", "needs_review", "needs_approval"]) {
      expect(isHumanActionOpen(status)).toBe(true);
    }
  });

  it("closes an action once the founder has decided it either way", () => {
    expect(isHumanActionOpen("approved")).toBe(false);
    expect(isHumanActionOpen("rejected")).toBe(false);
    expect(isHumanActionOpen("dismissed")).toBe(false);
  });

  it("still closes the runner's completion statuses", () => {
    for (const status of ["complete", "completed", "resolved", "done", "closed"]) {
      expect(isHumanActionOpen(status)).toBe(false);
    }
  });

  it("normalizes case and whitespace", () => {
    expect(isHumanActionOpen("  Approved ")).toBe(false);
    expect(isHumanActionOpen("PENDING")).toBe(true);
  });

  it("defaults an unknown or missing status to open", () => {
    expect(isHumanActionOpen("waiting_on_founder")).toBe(true);
    expect(isHumanActionOpen(null)).toBe(true);
    expect(isHumanActionOpen(undefined)).toBe(true);
  });
});

type StubResponse = { data: unknown; error: unknown };

function makeSupabaseStub(responses: StubResponse[]) {
  let call = 0;
  const next = () =>
    Promise.resolve(
      responses[call++] ?? { data: null, error: { message: "no more stubbed responses" } }
    );

  const builder = {
    from: vi.fn(() => builder),
    select: vi.fn(() => builder),
    update: vi.fn(() => builder),
    eq: vi.fn(() => builder),
    maybeSingle: vi.fn(() => next()),
    single: vi.fn(() => next()),
  };
  return builder;
}

const PENDING_ROW = {
  id: "action-1",
  business_id: "business-1",
  user_id: "user-1",
  title: "Register the business",
  description: "Legal operation",
  status: "pending",
  risk_level: "high",
};

describe("updateHumanActionDecision", () => {
  beforeEach(() => {
    createSupabaseServerClientMock.mockReset();
  });

  it("returns not_found when the row does not exist", async () => {
    createSupabaseServerClientMock.mockResolvedValue(
      makeSupabaseStub([{ data: null, error: null }])
    );

    const result = await updateHumanActionDecision({
      id: "action-1",
      decision: "approve",
      userId: "user-1",
    });

    expect(result.error).toBeTruthy();
    expect(result.code).toBe("not_found");
  });

  it("returns forbidden when the row belongs to another user", async () => {
    createSupabaseServerClientMock.mockResolvedValue(
      makeSupabaseStub([{ data: { ...PENDING_ROW, user_id: "someone-else" }, error: null }])
    );

    const result = await updateHumanActionDecision({
      id: "action-1",
      decision: "approve",
      userId: "user-1",
    });

    expect(result.code).toBe("forbidden");
  });

  it("flips an open row to approved", async () => {
    createSupabaseServerClientMock.mockResolvedValue(
      makeSupabaseStub([
        { data: PENDING_ROW, error: null },
        { data: { ...PENDING_ROW, status: "approved" }, error: null },
      ])
    );

    const result = await updateHumanActionDecision({
      id: "action-1",
      decision: "approve",
      userId: "user-1",
    });

    expect(result.error).toBeNull();
    expect(result.data?.status).toBe("approved");
  });

  it("maps dismiss onto the rejected status", async () => {
    const stub = makeSupabaseStub([
      { data: PENDING_ROW, error: null },
      { data: { ...PENDING_ROW, status: "rejected" }, error: null },
    ]);
    createSupabaseServerClientMock.mockResolvedValue(stub);

    const result = await updateHumanActionDecision({
      id: "action-1",
      decision: "dismiss",
      userId: "user-1",
    });

    expect(result.data?.status).toBe("rejected");
    expect(stub.update).toHaveBeenCalledWith(
      expect.objectContaining({ status: "rejected" })
    );
  });

  it("is idempotent: an already-decided row is returned without re-updating", async () => {
    const alreadyApproved = { ...PENDING_ROW, status: "approved" };
    const stub = makeSupabaseStub([{ data: alreadyApproved, error: null }]);
    createSupabaseServerClientMock.mockResolvedValue(stub);

    const result = await updateHumanActionDecision({
      id: "action-1",
      decision: "dismiss",
      userId: "user-1",
    });

    expect(result.error).toBeNull();
    expect(result.data).toEqual(alreadyApproved);
    expect(stub.update).not.toHaveBeenCalled();
  });
});
