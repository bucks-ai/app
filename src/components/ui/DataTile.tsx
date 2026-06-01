import { SectionLabel } from "@/components/ui/SectionLabel";

type DataTileProps = {
  label: string;
  value: string;
  detail?: string;
  tone?: "accent" | "success" | "warning" | "danger" | "neutral";
  className?: string;
};

const valueToneClasses = {
  accent: "text-accent",
  success: "text-success",
  warning: "text-warning",
  danger: "text-error",
  neutral: "text-foreground",
};

export function DataTile({
  label,
  value,
  detail,
  tone = "neutral",
  className = "",
}: DataTileProps) {
  return (
    <div
      className={`rounded-lg border border-border bg-background p-4 ${className}`}
    >
      <SectionLabel tone="muted">{label}</SectionLabel>
      <p
        className={`mt-3 break-words text-xl font-semibold tracking-tight ${valueToneClasses[tone]}`}
      >
        {value}
      </p>
      {detail ? (
        <p className="mt-2 text-sm leading-6 text-secondary">{detail}</p>
      ) : null}
    </div>
  );
}
