"use client";

import { motion, useReducedMotion } from "framer-motion";

type ProgressRingProps = {
  value: number;
  label?: string;
  size?: number;
  stroke?: number;
  className?: string;
};

export function ProgressRing({
  value,
  label = "Project progress",
  size = 68,
  stroke = 6,
  className = "",
}: ProgressRingProps) {
  const reducedMotion = useReducedMotion();
  const normalized = Math.max(0, Math.min(100, value));
  const radius = (size - stroke) / 2;

  return (
    <div
      className={`relative inline-flex items-center justify-center ${className}`}
      role="img"
      aria-label={`${label}: ${normalized}%`}
    >
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--border)"
          strokeWidth={stroke}
        />
        <motion.circle
          cx={size / 2}
          cy={size / 2}
          r={radius}
          fill="none"
          stroke="var(--accent)"
          strokeLinecap="round"
          strokeWidth={stroke}
          pathLength="1"
          strokeDasharray="1"
          initial={false}
          animate={{ strokeDashoffset: 1 - normalized / 100 }}
          transition={{ duration: reducedMotion ? 0 : 0.7, ease: [0.16, 1, 0.3, 1] }}
          style={{ rotate: -90, transformOrigin: "center" }}
        />
      </svg>
      <span className="absolute font-mono text-sm font-semibold text-foreground">
        {normalized}%
      </span>
    </div>
  );
}
