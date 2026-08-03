"use client";

import { useEffect } from "react";
import { animate, motion, useMotionValue, useReducedMotion, useTransform } from "framer-motion";
import { SectionLabel } from "@/components/ui/SectionLabel";

type KpiStatProps = {
  label: string;
  value: number;
  detail?: string;
  tone?: "accent" | "success" | "warning" | "danger" | "neutral";
  sparkline?: number[];
  className?: string;
};

const toneText = {
  accent: "text-accent-bright",
  success: "text-success",
  warning: "text-warning",
  danger: "text-error",
  neutral: "text-foreground",
};

const toneStroke = {
  accent: "var(--accent-bright)",
  success: "var(--status-done)",
  warning: "var(--risk-medium)",
  danger: "var(--risk-critical)",
  neutral: "var(--border-strong)",
};

function sparklinePoints(values: number[]) {
  if (values.length < 2) return "";
  const min = Math.min(...values);
  const max = Math.max(...values);
  const span = Math.max(1, max - min);
  return values
    .map((value, index) => {
      const x = (index / (values.length - 1)) * 88 + 6;
      const y = 38 - ((value - min) / span) * 26;
      return `${x},${y}`;
    })
    .join(" ");
}

export function KpiStat({
  label,
  value,
  detail,
  tone = "neutral",
  sparkline,
  className = "",
}: KpiStatProps) {
  const reducedMotion = useReducedMotion();
  const count = useMotionValue(reducedMotion ? value : 0);
  const rounded = useTransform(count, (latest) => Math.round(latest).toString());

  useEffect(() => {
    const controls = animate(count, value, {
      duration: reducedMotion ? 0 : 0.7,
      ease: [0.16, 1, 0.3, 1],
    });
    return () => controls.stop();
  }, [count, reducedMotion, value]);

  return (
    <motion.div
      className={`flow-card interactive-surface flex min-h-[9.5rem] flex-col p-6 ${className}`}
      initial={false}
      whileInView={reducedMotion ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ duration: 0.45, ease: [0.16, 1, 0.3, 1] }}
    >
      <SectionLabel tone="muted">{label}</SectionLabel>
      <motion.p
        className={`mt-3 font-mono text-4xl font-semibold tracking-tight ${toneText[tone]}`}
      >
        {rounded}
      </motion.p>
      {/* The sparkline used to be absolutely positioned bottom-right, so any
          detail string long enough to reach the corner got a line drawn
          through it. It now shares a flex row with the text and cannot
          overlap at any width. */}
      <div className="mt-auto flex items-end justify-between gap-3 pt-3">
        {detail ? (
          <p className="min-w-0 text-sm leading-6 text-foreground-secondary">
            {detail}
          </p>
        ) : (
          <span />
        )}
        {sparkline && sparkline.length > 1 ? (
          <svg
            aria-hidden
            className="h-9 w-20 shrink-0 opacity-70"
            viewBox="0 0 100 44"
            preserveAspectRatio="none"
          >
            <polyline
              points={sparklinePoints(sparkline)}
              fill="none"
              stroke={toneStroke[tone]}
              strokeLinecap="round"
              strokeLinejoin="round"
              strokeWidth="2"
              vectorEffect="non-scaling-stroke"
            />
          </svg>
        ) : null}
      </div>
    </motion.div>
  );
}
