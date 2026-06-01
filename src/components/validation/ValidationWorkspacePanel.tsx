"use client";

import { useCallback, useEffect, useState } from "react";
import { fetchValidationWorkspace, seedValidationWorkspace } from "@/lib/validation-client";
import type { ValidationWorkspace } from "@/types/validation-ui";
import { FeedbackNotes } from "@/components/validation/FeedbackNotes";
import { HypothesisTracker } from "@/components/validation/HypothesisTracker";
import { LeadPipeline } from "@/components/validation/LeadPipeline";
import { PersonaList } from "@/components/validation/PersonaList";
import { ValidationEmptyState } from "@/components/validation/ValidationEmptyState";
import { ValidationNextActionCard } from "@/components/validation/ValidationNextActionCard";
import { ValidationSummaryHeader } from "@/components/validation/ValidationSummaryHeader";

type ValidationWorkspacePanelProps = {
  businessId: string;
};

type LoadState = "loading" | "ready" | "empty" | "error";

export function ValidationWorkspacePanel({ businessId }: ValidationWorkspacePanelProps) {
  const [workspace, setWorkspace] = useState<ValidationWorkspace | null>(null);
  const [loadState, setLoadState] = useState<LoadState>("loading");
  const [message, setMessage] = useState<string | null>(null);
  const [seeding, setSeeding] = useState(false);

  const loadWorkspace = useCallback(async () => {
    setMessage(null);
    const result = await fetchValidationWorkspace(businessId);

    if (!result.ok) {
      setWorkspace(null);
      setLoadState("error");
      setMessage(result.error);
      return;
    }

    setWorkspace(result.data);
    setLoadState(result.data.summary.canSeed ? "empty" : "ready");
  }, [businessId]);

  useEffect(() => {
    const timer = window.setTimeout(() => {
      void loadWorkspace();
    }, 0);

    return () => {
      window.clearTimeout(timer);
    };
  }, [loadWorkspace]);

  async function handleSeed() {
    setSeeding(true);
    setMessage(null);

    const result = await seedValidationWorkspace(businessId);
    setSeeding(false);

    if (!result.ok) {
      setMessage(result.error);
      setLoadState("empty");
      return;
    }

    await loadWorkspace();
  }

  function scrollTo(id: string) {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  if (loadState === "loading") {
    return (
      <div className="space-y-3">
        <div className="h-36 animate-pulse rounded-lg border border-border bg-surface" />
        <div className="grid gap-3 lg:grid-cols-2">
          <div className="h-48 animate-pulse rounded-lg border border-border bg-surface" />
          <div className="h-48 animate-pulse rounded-lg border border-border bg-surface" />
        </div>
      </div>
    );
  }

  if (loadState === "error") {
    return (
      <div className="rounded-lg border border-error/25 bg-error/8 p-5">
        <p className="font-mono text-[10px] uppercase tracking-[0.24em] text-error">
          Validation unavailable
        </p>
        <p className="mt-3 text-sm leading-6 text-error">
          {message ?? "Customer validation could not be loaded."}
        </p>
        <button
          type="button"
          onClick={() => void loadWorkspace()}
          className="mt-4 rounded-md border border-error/35 bg-background px-3 py-2 text-xs font-semibold text-error transition-colors hover:border-error/60"
        >
          Retry
        </button>
      </div>
    );
  }

  if (loadState === "empty") {
    return (
      <div className="space-y-4">
        <ValidationEmptyState onSeed={handleSeed} loading={seeding} error={message} />
        <ValidationNextActionCard
          workspace={null}
          onCreateWorkspace={handleSeed}
          loading={seeding}
        />
      </div>
    );
  }

  if (!workspace) return null;

  return (
    <div className="space-y-4">
      <ValidationSummaryHeader workspace={workspace} />
      <ValidationNextActionCard
        workspace={workspace}
        onFocusLeads={() => scrollTo("validation-leads")}
        onFocusFeedback={() => scrollTo("validation-feedback")}
      />
      <div className="grid gap-4 xl:grid-cols-2">
        <PersonaList personas={workspace.personas} />
        <HypothesisTracker
          businessId={businessId}
          hypotheses={workspace.hypotheses}
          onChange={loadWorkspace}
        />
      </div>
      <LeadPipeline businessId={businessId} leads={workspace.leads} onChange={loadWorkspace} />
      <FeedbackNotes
        businessId={businessId}
        feedbackNotes={workspace.feedbackNotes}
        leads={workspace.leads}
        hypotheses={workspace.hypotheses}
        onChange={loadWorkspace}
      />
    </div>
  );
}
