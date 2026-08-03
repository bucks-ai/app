import { describe, expect, it, vi } from "vitest";
import {
  DEMO_PENDING_TOOL_PERMISSIONS,
  resetDemoBusiness,
  seedE2E,
  upsertTestUser,
} from "@/lib/seed-e2e";

function makeAdminMock() {
  const businessesDelete = vi.fn().mockReturnValue({ eq: vi.fn().mockResolvedValue({ error: null }) });
  const businessesInsertSingle = vi.fn().mockResolvedValue({ data: { id: "business-1" }, error: null });
  const businessesInsertSelect = vi.fn().mockReturnValue({ single: businessesInsertSingle });
  const businessesInsert = vi.fn().mockReturnValue({ select: businessesInsertSelect });
  const blueprintsInsert = vi.fn().mockResolvedValue({ error: null });
  const toolPermissionsInsert = vi.fn().mockResolvedValue({ error: null });

  const from = vi.fn((table: string) => {
    if (table === "businesses") {
      return { delete: businessesDelete, insert: businessesInsert };
    }
    if (table === "business_blueprints") {
      return { insert: blueprintsInsert };
    }
    if (table === "tool_permissions") {
      return { insert: toolPermissionsInsert };
    }
    throw new Error(`Unexpected table: ${table}`);
  });

  const listUsers = vi.fn().mockResolvedValue({ data: { users: [] }, error: null });
  const createUser = vi.fn().mockResolvedValue({ data: { user: { id: "user-1" } }, error: null });
  const updateUserById = vi.fn().mockResolvedValue({ data: {}, error: null });

  return {
    from,
    auth: { admin: { listUsers, createUser, updateUserById } },
    _spies: {
      from,
      businessesDelete,
      businessesInsert,
      blueprintsInsert,
      toolPermissionsInsert,
      listUsers,
      createUser,
      updateUserById,
    },
  };
}

describe("upsertTestUser", () => {
  it("creates a new user when none exists with that email", async () => {
    const admin = makeAdminMock();

    const userId = await upsertTestUser(admin as never, "test@example.com", "hunter2");

    expect(userId).toBe("user-1");
    expect(admin._spies.createUser).toHaveBeenCalledWith({
      email: "test@example.com",
      password: "hunter2",
      email_confirm: true,
    });
    expect(admin._spies.updateUserById).not.toHaveBeenCalled();
  });

  it("resets the password of an existing user instead of creating a duplicate", async () => {
    const admin = makeAdminMock();
    admin._spies.listUsers.mockResolvedValue({
      data: { users: [{ id: "existing-user", email: "test@example.com" }] },
      error: null,
    });

    const userId = await upsertTestUser(admin as never, "test@example.com", "newpassword");

    expect(userId).toBe("existing-user");
    expect(admin._spies.updateUserById).toHaveBeenCalledWith("existing-user", {
      password: "newpassword",
      email_confirm: true,
    });
    expect(admin._spies.createUser).not.toHaveBeenCalled();
  });

  it("throws when user creation fails", async () => {
    const admin = makeAdminMock();
    admin._spies.createUser.mockResolvedValue({ data: { user: null }, error: { message: "boom" } });

    await expect(upsertTestUser(admin as never, "test@example.com", "hunter2")).rejects.toThrow("boom");
  });
});

describe("resetDemoBusiness", () => {
  it("deletes only the test user's businesses before inserting the demo business and blueprint", async () => {
    const admin = makeAdminMock();

    const businessId = await resetDemoBusiness(admin as never, "user-1");

    expect(businessId).toBe("business-1");
    expect(admin._spies.from).toHaveBeenCalledWith("businesses");

    const deleteEqMock = admin._spies.businessesDelete.mock.results[0].value.eq;
    expect(deleteEqMock).toHaveBeenCalledWith("user_id", "user-1");

    expect(admin._spies.businessesInsert).toHaveBeenCalledWith(
      expect.objectContaining({ user_id: "user-1", idea_name: "Seeded Demo Co" })
    );
    expect(admin._spies.blueprintsInsert).toHaveBeenCalledWith(
      expect.objectContaining({ business_id: "business-1", user_id: "user-1" })
    );
    expect(admin._spies.toolPermissionsInsert).toHaveBeenCalledWith(
      DEMO_PENDING_TOOL_PERMISSIONS.map((permission) => ({
        ...permission,
        user_id: "user-1",
        business_id: "business-1",
      }))
    );
    expect(
      DEMO_PENDING_TOOL_PERMISSIONS.every((permission) => permission.status === "approval_requested")
    ).toBe(true);
  });

  it("throws when the delete step fails, without inserting a new business", async () => {
    const admin = makeAdminMock();
    admin._spies.businessesDelete.mockReturnValue({ eq: vi.fn().mockResolvedValue({ error: { message: "delete failed" } }) });

    await expect(resetDemoBusiness(admin as never, "user-1")).rejects.toThrow("delete failed");
    expect(admin._spies.businessesInsert).not.toHaveBeenCalled();
  });
});

describe("seedE2E", () => {
  it("upserts the test user and resets their demo business end to end", async () => {
    const admin = makeAdminMock();

    const result = await seedE2E(admin as never, { email: "test@example.com", password: "hunter2" });

    expect(result).toEqual({ userId: "user-1", businessId: "business-1" });
  });
});
