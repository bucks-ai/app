import type {
  ValidationHypothesisStatus,
  ValidationLeadStatus,
  ValidationPriority,
  ValidationSignalStrength,
  ValidationStatus,
} from "@/types/validation-ui";

type BadgeTone = "accent" | "success" | "warning" | "danger" | "neutral";

type ValidationStatusBadgeProps = {
  label?: string;
  value:
    | ValidationStatus
    | ValidationPriority
    | ValidationSignalStrength
    | ValidationLeadStatus
    | ValidationHypothesisStatus
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

const statusTone: Record<string, BadgeTone> = {
  not_started: "neutral",
  planned: "accent",
  outreach_ready: "warning",
  interviews_scheduled: "warning",
  learning: "accent",
  validated: "success",
  invalidated: "danger",
  needs_pivot: "danger",
  high: "warning",
  medium: "accent",
  low: "neutral",
  strong: "success",
  weak: "neutral",
  identified: "neutral",
  contacted: "accent",
  replied: "warning",
  scheduled: "warning",
  interviewed: "success",
  not_interested: "danger",
  untested: "neutral",
  testing: "warning",
  supported: "success",
  rejected: "danger",
  inconclusive: "accent",
};

export function validationLabel(value: string | null | undefined) {
  if (!value) return "Not set";
  return value
    .split("_")
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

export function ValidationStatusBadge({
  label,
  value,
  tone,
  className = "",
}: ValidationStatusBadgeProps) {
  const raw = value ?? "not_set";
  const resolvedTone = tone ?? statusTone[String(raw)] ?? "neutral";

  return (
    <span
      className={`inline-flex w-fit max-w-full items-center rounded-md border px-2 py-1 font-mono text-[10px] font-medium uppercase tracking-[0.16em] ${toneClasses[resolvedTone]} ${className}`}
    >
      <span className="truncate">{label ?? validationLabel(String(raw))}</span>
    </span>
  );
}
