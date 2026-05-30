"use client";

import { FormEvent, useState } from "react";
import type {
  ValidationLeadRecord,
  ValidationLeadStatus,
  ValidationPriority,
} from "@/types/validation-ui";
import {
  createValidationLead,
  updateValidationLead,
} from "@/lib/validation-client";
import { ValidationStatusBadge } from "@/components/validation/ValidationStatusBadge";

type LeadPipelineProps = {
  businessId: string;
  leads: ValidationLeadRecord[];
  onChange: () => void;
};

const STATUSES: ValidationLeadStatus[] = [
  "identified",
  "contacted",
  "replied",
  "scheduled",
  "interviewed",
  "not_interested",
];
const PRIORITIES: ValidationPriority[] = ["high", "medium", "low"];

export function LeadPipeline({ businessId, leads, onChange }: LeadPipelineProps) {
  const [open, setOpen] = useState(false);
  const [name, setName] = useState("");
  const [company, setCompany] = useState("");
  const [role, setRole] = useState("");
  const [email, setEmail] = useState("");
  const [priority, setPriority] = useState<ValidationPriority>("medium");
  const [saving, setSaving] = useState(false);
  const [updatingId, setUpdatingId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!name.trim()) return;

    setSaving(true);
    setError(null);

    const result = await createValidationLead(businessId, {
      name: name.trim(),
      company: company.trim() || null,
      role: role.trim() || null,
      email: email.trim() || null,
      priority,
      source: "manual",
      status: "identified",
    });

    setSaving(false);

    if (!result.ok) {
      setError(result.error);
      return;
    }

    setName("");
    setCompany("");
    setRole("");
    setEmail("");
    setPriority("medium");
    setOpen(false);
    onChange();
  }

  async function handleStatusChange(id: string, status: ValidationLeadStatus) {
    setUpdatingId(id);
    setError(null);

    const result = await updateValidationLead(businessId, { id, status });
    setUpdatingId(null);

    if (!result.ok) {
      setError(result.error);
      return;
    }

    onChange();
  }

  const grouped = STATUSES.map((status) => ({
    status,
    leads: leads.filter((lead) => lead.status === status),
  }));

  return (
    <div id="validation-leads" className="rounded-lg border border-[#1C1C1C] bg-[#0F0F0F] p-4 scroll-mt-28">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-[#A5B4FC]">
            Lead pipeline
          </p>
          <p className="mt-1 text-xs text-[#666]">Move real discovery contacts through interview stages.</p>
        </div>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="rounded-md border border-[#4F46E5]/40 bg-[#4F46E5]/10 px-3 py-2 text-xs font-semibold text-[#C7D2FE] transition-colors hover:border-[#4F46E5]/70"
        >
          {open ? "Close" : "Add lead"}
        </button>
      </div>

      {open ? (
        <form onSubmit={handleSubmit} className="mt-3 grid gap-2 rounded border border-[#1C1C1C] bg-[#080808] p-3 md:grid-cols-2">
          <input
            value={name}
            onChange={(event) => setName(event.target.value)}
            placeholder="Name"
            className="min-h-10 rounded border border-[#1C1C1C] bg-[#141414] px-3 text-sm text-[#F0F0F0] outline-none focus:border-[#4F46E5]/70"
          />
          <input
            value={company}
            onChange={(event) => setCompany(event.target.value)}
            placeholder="Company"
            className="min-h-10 rounded border border-[#1C1C1C] bg-[#141414] px-3 text-sm text-[#F0F0F0] outline-none focus:border-[#4F46E5]/70"
          />
          <input
            value={role}
            onChange={(event) => setRole(event.target.value)}
            placeholder="Role"
            className="min-h-10 rounded border border-[#1C1C1C] bg-[#141414] px-3 text-sm text-[#F0F0F0] outline-none focus:border-[#4F46E5]/70"
          />
          <input
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="Email or contact note"
            className="min-h-10 rounded border border-[#1C1C1C] bg-[#141414] px-3 text-sm text-[#F0F0F0] outline-none focus:border-[#4F46E5]/70"
          />
          <select
            value={priority}
            onChange={(event) => setPriority(event.target.value as ValidationPriority)}
            className="min-h-10 rounded border border-[#1C1C1C] bg-[#141414] px-3 text-sm text-[#F0F0F0] outline-none focus:border-[#4F46E5]/70"
          >
            {PRIORITIES.map((value) => (
              <option key={value} value={value}>
                {value} priority
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={saving || !name.trim()}
            className="min-h-10 rounded-md border border-[#4F46E5]/45 bg-[#4F46E5]/15 px-3 text-sm font-semibold text-[#C7D2FE] transition-colors hover:border-[#4F46E5]/70 disabled:cursor-not-allowed disabled:opacity-60"
          >
            {saving ? "Adding..." : "Add lead"}
          </button>
        </form>
      ) : null}

      {error ? (
        <p className="mt-3 rounded border border-[#EF4444]/30 bg-[#EF4444]/10 px-3 py-2 text-sm leading-6 text-[#FECACA]">
          {error}
        </p>
      ) : null}

      <div className="mt-3 grid gap-2 lg:grid-cols-3">
        {grouped.map((group) => (
          <div key={group.status} className="min-w-0 rounded border border-[#1C1C1C] bg-[#080808] p-3">
            <div className="flex items-center justify-between gap-2">
              <ValidationStatusBadge value={group.status} />
              <span className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
                {group.leads.length}
              </span>
            </div>
            <div className="mt-2 space-y-2">
              {group.leads.length > 0 ? (
                group.leads.map((lead) => (
                  <div key={lead.id} className="rounded border border-[#1C1C1C] bg-[#0F0F0F] p-2.5">
                    <p className="truncate text-xs font-semibold text-[#F0F0F0]">{lead.name}</p>
                    <p className="mt-0.5 truncate text-xs text-[#666]">
                      {[lead.role, lead.company].filter(Boolean).join(", ") || "No company details"}
                    </p>
                    <div className="mt-2 flex flex-wrap items-center gap-2">
                      <ValidationStatusBadge value={lead.priority} />
                      <select
                        value={lead.status}
                        disabled={updatingId === lead.id}
                        onChange={(event) =>
                          handleStatusChange(lead.id, event.target.value as ValidationLeadStatus)
                        }
                        className="min-h-8 min-w-0 flex-1 rounded border border-[#1C1C1C] bg-[#141414] px-2 py-1.5 text-xs text-[#D4D4D4] outline-none focus:border-[#4F46E5]/70 disabled:opacity-60"
                      >
                        {STATUSES.map((status) => (
                          <option key={status} value={status}>
                            {status.replaceAll("_", " ")}
                          </option>
                        ))}
                      </select>
                    </div>
                  </div>
                ))
              ) : (
                <p className="py-4 text-xs text-[#555]">No leads here.</p>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
