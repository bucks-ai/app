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
  const [editingFields, setEditingFields] = useState<Record<string, boolean>>({});

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
    setEditingFields((prev) => ({ ...prev, [field]: false }));
  }

  function startEditing(field: string, currentValue: string | null) {
    setSaveError(null);
    setDrafts((prev) => ({ ...prev, [field]: currentValue ?? "" }));
    setEditingFields((prev) => ({ ...prev, [field]: true }));
  }

  function cancelEditing(field: string) {
    setSaveError(null);
    setDrafts((prev) => ({ ...prev, [field]: "" }));
    setEditingFields((prev) => ({ ...prev, [field]: false }));
  }

  return (
    <div className="solid-surface rounded-card p-5">
      <div className="flex items-center justify-between gap-3">
        <p className="font-mono text-[11px] uppercase tracking-[0.24em] text-accent">
          Sandbox configuration
        </p>
        {loadState === "ready" && (
          <StatusPill label={status} variant={statusVariant(status)} />
        )}
      </div>
      <p className="mt-2 text-xs leading-5 text-muted-foreground">
        Names the repo, Vercel project, and secret NAMES the runner may use to
        execute missions for this business. Values shown are names only —
        actual tokens live in the runner&apos;s own env/secret store and are
        never stored or displayed here.
      </p>

      {loadState === "loading" && (
        <p className="mt-4 text-xs text-muted-foreground">Loading sandbox status…</p>
      )}

      {loadState === "api_unavailable" && (
        <p className="mt-4 text-xs text-muted-foreground">
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
              className="flow-well px-4 py-3.5"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <div
                    className={`h-1.5 w-1.5 rounded-full ${
                      field.configured ? "bg-success" : "bg-muted"
                    }`}
                  />
                  <p className="text-xs font-medium text-foreground-secondary">
                    {field.label}
                  </p>
                </div>
                <StatusPill
                  label={field.configured ? "configured" : "unconfigured"}
                  variant={field.configured ? "success" : "neutral"}
                />
              </div>
              {field.configured && !editingFields[field.field] ? (
                <div className="mt-1 flex items-center justify-between gap-2">
                  <p className="font-mono text-xs text-muted-foreground">{field.value}</p>
                  <button
                    type="button"
                    onClick={() => startEditing(field.field, field.value)}
                    className="min-h-11 shrink-0 rounded-lg bg-muted px-2.5 py-1 text-[11px] font-medium text-foreground-secondary transition-colors hover:bg-accent/12 hover:text-accent-on-tint"
                  >
                    Change
                  </button>
                </div>
              ) : (
                <div className="mt-2 flex gap-2">
                  <input
                    type="text"
                    value={drafts[field.field] ?? ""}
                    onChange={(event) =>
                      setDrafts((prev) => ({ ...prev, [field.field]: event.target.value }))
                    }
                    placeholder={`Set ${field.label.toLowerCase()}`}
                    className="min-h-11 w-full rounded-lg border border-[var(--input-border)] bg-muted px-3 py-1.5 text-xs text-foreground outline-none transition-all duration-200 focus:border-accent/60 focus:shadow-[0_0_0_3px_var(--accent-soft)]"
                    autoFocus={field.configured}
                  />
                  <button
                    type="button"
                    onClick={() => handleSave(field.field)}
                    disabled={savingField === field.field || !drafts[field.field]?.trim()}
                    className="min-h-11 shrink-0 rounded-lg bg-accent/12 px-3.5 py-1.5 text-xs font-medium text-accent-on-tint transition-colors hover:bg-accent/20 disabled:opacity-50"
                  >
                    {savingField === field.field ? "Saving…" : "Save"}
                  </button>
                  {field.configured && (
                    <button
                      type="button"
                      onClick={() => cancelEditing(field.field)}
                      disabled={savingField === field.field}
                      className="min-h-11 shrink-0 rounded-lg px-3 py-1.5 text-xs text-muted-foreground transition-colors hover:text-foreground disabled:opacity-50"
                    >
                      Cancel
                    </button>
                  )}
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
