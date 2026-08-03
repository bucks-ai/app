import React from "react";
import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import { ApprovalsEmptyStateNotice } from "@/components/workspace/tabs/ApprovalsPanel";

describe("ApprovalsEmptyStateNotice", () => {
  it("renders the plain empty state when no approvals are pending", () => {
    const html = renderToStaticMarkup(
      React.createElement(ApprovalsEmptyStateNotice, { state: "none" })
    );

    expect(html).toContain("No approvals pending");
    expect(html).not.toContain("Human setup required");
  });

  it("renders an amber human-required notice when the approvals schema is missing", () => {
    const html = renderToStaticMarkup(
      React.createElement(ApprovalsEmptyStateNotice, {
        state: "approvals_schema_missing",
        sqlFile: "supabase/m4a-approvals-queue.sql",
      })
    );

    expect(html).toContain("Human setup required");
    expect(html).toContain("Approvals schema missing");
    expect(html).toContain("supabase/m4a-approvals-queue.sql");
    expect(html).toContain("border-warning/30");
    expect(html).toContain("bg-warning/10");
  });
});
