"use client";

import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";

type GlassPanelProps = {
  children: ReactNode;
  className?: string;
  innerClassName?: string;
  interactive?: boolean;
  as?: "div" | "section" | "article";
  variant?: "glass" | "solid" | "elevated" | "neumorphic";
};

const variantClasses = {
  glass: "glass-surface glass-highlight",
  solid: "solid-surface",
  elevated: "elevated-surface glass-highlight",
  neumorphic: "neumorphic-soft",
};

export function GlassPanel({
  children,
  className = "",
  innerClassName = "",
  interactive = false,
  as = "div",
  variant = "glass",
}: GlassPanelProps) {
  const reducedMotion = useReducedMotion();
  const MotionTag =
    as === "section" ? motion.section : as === "article" ? motion.article : motion.div;

  return (
    <MotionTag
      className={`${variantClasses[variant]} relative overflow-hidden rounded-card ${
        interactive ? "interactive-surface group" : ""
      } ${className}`}
      initial={false}
      whileInView={reducedMotion ? undefined : { opacity: 1, y: 0, rotateX: 0 }}
      viewport={{ once: true, margin: "-10% 0px" }}
      whileHover={
        interactive && !reducedMotion
          ? {
              y: -4,
              borderColor: "var(--accent-ring)",
              transition: { duration: 0.2, ease: [0.16, 1, 0.3, 1] },
            }
          : undefined
      }
      transition={{ duration: 0.5, ease: [0.16, 1, 0.3, 1] }}
      style={{ transformPerspective: 1200 }}
    >
      <div className={`relative z-10 ${innerClassName}`}>{children}</div>
    </MotionTag>
  );
}
