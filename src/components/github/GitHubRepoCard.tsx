"use client";

import type { FormEvent } from "react";
import { useMemo, useState } from "react";
import { GitHubRepoResult } from "@/components/github/GitHubRepoResult";
import { createGitHubRepo } from "@/lib/github-client";
import type {
  GitHubCreateRepoState,
  GitHubRepoResult as GitHubRepoResultData,
  GitHubRepoVisibility,
} from "@/types/github-ui";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";

type GitHubRepoCardProps = {
  businessId: string;
  businessName: string;
  oneLineIdea?: string | null;
  existingRepo?: GitHubRepoResultData | null;
};

const initialState: GitHubCreateRepoState = {
  status: "idle",
  result: null,
  error: null,
  warning: null,
};

function repoNameFromBusinessName(name: string) {
  const normalized = name
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, 80);

  return normalized || "bucks-ai-business";
}

function friendlyDetailForError(code?: string) {
  if (code === "api_unavailable") {
    return "The frontend is ready, but the backend route from the other branch is not merged here yet.";
  }

  if (
    code === "permission_required" ||
    code === "permission_missing" ||
    code === "github_permission_required"
  ) {
    return "This protects founders from accidental external asset creation.";
  }

  if (code === "github_token_missing" || code === "token_missing") {
    return "Configure the server-side GitHub token before trying again.";
  }

  return "Review the setup queue and try again once the backend confirms it can create the repo.";
}

export function GitHubRepoCard({
  businessId,
  businessName,
  oneLineIdea,
  existingRepo,
}: GitHubRepoCardProps) {
  const defaultRepoName = useMemo(
    () => repoNameFromBusinessName(businessName),
    [businessName]
  );
  const [repoName, setRepoName] = useState(defaultRepoName);
  const [visibility, setVisibility] = useState<GitHubRepoVisibility>("private");
  const [includeStarterFiles, setIncludeStarterFiles] = useState(true);
  const [state, setState] = useState<GitHubCreateRepoState>(initialState);
  const [showCreateAnother, setShowCreateAnother] = useState(!existingRepo);

  const activeResult = state.status === "success" ? state.result : existingRepo;
  const repoNameIsValid = repoName.trim().length > 0;
  const isLoading = state.status === "loading";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!repoNameIsValid || isLoading) return;

    setState({
      status: "loading",
      result: null,
      error: null,
      warning: null,
    });

    const result = await createGitHubRepo({
      businessId,
      repoName: repoName.trim(),
      visibility,
      includeStarterFiles,
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
    setShowCreateAnother(false);
  }

  return (
    <div className="space-y-5">
      {activeResult ? (
        <GitHubRepoResult
          result={activeResult}
          warning={state.status === "success" ? state.warning : null}
          description={
            existingRepo && state.status !== "success"
              ? "This business already has a recorded GitHub repository. No duplicate create action is shown unless you expand the form below."
              : undefined
          }
        />
      ) : null}

      {activeResult && !showCreateAnother ? (
        <button
          type="button"
          onClick={() => setShowCreateAnother(true)}
          className="rounded-md border border-[#1C1C1C] bg-[#080808] px-4 py-3 text-sm font-semibold text-[#D4D4D4] transition-colors hover:border-[#4F46E5]/60 hover:text-[#F0F0F0]"
        >
          Create another repo
        </button>
      ) : null}

      {showCreateAnother ? (
        <form
          onSubmit={handleSubmit}
          className="rounded-lg border border-[#1C1C1C] bg-[#080808] p-5"
        >
          <div className="flex flex-col gap-4 lg:flex-row lg:items-start lg:justify-between">
            <div className="max-w-2xl">
              <div className="flex flex-wrap items-center gap-3">
                <SectionLabel tone="warning">External action</SectionLabel>
                <StatusPill label="Private by default" variant="warning" />
              </div>
              <h3 className="mt-4 text-2xl font-semibold tracking-tight text-[#F0F0F0]">
                Create the first GitHub repository.
              </h3>
              <p className="mt-3 text-sm leading-7 text-[#888888]">
                This creates a real GitHub repo using the server-side dev token.
                No production app code is generated, no deployment is triggered,
                and no billing or payment action happens.
              </p>
              {oneLineIdea ? (
                <p className="mt-3 rounded-md border border-[#1C1C1C] bg-[#0F0F0F] p-3 text-sm leading-6 text-[#D4D4D4]">
                  {oneLineIdea}
                </p>
              ) : null}
            </div>
          </div>

          <div className="mt-6 grid gap-5 lg:grid-cols-[1fr_0.7fr]">
            <label className="block">
              <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#888888]">
                Repository name
              </span>
              <input
                value={repoName}
                onChange={(event) => setRepoName(event.target.value)}
                className="mt-2 w-full rounded-md border border-[#1C1C1C] bg-[#0F0F0F] px-4 py-3 text-sm text-[#F0F0F0] outline-none transition-colors placeholder:text-[#444444] focus:border-[#4F46E5]/70"
                placeholder={defaultRepoName}
                aria-invalid={!repoNameIsValid}
              />
            </label>

            <fieldset>
              <legend className="font-mono text-[11px] uppercase tracking-[0.18em] text-[#888888]">
                Visibility
              </legend>
              <div className="mt-2 grid grid-cols-2 rounded-md border border-[#1C1C1C] bg-[#0F0F0F] p-1">
                {(["private", "public"] as GitHubRepoVisibility[]).map((option) => (
                  <button
                    key={option}
                    type="button"
                    onClick={() => setVisibility(option)}
                    className={`rounded px-3 py-2 text-sm font-semibold transition-colors ${
                      visibility === option
                        ? "bg-[#4F46E5] text-[#F0F0F0]"
                        : "text-[#888888] hover:text-[#F0F0F0]"
                    }`}
                  >
                    {option === "private" ? "Private" : "Public"}
                  </button>
                ))}
              </div>
            </fieldset>
          </div>

          <label className="mt-5 flex gap-3 rounded-md border border-[#1C1C1C] bg-[#0F0F0F] p-4 text-sm leading-6 text-[#D4D4D4]">
            <input
              type="checkbox"
              checked={includeStarterFiles}
              onChange={(event) => setIncludeStarterFiles(event.target.checked)}
              className="mt-1 h-4 w-4 accent-[#4F46E5]"
            />
            <span>Add starter README/package files</span>
          </label>

          {state.status === "error" ? (
            <div className="mt-5 rounded-md border border-[#EF4444]/30 bg-[#EF4444]/10 p-4">
              <StatusPill label="Create blocked" variant="danger" />
              <p className="mt-3 text-sm font-semibold text-[#FCA5A5]">{state.error}</p>
              <p className="mt-2 text-sm leading-6 text-[#FECACA]">
                {friendlyDetailForError(state.code)}
              </p>
            </div>
          ) : null}

          <div className="mt-6 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm leading-6 text-[#888888]">
              Founder approval is required before bucks.ai creates external
              assets.
            </p>
            <button
              type="submit"
              disabled={!repoNameIsValid || isLoading}
              className="rounded-md bg-[#4F46E5] px-5 py-3 text-sm font-semibold text-[#F0F0F0] transition-colors hover:bg-[#6366F1] disabled:cursor-not-allowed disabled:opacity-50"
            >
              {isLoading ? "Creating repo..." : "Create GitHub repo"}
            </button>
          </div>
        </form>
      ) : null}
    </div>
  );
}
