type StatusPillVariant =
  | "accent"
  | "success"
  | "warning"
  | "danger"
  | "neutral";

const variantClasses: Record<StatusPillVariant, string> = {
  accent: "border-[#4F46E5]/35 bg-[#4F46E5]/10 text-[#A5B4FC]",
  success: "border-[#22C55E]/25 bg-[#22C55E]/10 text-[#86EFAC]",
  warning: "border-[#F59E0B]/35 bg-[#F59E0B]/10 text-[#FCD34D]",
  danger: "border-[#EF4444]/35 bg-[#EF4444]/10 text-[#FCA5A5]",
  neutral: "border-[#1C1C1C] bg-[#141414] text-[#888888]",
};

type StatusPillProps = {
  label: string;
  variant?: StatusPillVariant;
  className?: string;
};

export function StatusPill({
  label,
  variant = "neutral",
  className = "",
}: StatusPillProps) {
  return (
    <span
      className={`inline-flex w-fit items-center rounded-md border px-2.5 py-1 font-mono text-[11px] font-medium uppercase tracking-[0.18em] ${variantClasses[variant]} ${className}`}
    >
      {label}
    </span>
  );
}
