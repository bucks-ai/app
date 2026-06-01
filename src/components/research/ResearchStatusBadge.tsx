import type {
  ResearchConfidence,
  ResearchPriority,
  ResearchStatus,
} from "@/types/research-ui";

type BadgeTone = "accent" | "success" | "warning" | "danger" | "neutral";

type ResearchStatusBadgeProps = {
  label?: string;
  value:
    | ResearchStatus
    | ResearchConfidence
    | ResearchPriority
    | string
    | null
    | undefined;
  tone?: BadgeTone;
  className?: string;
};

const toneClasses: Record<BadgeTone, string> = {
  accent: "border-accent/35 bg-accent/10 text-accent",
  success: "border-success/25 bg-success/10 text-success",
  warning: "border-warning/35 bg-warning/10 text-warning",
  danger: "border-error/35 bg-error/10 text-error",
  neutral: "border-border bg-elevated text-secondary",
};

const valueTone: Record<string, BadgeTone> = {
  not_started: "neutral",
  researching: "accent",
  draft: "accent",
  reviewed: "success",
  ready_for_validation: "success",
  needs_more_research: "warning",
  assumption: "neutral",
  weak_signal: "neutral",
  medium_signal: "accent",
  strong_signal: "success",
  validated: "success",
  invalidated: "danger",
  high: "warning",
  medium: "accent",
  low: "neutral",
  critical: "danger",
};

export function researchLabel(value: string | null | undefined) {
  if (!value) return "Not set";
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function ResearchStatusBadge({
  label,
  value,
  tone,
  className = "",
}: ResearchStatusBadgeProps) {
  const raw = value ?? "not_set";
  const resolvedTone = tone ?? valueTone[String(raw)] ?? "neutral";

  return (
    <span
      className={`inline-flex w-fit max-w-full items-center rounded-md border px-2 py-1 font-mono text-[10px] font-medium uppercase tracking-[0.16em] ${toneClasses[resolvedTone]} ${className}`}
    >
      <span className="truncate">{label ?? researchLabel(String(raw))}</span>
    </span>
  );
}
