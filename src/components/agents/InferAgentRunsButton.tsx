"use client";

import { useState } from "react";
import { inferAgentRuns } from "@/lib/agents-client";

type InferAgentRunsButtonProps = {
  businessId: string;
  disabled?: boolean;
  onInferred?: () => Promise<void> | void;
};

export function InferAgentRunsButton({
  businessId,
  disabled,
  onInferred,
}: InferAgentRunsButtonProps) {
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [tone, setTone] = useState<"success" | "warning" | "error" | null>(null);

  async function handleInfer() {
    if (loading || disabled) return;

    setLoading(true);
    setMessage(null);
    setTone(null);

    const result = await inferAgentRuns(businessId);
    setLoading(false);

    if (!result.ok) {
      setTone(result.code === "agent_runs_schema_missing" ? "warning" : "error");
      setMessage(result.error);
      return;
    }

    setTone(result.data.created > 0 ? "success" : "warning");
    setMessage(
      result.data.created > 0
        ? `Created ${result.data.created} run${result.data.created === 1 ? "" : "s"}; skipped ${result.data.skipped}.`
        : `History already up to date; skipped ${result.data.skipped}.`
    );
    await onInferred?.();
  }

  return (
    <div className="min-w-0">
      <button
        type="button"
        onClick={handleInfer}
        disabled={disabled || loading}
        className="rounded-md border border-[#4F46E5]/40 bg-[#4F46E5] px-3 py-2 text-xs font-semibold text-[#F0F0F0] transition-colors hover:bg-[#6366F1] disabled:cursor-not-allowed disabled:border-[#1C1C1C] disabled:bg-[#1C1C1C] disabled:text-[#666]"
      >
        {loading ? "Building history..." : "Build run history"}
      </button>
      {message ? (
        <p
          className={`mt-2 max-w-md break-words text-xs leading-5 ${
            tone === "success"
              ? "text-[#86EFAC]"
              : tone === "warning"
                ? "text-[#FCD34D]"
                : "text-[#FCA5A5]"
          }`}
        >
          {message}
        </p>
      ) : null}
    </div>
  );
}
