"use client";

import { FormEvent, useState } from "react";
import type {
  ValidationFeedbackNoteRecord,
  ValidationHypothesisRecord,
  ValidationLeadRecord,
  ValidationSignalStrength,
} from "@/types/validation-ui";
import { createValidationFeedbackNote } from "@/lib/validation-client";
import { ValidationStatusBadge } from "@/components/validation/ValidationStatusBadge";

type FeedbackNotesProps = {
  businessId: string;
  feedbackNotes: ValidationFeedbackNoteRecord[];
  leads: ValidationLeadRecord[];
  hypotheses: ValidationHypothesisRecord[];
  onChange: () => void;
};

const SIGNALS: ValidationSignalStrength[] = ["weak", "medium", "strong"];

export function FeedbackNotes({
  businessId,
  feedbackNotes,
  leads,
  hypotheses,
  onChange,
}: FeedbackNotesProps) {
  const [open, setOpen] = useState(false);
  const [summary, setSummary] = useState("");
  const [leadId, setLeadId] = useState("");
  const [hypothesisId, setHypothesisId] = useState("");
  const [painSignal, setPainSignal] = useState("");
  const [willingnessSignal, setWillingnessSignal] = useState("");
  const [nextStep, setNextStep] = useState("");
  const [signalStrength, setSignalStrength] = useState<ValidationSignalStrength | "">("");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!summary.trim()) return;

    setSaving(true);
    setError(null);

    const result = await createValidationFeedbackNote(businessId, {
      summary: summary.trim(),
      lead_id: leadId || null,
      hypothesis_id: hypothesisId || null,
      pain_signal: painSignal.trim() || null,
      willingness_to_pay_signal: willingnessSignal.trim() || null,
      next_step: nextStep.trim() || null,
      signal_strength: signalStrength || null,
    });

    setSaving(false);

    if (!result.ok) {
      setError(result.error);
      return;
    }

    setSummary("");
    setLeadId("");
    setHypothesisId("");
    setPainSignal("");
    setWillingnessSignal("");
    setNextStep("");
    setSignalStrength("");
    setOpen(false);
    onChange();
  }

  function leadName(id: string | null) {
    if (!id) return null;
    return leads.find((lead) => lead.id === id)?.name ?? null;
  }

  function hypothesisTitle(id: string | null) {
    if (!id) return null;
    return hypotheses.find((hypothesis) => hypothesis.id === id)?.title ?? null;
  }

  return (
    <div id="validation-feedback" className="rounded-lg border border-border bg-surface p-4 scroll-mt-28">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-accent">
            Feedback notes
          </p>
          <p className="mt-1 text-xs text-muted">Capture the evidence from discovery calls.</p>
        </div>
        <button
          type="button"
          onClick={() => setOpen((value) => !value)}
          className="rounded-md border border-accent/40 bg-accent/10 px-3 py-2 text-xs font-semibold text-accent transition-colors hover:border-accent/70"
        >
          {open ? "Close" : "Add feedback"}
        </button>
      </div>

      {open ? (
        <form onSubmit={handleSubmit} className="mt-3 grid gap-2 rounded border border-border bg-background p-3 md:grid-cols-2">
          <textarea
            value={summary}
            onChange={(event) => setSummary(event.target.value)}
            placeholder="Customer said..."
            rows={4}
            className="min-h-28 rounded border border-border bg-elevated px-3 py-2 text-sm text-foreground outline-none focus:border-accent/70 md:col-span-2"
          />
          <select
            value={leadId}
            onChange={(event) => setLeadId(event.target.value)}
            className="min-h-10 rounded border border-border bg-elevated px-3 text-sm text-foreground outline-none focus:border-accent/70"
          >
            <option value="">No lead attached</option>
            {leads.map((lead) => (
              <option key={lead.id} value={lead.id}>
                {lead.name}
              </option>
            ))}
          </select>
          <select
            value={hypothesisId}
            onChange={(event) => setHypothesisId(event.target.value)}
            className="min-h-10 rounded border border-border bg-elevated px-3 text-sm text-foreground outline-none focus:border-accent/70"
          >
            <option value="">No hypothesis attached</option>
            {hypotheses.map((hypothesis) => (
              <option key={hypothesis.id} value={hypothesis.id}>
                {hypothesis.title}
              </option>
            ))}
          </select>
          <input
            value={painSignal}
            onChange={(event) => setPainSignal(event.target.value)}
            placeholder="Pain signal"
            className="min-h-10 rounded border border-border bg-elevated px-3 text-sm text-foreground outline-none focus:border-accent/70"
          />
          <input
            value={willingnessSignal}
            onChange={(event) => setWillingnessSignal(event.target.value)}
            placeholder="Willingness to pay"
            className="min-h-10 rounded border border-border bg-elevated px-3 text-sm text-foreground outline-none focus:border-accent/70"
          />
          <input
            value={nextStep}
            onChange={(event) => setNextStep(event.target.value)}
            placeholder="Next step"
            className="min-h-10 rounded border border-border bg-elevated px-3 text-sm text-foreground outline-none focus:border-accent/70"
          />
          <select
            value={signalStrength}
            onChange={(event) =>
              setSignalStrength(event.target.value as ValidationSignalStrength | "")
            }
            className="min-h-10 rounded border border-border bg-elevated px-3 text-sm text-foreground outline-none focus:border-accent/70"
          >
            <option value="">No signal rating</option>
            {SIGNALS.map((signal) => (
              <option key={signal} value={signal}>
                {signal} signal
              </option>
            ))}
          </select>
          <button
            type="submit"
            disabled={saving || !summary.trim()}
            className="min-h-10 rounded-md border border-accent/45 bg-accent/15 px-3 text-sm font-semibold text-accent transition-colors hover:border-accent/70 disabled:cursor-not-allowed disabled:opacity-60 md:col-span-2"
          >
            {saving ? "Adding..." : "Add feedback"}
          </button>
        </form>
      ) : null}

      {error ? (
        <p className="mt-3 rounded border border-error/30 bg-error/10 px-3 py-2 text-sm leading-6 text-error">
          {error}
        </p>
      ) : null}

      <div className="mt-3 space-y-2">
        {feedbackNotes.length > 0 ? (
          feedbackNotes.map((note) => (
            <div key={note.id} className="rounded border border-border bg-background p-3">
              <div className="flex flex-wrap items-start justify-between gap-2">
                <p className="min-w-0 text-sm leading-6 text-secondary">{note.summary}</p>
                {note.signal_strength ? (
                  <ValidationStatusBadge value={note.signal_strength} />
                ) : null}
              </div>
              <div className="mt-2 flex flex-wrap gap-2 text-xs text-muted">
                {leadName(note.lead_id) ? <span>Lead: {leadName(note.lead_id)}</span> : null}
                {hypothesisTitle(note.hypothesis_id) ? (
                  <span>Hypothesis: {hypothesisTitle(note.hypothesis_id)}</span>
                ) : null}
                {note.pain_signal ? <span>Pain: {note.pain_signal}</span> : null}
                {note.willingness_to_pay_signal ? (
                  <span>WTP: {note.willingness_to_pay_signal}</span>
                ) : null}
                {note.next_step ? <span>Next: {note.next_step}</span> : null}
              </div>
            </div>
          ))
        ) : (
          <p className="rounded border border-border bg-background px-3 py-4 text-sm text-muted">
            No feedback yet.
          </p>
        )}
      </div>
    </div>
  );
}
