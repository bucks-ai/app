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
  "inline-flex min-h-12 cursor-pointer items-center justify-center gap-2 rounded-lg px-6 py-3 text-sm font-semibold transition-[background-color,border-color,color,transform] duration-200 active:scale-[0.98]";

const variants = {
  primary:
    "bg-accent text-accent-contrast shadow-soft hover:bg-accent-hover",
  secondary:
    "border border-border bg-surface/70 font-medium text-secondary hover:border-accent/45 hover:text-foreground",
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
