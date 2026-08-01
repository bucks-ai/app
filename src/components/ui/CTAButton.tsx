import Link from "next/link";
import type { ReactNode } from "react";

type CTAButtonProps = {
  href: string;
  children: ReactNode;
  variant?: "primary" | "secondary";
  /** Show the trailing arrow */
  arrow?: boolean;
  className?: string;
};

const base =
  "inline-flex min-h-12 cursor-pointer items-center justify-center gap-2 rounded-lg px-6 py-3 text-sm font-semibold transition-[background-color,border-color,color,box-shadow,transform] duration-200 ease-[var(--ease-out-expo)] active:scale-[0.98]";

const variants = {
  primary:
    "border border-white/10 bg-accent bg-[image:var(--cta-gradient)] text-accent-contrast shadow-[var(--shadow-cta)] hover:-translate-y-0.5 hover:shadow-[0_1px_0_rgba(255,255,255,0.2)_inset,0_18px_42px_rgba(12,133,121,0.3)]",
  secondary:
    "glass-surface font-medium text-foreground-secondary hover:-translate-y-0.5 hover:border-accent/45 hover:text-foreground",
};

/**
 * The one CTA. Press feedback is a 0.98 scale (cheap, GPU-only); arrow is
 * decorative and hidden from readers.
 */
export function CTAButton({
  href,
  children,
  variant = "primary",
  arrow = false,
  className = "",
}: CTAButtonProps) {
  return (
    <Link href={href} className={`${base} ${variants[variant]} ${className}`}>
      {children}
      {arrow ? (
        <span aria-hidden className="opacity-80">
          &#8594;
        </span>
      ) : null}
    </Link>
  );
}
