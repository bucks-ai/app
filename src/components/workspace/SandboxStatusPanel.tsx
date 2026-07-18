"use client";

import { useEffect, useState } from "react";
import { StatusPill } from "@/components/ui/StatusPill";
import { fetchSandboxConfig, setSandboxConfig } from "@/lib/sandbox-client";
import type { SandboxFieldView, SandboxStatus } from "@/types/sandbox-ui";

type SandboxStatusPanelProps = {
  businessId: string;
};

type LoadState = "loading" | "ready" | "api_unavailable" | "error";

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null;
}

// The client's requestJson() returns the raw response body as `data`, i.e.
// `{ ok: true, data: { data: { sandbox } } }` — unwrap defensively the same
// way PermissionControlRoom does for the tool-permissions API.
function extractSandbox(payload: unknown): { status: SandboxStatus; fields: SandboxFieldView[] } | null {
  const outer = isRecord(payload) && isRecord(payload.data) ? payload.data : payload;
  const sandbox = isRecord(outer) ? outer.sandbox : null;
  if (!isRecord(sandbox) || !Array.isArray(sandbox.fields)) return null;

  return {
    status: (sandbox.status as SandboxStatus) ?? "unconfigured",
    fields: sandbox.fields as SandboxFieldView[],
  };
}

function statusVariant(status: SandboxStatus) {
  if (status === "configured") return "success" as const;
  if (status === "partial") return "warning" as const;
  return "neutral" as const;
}

export function SandboxStatusPanel({ businessId }: SandboxStatusPanelProps) {
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [status, setStatus] = useState<SandboxStatus>("unconfigured");
  const [fields, setFields] = useState<SandboxFieldView[]>([]);
  const [drafts, setDrafts] = useState<Record<string, string>>({});
  const [savingField, setSavingField] = useState<string | null>(null);
  const [saveError, setSaveError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      setLoadState("loading");
      const result = await fetchSandboxConfig(businessId);
      if (cancelled) return;

      if (!result.ok) {
        setLoadState(result.code === "api_unavailable" ? "api_unavailable" : "error");
        return;
      }

      const parsed = extractSandbox(result.data);
      if (!parsed) {
        setLoadState("error");
        return;
      }

      setStatus(parsed.status);
      setFields(parsed.fields);
      setLoadState("ready");
    }

    load();
    return () => {
      cancelled = true;
    };
  }, [businessId]);

  async function handleSave(field: string) {
    const value = drafts[field]?.trim();
    if (!value) return;

    setSavingField(field);
    setSaveError(null);

    const result = await setSandboxConfig(businessId, { [field]: value });
    setSavingField(null);

    if (!result.ok) {
      setSaveError(result.error);
      return;
    }

    const parsed = extractSandbox(result.data);
    if (!parsed) {
      setSaveError("Sandbox config API returned an invalid response.");
      return;
    }

    setStatus(parsed.status);
    setFields(parsed.fields);
    setDrafts((prev) => ({ ...prev, [field]: "" }));
  }

  return (
    <div className="rounded-lg border border-border bg-surface p-4">
      <div className="flex items-center justify-between gap-3">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
          Sandbox configuration
        </p>
        {loadState === "ready" && (
          <StatusPill label={status} variant={statusVariant(status)} />
        )}
      </div>
      <p className="mt-2 text-xs leading-5 text-muted">
        Names the repo, Vercel project, and secret NAMES the runner may use to
        execute missions for this business. Values shown are names only —
        actual tokens live in the runner&apos;s own env/secret store and are
        never stored or displayed here.
      </p>

      {loadState === "loading" && (
        <p className="mt-4 text-xs text-muted">Loading sandbox status…</p>
      )}

      {loadState === "api_unavailable" && (
        <p className="mt-4 text-xs text-muted">
          Sandbox config API not available yet. Merge backend branch first.
        </p>
      )}

      {loadState === "error" && (
        <p className="mt-4 text-xs text-error">
          Could not load sandbox configuration.
        </p>
      )}

      {loadState === "ready" && (
        <div className="mt-4 space-y-2">
          {fields.map((field) => (
            <div
              key={field.field}
              className="rounded border border-border bg-background px-3 py-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <div
                    className={`h-1.5 w-1.5 rounded-full ${
                      field.configured ? "bg-success" : "bg-muted"
                    }`}
                  />
                  <p className="text-xs font-medium text-secondary">
                    {field.label}
                  </p>
                </div>
                <StatusPill
                  label={field.configured ? "configured" : "unconfigured"}
                  variant={field.configured ? "success" : "neutral"}
                />
              </div>
              {field.configured ? (
                <p className="mt-1 font-mono text-xs text-muted">{field.value}</p>
              ) : (
                <div className="mt-2 flex gap-2">
                  <input
                    type="text"
                    value={drafts[field.field] ?? ""}
                    onChange={(event) =>
                      setDrafts((prev) => ({ ...prev, [field.field]: event.target.value }))
                    }
                    placeholder={`Set ${field.label.toLowerCase()}`}
                    className="w-full rounded border border-border bg-surface px-2 py-1 text-xs text-secondary outline-none focus:border-accent"
                  />
                  <button
                    type="button"
                    onClick={() => handleSave(field.field)}
                    disabled={savingField === field.field || !drafts[field.field]?.trim()}
                    className="shrink-0 rounded border border-border bg-elevated px-3 py-1 text-xs font-medium text-secondary disabled:opacity-50"
                  >
                    {savingField === field.field ? "Saving…" : "Save"}
                  </button>
                </div>
              )}
            </div>
          ))}
          {saveError && <p className="text-xs text-error">{saveError}</p>}
        </div>
      )}
    </div>
  );
}
