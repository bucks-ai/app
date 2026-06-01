"use client";

import { useState } from "react";
import { prepareNextScaffold } from "@/lib/vercel-client";
import type { PrepareScaffoldResponse } from "@/types/vercel-ui";
import { SectionLabel } from "@/components/ui/SectionLabel";
import { StatusPill } from "@/components/ui/StatusPill";

type ScaffoldPrepCardProps = {
  businessId: string;
};

const scaffoldFiles = [
  "package.json",
  "next.config.ts",
  "tsconfig.json",
  "src/app/layout.tsx",
  "src/app/page.tsx",
  "src/app/globals.css",
  "README.md",
];

export function ScaffoldPrepCard({ businessId }: ScaffoldPrepCardProps) {
  const [state, setState] = useState<PrepareScaffoldResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);

  async function handlePrepare() {
    if (isLoading) return;

    setIsLoading(true);
    const result = await prepareNextScaffold({ businessId });
    setState(result);
    setIsLoading(false);
  }

  return (
    <div className="rounded-lg border border-border bg-background p-5">
      <div className="flex flex-wrap items-center gap-3">
        <SectionLabel>Starter scaffold</SectionLabel>
        <StatusPill label="GitHub write" variant="warning" />
      </div>
      <h3 className="mt-4 text-xl font-semibold tracking-tight text-foreground">
        Prepare a deployable Next.js starter.
      </h3>
      <p className="mt-3 text-sm leading-7 text-secondary">
        This writes a minimal deployable app to the recorded GitHub repo. It does
        not copy the current app&apos;s secrets or production customer data.
      </p>

      <div className="mt-5 grid gap-2 sm:grid-cols-2">
        {scaffoldFiles.map((file) => (
          <div
            key={file}
            className="rounded-md border border-border bg-surface px-3 py-2 font-mono text-xs text-secondary"
          >
            {file}
          </div>
        ))}
      </div>

      {state?.ok ? (
        <div className="mt-5 rounded-md border border-success/25 bg-success/10 p-4">
          <StatusPill label="Scaffold prepared" variant="success" />
          <p className="mt-3 text-sm leading-6 text-secondary">
            Starter files were written to GitHub
            {state.data.repoFullName ? ` for ${state.data.repoFullName}` : ""}.
          </p>
          {state.warning ? (
            <p className="mt-3 text-sm leading-6 text-warning">{state.warning}</p>
          ) : null}
        </div>
      ) : null}

      {state && !state.ok ? (
        <div className="mt-5 rounded-md border border-error/30 bg-error/10 p-4">
          <StatusPill label="Scaffold blocked" variant="danger" />
          <p className="mt-3 text-sm font-semibold text-error">{state.error}</p>
        </div>
      ) : null}

      <div className="mt-5 flex justify-end">
        <button
          type="button"
          onClick={handlePrepare}
          disabled={isLoading}
          className="rounded-md border border-accent/45 bg-background px-4 py-3 text-sm font-semibold text-accent transition-colors hover:border-accent/75 hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isLoading ? "Preparing scaffold..." : "Prepare starter scaffold"}
        </button>
      </div>
    </div>
  );
}
