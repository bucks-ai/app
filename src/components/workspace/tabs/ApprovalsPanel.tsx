"use client";

import { useEffect, useState } from "react";
import { fetchPendingApprovals, updateApproval } from "@/lib/approval-client";
import {
  APPROVALS_SCHEMA_SQL_FILE,
  type ApprovalAction,
  type ApprovalsEmptyState,
} from "@/types/approval-ui";
import type { ApprovalRecord } from "@/types/database";

const REQUEST_TYPE_LABEL: Record<string, string> = {
  merge_approval: "Merge approval",
  sql_approval: "SQL approval",
  resource_request: "Resource request",
  strategic_review: "Strategic review",
};

export function ApprovalsPanel() {
  const [approvals, setApprovals] = useState<ApprovalRecord[]>([]);
  const [emptyState, setEmptyState] = useState<ApprovalsEmptyState>("none");
  const [sqlFile, setSqlFile] = useState(APPROVALS_SCHEMA_SQL_FILE);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [pendingActionId, setPendingActionId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const result = await fetchPendingApprovals();
      if (cancelled) return;

      if (!result.ok) {
        // api_unavailable (route not merged yet) degrades silently, same as
        // an empty queue — nothing pending for the founder to act on.
        if (result.code !== "api_unavailable") {
          setError(result.error);
        }
        setLoading(false);
        return;
      }

      const data = result.data.data;
      setApprovals(data.approvals);
      setEmptyState(data.emptyState ?? "none");
      setSqlFile(data.sqlFile ?? APPROVALS_SCHEMA_SQL_FILE);
      setLoading(false);
    }

    load();
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleDecision(id: string, action: ApprovalAction) {
    setPendingActionId(id);
    const result = await updateApproval(id, action);
    setPendingActionId(null);

    if (!result.ok) {
      setError(result.error);
      return;
    }

    // The row may come back still "pending" if another channel (Slack) lost
    // the race, or "approved"/"rejected" on success — either way it's no
    // longer actionable here, so drop it from the pending list.
    setApprovals((current) => current.filter((a) => a.id !== id));
  }

  if (loading) {
    return null;
  }

  return (
    <div className="mb-5 space-y-3">
      <p className="font-mono text-xs uppercase tracking-[0.24em] text-muted-foreground">
        Approvals
      </p>
      {error ? (
        <div className="rounded-xl bg-error/10 p-4 text-xs leading-5 text-error">
          {error}
        </div>
      ) : null}
      {!error && approvals.length === 0 ? (
        <ApprovalsEmptyStateNotice state={emptyState} sqlFile={sqlFile} />
      ) : null}
      {approvals.map((approval) => (
        <div
          key={approval.id}
          className="rounded-r-xl border-l-2 border-status-pending/50 bg-status-pending/[0.07] py-4 pl-5 pr-4"
        >
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div className="min-w-0 flex-1">
              <div className="flex flex-wrap items-center gap-2">
                <span className="rounded-full bg-warning/12 px-2.5 py-1 font-mono text-[11px] uppercase tracking-[0.18em] text-warning">
                  {REQUEST_TYPE_LABEL[approval.request_type] ?? approval.request_type}
                </span>
                <h3 className="text-sm font-medium text-foreground">{approval.title}</h3>
                <span className="font-mono text-[11px] text-muted-foreground">{approval.request_id}</span>
              </div>
              {approval.body ? (
                <pre className="mt-1.5 whitespace-pre-wrap break-words text-xs leading-5 text-foreground-secondary">
                  {approval.body}
                </pre>
              ) : null}
            </div>
            <div className="flex shrink-0 gap-2">
              <button
                type="button"
                onClick={() => handleDecision(approval.id, "approve")}
                disabled={pendingActionId === approval.id}
                className="min-h-11 rounded-xl bg-accent/12 px-3.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.18em] text-accent-on-tint transition-colors hover:bg-accent/20 disabled:opacity-50"
              >
                Approve
              </button>
              <button
                type="button"
                onClick={() => handleDecision(approval.id, "reject")}
                disabled={pendingActionId === approval.id}
                className="min-h-11 rounded-xl bg-error/12 px-3.5 py-1.5 font-mono text-[11px] uppercase tracking-[0.18em] text-error transition-colors hover:bg-error/20 disabled:opacity-50"
              >
                Reject
              </button>
            </div>
          </div>
        </div>
      ))}
    </div>
  );
}

export function ApprovalsEmptyStateNotice({
  state,
  sqlFile = APPROVALS_SCHEMA_SQL_FILE,
}: {
  state: ApprovalsEmptyState;
  sqlFile?: string;
}) {
  if (state === "approvals_schema_missing") {
    return (
      <div className="rounded-r-xl border-l-2 border-status-pending/50 bg-status-pending/[0.07] py-4 pl-5 pr-4 text-left">
        <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-warning">
          Human setup required
        </p>
        <p className="mt-2 text-sm font-medium text-foreground">
          Approvals schema missing
        </p>
        <p className="mt-1.5 text-sm leading-6 text-foreground-secondary">
          Apply <span className="font-mono text-warning">{sqlFile}</span> before
          in-app approvals can sync with the runner.
        </p>
      </div>
    );
  }

  return (
    <div className="flow-well p-4 text-sm text-muted-foreground">
      No approvals pending
    </div>
  );
}
