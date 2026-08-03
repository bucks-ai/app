"use client";

import Link from "next/link";
import { motion, useReducedMotion } from "framer-motion";

type NextActionBlockProps = {
  href: string;
  title: string;
  description: string;
  meta?: string;
  cta?: string;
  className?: string;
};

export function NextActionBlock({
  href,
  title,
  description,
  meta,
  cta = "Open workspace",
  className = "",
}: NextActionBlockProps) {
  const reducedMotion = useReducedMotion();

  // Gradient was accent-soft → accent-BLUE-soft, one of the leaks that put a
  // second hue right next to the teal CTA. Both stops are teal now.
  return (
    <motion.div
      className={`interactive-surface rounded-2xl border border-accent/15 bg-[linear-gradient(135deg,var(--accent-soft),color-mix(in_srgb,var(--accent)_5%,transparent))] p-5 ${className}`}
      whileHover={reducedMotion ? undefined : { y: -2 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
    >
      <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-accent-bright">
        Next action
      </p>
      <h3 className="mt-2 text-base font-semibold tracking-tight text-foreground">
        {title}
      </h3>
      <p className="mt-2 line-clamp-3 text-sm leading-6 text-foreground-secondary">
        {description}
      </p>
      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {meta ? (
          <p className="font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground">
            {meta}
          </p>
        ) : null}
        <Link
          href={href}
          className="inline-flex min-h-11 cursor-pointer items-center justify-center rounded-lg bg-accent bg-[image:var(--cta-gradient)] px-4 py-2.5 text-sm font-semibold text-accent-contrast shadow-[var(--shadow-cta)] transition-transform duration-200 hover:-translate-y-0.5"
        >
          {cta}
        </Link>
      </div>
    </motion.div>
  );
}
