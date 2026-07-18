import { describe, expect, it } from "vitest";
import { computeSandboxStatus, getSandboxFieldStatuses } from "@/lib/sandbox";

describe("computeSandboxStatus", () => {
  it("returns unconfigured when no fields are set", () => {
    expect(computeSandboxStatus({})).toBe("unconfigured");
    expect(
      computeSandboxStatus({
        repo_full_name: null,
        vercel_project_id: undefined,
        github_token_secret_name: "",
        vercel_token_secret_name: "   ",
      })
    ).toBe("unconfigured");
  });

  it("returns partial when some but not all fields are set", () => {
    expect(
      computeSandboxStatus({
        repo_full_name: "acme/landing-page",
        vercel_project_id: null,
      })
    ).toBe("partial");
  });

  it("returns configured when every field is set", () => {
    expect(
      computeSandboxStatus({
        repo_full_name: "acme/landing-page",
        vercel_project_id: "prj_123",
        github_token_secret_name: "ACME_GITHUB_TOKEN",
        vercel_token_secret_name: "ACME_VERCEL_TOKEN",
      })
    ).toBe("configured");
  });
});

describe("getSandboxFieldStatuses", () => {
  it("marks every field unconfigured with a null value when there is no record", () => {
    const statuses = getSandboxFieldStatuses(null);

    expect(statuses).toHaveLength(4);
    for (const status of statuses) {
      expect(status.configured).toBe(false);
      expect(status.value).toBeNull();
    }
    expect(statuses.map((s) => s.field)).toEqual([
      "repo_full_name",
      "vercel_project_id",
      "github_token_secret_name",
      "vercel_token_secret_name",
    ]);
  });

  it("reports configured fields with their stored name and unset fields as null", () => {
    const statuses = getSandboxFieldStatuses({
      repo_full_name: "acme/landing-page",
      vercel_project_id: null,
      github_token_secret_name: "ACME_GITHUB_TOKEN",
      vercel_token_secret_name: undefined,
    });

    const byField = Object.fromEntries(statuses.map((s) => [s.field, s]));
    expect(byField.repo_full_name).toMatchObject({
      configured: true,
      value: "acme/landing-page",
    });
    expect(byField.vercel_project_id).toMatchObject({
      configured: false,
      value: null,
    });
    expect(byField.github_token_secret_name).toMatchObject({
      configured: true,
      value: "ACME_GITHUB_TOKEN",
    });
    expect(byField.vercel_token_secret_name).toMatchObject({
      configured: false,
      value: null,
    });
  });

  it("never returns anything but the stored NAME — trims whitespace-only values to unconfigured", () => {
    const statuses = getSandboxFieldStatuses({
      repo_full_name: "   ",
    });

    const repo = statuses.find((s) => s.field === "repo_full_name");
    expect(repo?.configured).toBe(false);
    expect(repo?.value).toBeNull();
  });
});
