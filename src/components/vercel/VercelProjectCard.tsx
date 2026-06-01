"use client";

import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import { createVercelProject } from "@/lib/vercel-client";
import type {
  VercelCreateProjectState,
  VercelProjectResult as VercelProjectResultData,
} from "@/types/vercel-ui";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";
import { VercelProjectResult } from "@/components/vercel/VercelProjectResult";

type VercelProjectCardProps = {
  businessId: string;
  businessName: string;
  oneLineIdea?: string | null;
  existingProject?: VercelProjectResultData | null;
};

const initialState: VercelCreateProjectState = {
  status: "idle",
  result: null,
  error: null,
  warning: null,
};

function projectNameFromBusinessName(name: string) {
  const normalized = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);

  return normalized || "bucks-ai-project";
}

function friendlyDetailForError(code?: string) {
  if (code === "api_unavailable") {
    return "The frontend is ready, but the backend deployment routes are not merged here yet.";
  }

  if (code === "missing_vercel_env" || code === "vercel_token_missing") {
    return "Configure the server-side Vercel token before trying again.";
  }

  if (code === "github_repo_missing") {
    return "Deployment starts from the recorded GitHub repository.";
  }

  if (code === "vercel_not_approved" || code === "vercel_permission_missing") {
    return "This protects founders from accidental project creation in external tools.";
  }

  return "Review Vercel access, team permissions, and GitHub integration access before retrying.";
}

export function VercelProjectCard({
  businessId,
  businessName,
  oneLineIdea,
  existingProject,
}: VercelProjectCardProps) {
  const defaultProjectName = useMemo(
    () => projectNameFromBusinessName(businessName),
    [businessName]
  );
  const [projectName, setProjectName] = useState(defaultProjectName);
  const [prepareScaffold, setPrepareScaffold] = useState(true);
  const [attemptInitialDeployment, setAttemptInitialDeployment] = useState(true);
  const [state, setState] = useState<VercelCreateProjectState>(initialState);

  const activeResult = state.status === "success" ? state.result : existingProject;
  const projectNameIsValid = projectName.trim().length > 0;
  const isLoading = state.status === "loading";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!projectNameIsValid || isLoading) return;

    setState({
      status: "loading",
      result: null,
      error: null,
      warning: null,
    });

    const result = await createVercelProject({
      businessId,
      projectName: projectName.trim(),
      prepareScaffold,
      attemptInitialDeployment,
    });

    if (!result.ok) {
      setState({
        status: "error",
        result: null,
        error: result.error,
        warning: null,
        code: result.code,
      });
      return;
    }

    setState({
      status: "success",
      result: result.data,
      error: null,
      warning: result.warning ?? null,
    });
  }

  if (activeResult) {
    return (
      <VercelProjectResult
        result={activeResult}
        warning={state.status === "success" ? state.warning : null}
      />
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-lg border border-border bg-background p-5"
    >
      <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
        <div className="max-w-2xl">
          <div className="flex flex-wrap items-center gap-3">
            <SectionLabel tone="warning">External action</SectionLabel>
            <StatusPill label="Creates real project" variant="warning" />
          </div>
          <h3 className="mt-4 text-2xl font-semibold tracking-tight text-foreground">
            Create the Vercel deployment project.
          </h3>
          <p className="mt-3 text-sm leading-7 text-secondary">
            This creates a real Vercel project using a server-side Vercel token.
            The generated app contains no secrets, no custom domain, no payments,
            no emails, and no production customer data.
          </p>
          {oneLineIdea ? (
            <p className="mt-3 rounded-md border border-border bg-surface p-3 text-sm leading-6 text-secondary">
              {oneLineIdea}
            </p>
          ) : null}
        </div>
      </div>

      <label className="mt-6 block">
        <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-secondary">
          Vercel project name
        </span>
        <input
          value={projectName}
          onChange={(event) => setProjectName(event.target.value)}
          className="mt-2 w-full rounded-md border border-border bg-surface px-4 py-3 text-sm text-foreground outline-none transition-colors placeholder:text-muted focus:border-accent/70"
          placeholder={defaultProjectName}
          aria-invalid={!projectNameIsValid}
        />
      </label>

      <div className="mt-5 grid gap-3">
        <label className="flex gap-3 rounded-md border border-border bg-surface p-4 text-sm leading-6 text-secondary">
          <input
            type="checkbox"
            checked={prepareScaffold}
            onChange={(event) => setPrepareScaffold(event.target.checked)}
            className="mt-1 h-4 w-4 accent-accent"
          />
          <span>Prepare deployable Next.js starter before creating project</span>
        </label>
        <label className="flex gap-3 rounded-md border border-border bg-surface p-4 text-sm leading-6 text-secondary">
          <input
            type="checkbox"
            checked={attemptInitialDeployment}
            onChange={(event) => setAttemptInitialDeployment(event.target.checked)}
            className="mt-1 h-4 w-4 accent-accent"
          />
          <span>Attempt initial deployment if supported</span>
        </label>
      </div>

      <div className="mt-5 rounded-md border border-warning/30 bg-warning/10 p-4">
        <StatusPill label="External action warning" variant="warning" />
        <ul className="mt-3 space-y-2 text-sm leading-6 text-warning">
          <li>This creates a real Vercel project.</li>
          <li>It uses a server-side Vercel token.</li>
          <li>It does not copy the current app&apos;s secrets.</li>
          <li>It does not create a custom domain.</li>
          <li>It does not create payments or send emails.</li>
          <li>It is approval-gated by the Vercel tool permission.</li>
        </ul>
      </div>

      {state.status === "error" ? (
        <div className="mt-5 rounded-md border border-error/30 bg-error/10 p-4">
          <StatusPill label="Create blocked" variant="danger" />
          <p className="mt-3 text-sm font-semibold text-error">{state.error}</p>
          <p className="mt-2 text-sm leading-6 text-error">
            {friendlyDetailForError(state.code)}
          </p>
        </div>
      ) : null}

      <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <p className="text-sm leading-6 text-secondary">
          bucks.ai will not create the project unless Vercel is approved in the
          setup queue.
        </p>
        <button
          type="submit"
          disabled={!projectNameIsValid || isLoading}
          className="rounded-md bg-accent px-5 py-3 text-sm font-semibold text-accent-contrast transition-colors hover:bg-accent-hover disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isLoading ? "Creating Vercel project..." : "Create Vercel project"}
        </button>
      </div>
    </form>
  );
}
