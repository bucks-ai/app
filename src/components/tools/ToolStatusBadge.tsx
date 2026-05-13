type ToolStatusBadgeVariant =
  | "preferred"
  | "approved"
  | "external"
  | "blocked"
  | "human"
  | "low"
  | "medium"
  | "high"
  | "critical"
  | "success"
  | "warning"
  | "neutral"
  | "danger";

const variantClasses: Record<ToolStatusBadgeVariant, string> = {
  preferred: "border-[#4F46E5]/35 bg-[#4F46E5]/10 text-[#A5B4FC]",
  approved: "border-[#1C1C1C] bg-[#141414] text-[#D4D4D4]",
  external: "border-[#F59E0B]/35 bg-[#F59E0B]/10 text-[#FCD34D]",
  blocked: "border-[#EF4444]/35 bg-[#EF4444]/10 text-[#FCA5A5]",
  human: "border-[#F59E0B]/35 bg-[#F59E0B]/10 text-[#FCD34D]",
  low: "border-[#22C55E]/25 bg-[#22C55E]/10 text-[#86EFAC]",
  medium: "border-[#F59E0B]/25 bg-[#F59E0B]/10 text-[#FDE68A]",
  high: "border-[#F59E0B]/35 bg-[#F59E0B]/10 text-[#FCD34D]",
  critical: "border-[#EF4444]/35 bg-[#EF4444]/10 text-[#FCA5A5]",
  success: "border-[#22C55E]/25 bg-[#22C55E]/10 text-[#86EFAC]",
  warning: "border-[#F59E0B]/35 bg-[#F59E0B]/10 text-[#FCD34D]",
  neutral: "border-[#1C1C1C] bg-[#141414] text-[#888888]",
  danger: "border-[#EF4444]/35 bg-[#EF4444]/10 text-[#FCA5A5]",
};

type ToolStatusBadgeProps = {
  label: string;
  variant: ToolStatusBadgeVariant;
};

export function ToolStatusBadge({
  label,
  variant,
}: ToolStatusBadgeProps) {
  return (
    <span
      className={`inline-flex w-fit rounded-md border px-2.5 py-1 font-mono text-[11px] font-medium uppercase tracking-[0.18em] ${variantClasses[variant]}`}
    >
      {label}
    </span>
  );
}
