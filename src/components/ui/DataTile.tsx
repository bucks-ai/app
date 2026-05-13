import { SectionLabel } from "@/components/ui/SectionLabel";

type DataTileProps = {
  label: string;
  value: string;
  detail?: string;
  tone?: "accent" | "success" | "warning" | "danger" | "neutral";
  className?: string;
};

const valueToneClasses = {
  accent: "text-[#A5B4FC]",
  success: "text-[#86EFAC]",
  warning: "text-[#FCD34D]",
  danger: "text-[#FCA5A5]",
  neutral: "text-[#F0F0F0]",
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
      className={`rounded-lg border border-[#1C1C1C] bg-[#080808] p-4 ${className}`}
    >
      <SectionLabel tone="muted">{label}</SectionLabel>
      <p
        className={`mt-3 text-2xl font-semibold tracking-tight ${valueToneClasses[tone]}`}
      >
        {value}
      </p>
      {detail ? (
        <p className="mt-2 text-sm leading-6 text-[#888888]">{detail}</p>
      ) : null}
    </div>
  );
}

