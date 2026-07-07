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

  return (
    <motion.div
      className={`rounded-xl border border-accent/25 bg-accent/10 p-4 ${className}`}
      whileHover={reducedMotion ? undefined : { y: -2 }}
      transition={{ duration: 0.2, ease: [0.16, 1, 0.3, 1] }}
    >
      <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-accent-bright">
        Next action
      </p>
      <h3 className="mt-2 text-base font-semibold tracking-tight text-foreground">
        {title}
      </h3>
      <p className="mt-2 line-clamp-3 text-sm leading-6 text-secondary">
        {description}
      </p>
      <div className="mt-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        {meta ? (
          <p className="font-mono text-[10px] uppercase tracking-[0.18em] text-muted">
            {meta}
          </p>
        ) : null}
        <Link
          href={href}
          className="inline-flex min-h-11 cursor-pointer items-center justify-center rounded-lg bg-accent px-4 py-2.5 text-sm font-semibold text-accent-contrast transition-colors hover:bg-accent-hover"
        >
          {cta}
        </Link>
      </div>
    </motion.div>
  );
}
