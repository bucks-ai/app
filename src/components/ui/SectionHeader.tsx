import type { ReactNode } from "react";
import { SectionLabel } from "@/components/ui/SectionLabel";

type SectionHeaderProps = {
  eyebrow: string;
  title: ReactNode;
  description?: ReactNode;
  align?: "left" | "center";
  className?: string;
};

/**
 * Standard section opener: mono eyebrow label with a hairline tick,
 * Space Grotesk display title, optional supporting copy.
 */
export function SectionHeader({
  eyebrow,
  title,
  description,
  align = "left",
  className = "",
}: SectionHeaderProps) {
  const centered = align === "center";
  return (
    <div
      className={`max-w-2xl ${centered ? "mx-auto text-center" : ""} ${className}`}
    >
      <div
        className={`flex items-center gap-3 ${centered ? "justify-center" : ""}`}
      >
        <span aria-hidden className="h-px w-6 bg-accent/60" />
        <SectionLabel>{eyebrow}</SectionLabel>
      </div>
      <h2 className="mt-4 text-3xl font-semibold tracking-tight text-foreground sm:text-4xl">
        {title}
      </h2>
      {description ? (
        <p className="mt-4 text-base leading-relaxed text-secondary">
          {description}
        </p>
      ) : null}
    </div>
  );
}
