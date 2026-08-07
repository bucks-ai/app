import { describe, expect, it } from "vitest";
import { resolveActionTarget } from "@/components/workspace/action-target";

const BUSINESS_ID = "b1b2c3d4";

describe("resolveActionTarget", () => {
  it("returns null when there is no href to act on", () => {
    expect(resolveActionTarget(null, BUSINESS_ID)).toBeNull();
    expect(resolveActionTarget(undefined, BUSINESS_ID)).toBeNull();
    expect(resolveActionTarget("   ", BUSINESS_ID)).toBeNull();
  });

  it("maps this business's legacy section anchors onto workspace tabs", () => {
    expect(
      resolveActionTarget(`/dashboard/businesses/${BUSINESS_ID}#tools`, BUSINESS_ID)
    ).toEqual({ kind: "tab", tab: "tools" });

    expect(
      resolveActionTarget(
        `/dashboard/businesses/${BUSINESS_ID}#repository-execution`,
        BUSINESS_ID
      )
    ).toEqual({ kind: "tab", tab: "build" });

    expect(
      resolveActionTarget(
        `/dashboard/businesses/${BUSINESS_ID}#deployment-execution`,
        BUSINESS_ID
      )
    ).toEqual({ kind: "tab", tab: "deploy" });
  });

  it("falls back to overview for an anchor with no tab of its own", () => {
    expect(
      resolveActionTarget(
        `/dashboard/businesses/${BUSINESS_ID}#some-future-section`,
        BUSINESS_ID
      )
    ).toEqual({ kind: "tab", tab: "overview" });
  });

  it("keeps an anchor for a different business as a plain link", () => {
    expect(
      resolveActionTarget("/dashboard/businesses/other-id#tools", BUSINESS_ID)
    ).toEqual({ kind: "internal", href: "/dashboard/businesses/other-id#tools" });
  });

  it("treats other app paths as internal links", () => {
    expect(resolveActionTarget("/intake", BUSINESS_ID)).toEqual({
      kind: "internal",
      href: "/intake",
    });
  });

  it("treats absolute urls as external links", () => {
    expect(
      resolveActionTarget("https://vercel.com/dashboard/project", BUSINESS_ID)
    ).toEqual({ kind: "external", href: "https://vercel.com/dashboard/project" });
  });

  it("rejects protocol-relative and non-path hrefs rather than linking off-app", () => {
    expect(resolveActionTarget("//evil.example.com", BUSINESS_ID)).toBeNull();
    expect(resolveActionTarget("javascript:alert(1)", BUSINESS_ID)).toBeNull();
  });
});
