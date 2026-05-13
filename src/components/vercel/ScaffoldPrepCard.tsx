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
    <div className="rounded-lg border border-[#1C1C1C] bg-[#080808] p-5">
      <div className="flex flex-wrap items-center gap-3">
        <SectionLabel>Starter scaffold</SectionLabel>
        <StatusPill label="GitHub write" variant="warning" />
      </div>
      <h3 className="mt-4 text-xl font-semibold tracking-tight text-[#F0F0F0]">
        Prepare a deployable Next.js starter.
      </h3>
      <p className="mt-3 text-sm leading-7 text-[#888888]">
        This writes a minimal deployable app to the recorded GitHub repo. It does
        not copy the current app&apos;s secrets or production customer data.
      </p>

      <div className="mt-5 grid gap-2 sm:grid-cols-2">
        {scaffoldFiles.map((file) => (
          <div
            key={file}
            className="rounded-md border border-[#1C1C1C] bg-[#0F0F0F] px-3 py-2 font-mono text-xs text-[#D4D4D4]"
          >
            {file}
          </div>
        ))}
      </div>

      {state?.ok ? (
        <div className="mt-5 rounded-md border border-[#22C55E]/25 bg-[#22C55E]/10 p-4">
          <StatusPill label="Scaffold prepared" variant="success" />
          <p className="mt-3 text-sm leading-6 text-[#D4D4D4]">
            Starter files were written to GitHub
            {state.data.repoFullName ? ` for ${state.data.repoFullName}` : ""}.
          </p>
          {state.warning ? (
            <p className="mt-3 text-sm leading-6 text-[#FDE68A]">{state.warning}</p>
          ) : null}
        </div>
      ) : null}

      {state && !state.ok ? (
        <div className="mt-5 rounded-md border border-[#EF4444]/30 bg-[#EF4444]/10 p-4">
          <StatusPill label="Scaffold blocked" variant="danger" />
          <p className="mt-3 text-sm font-semibold text-[#FCA5A5]">{state.error}</p>
        </div>
      ) : null}

      <div className="mt-5 flex justify-end">
        <button
          type="button"
          onClick={handlePrepare}
          disabled={isLoading}
          className="rounded-md border border-[#4F46E5]/45 bg-[#080808] px-4 py-3 text-sm font-semibold text-[#C7D2FE] transition-colors hover:border-[#4F46E5]/75 hover:text-[#F0F0F0] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isLoading ? "Preparing scaffold..." : "Prepare starter scaffold"}
        </button>
      </div>
    </div>
  );
}
