"use client";

import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";

type GlassCardProps = {
  children: ReactNode;
  className?: string;
  innerClassName?: string;
  interactive?: boolean;
  delay?: number;
  as?: "div" | "section" | "article";
  variant?: "glass" | "solid" | "elevated" | "neumorphic";
};

const variantClasses = {
  glass: "glass-surface glass-highlight",
  solid: "solid-surface",
  elevated: "elevated-surface glass-highlight",
  neumorphic: "neumorphic-soft",
};

export function GlassCard({
  children,
  className = "",
  innerClassName = "",
  interactive = false,
  delay = 0,
  as = "div",
  variant = "glass",
}: GlassCardProps) {
  const reducedMotion = useReducedMotion();
  const MotionTag =
    as === "section" ? motion.section : as === "article" ? motion.article : motion.div;

  return (
    <MotionTag
      className={`${variantClasses[variant]} relative overflow-hidden rounded-card ${
        interactive ? "interactive-surface cursor-pointer" : ""
      } ${className}`}
      initial={false}
      animate={reducedMotion ? undefined : { opacity: 1, y: 0 }}
      whileInView={reducedMotion ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-8% 0px" }}
      whileHover={
        interactive && !reducedMotion
          ? {
              y: -5,
              scale: 1.01,
              borderColor: "color-mix(in srgb, var(--accent) 42%, var(--border))",
              transition: { duration: 0.2, ease: [0.16, 1, 0.3, 1] },
            }
          : undefined
      }
      transition={{ duration: 0.5, delay, ease: [0.16, 1, 0.3, 1] }}
    >
      <div className={`relative z-10 ${innerClassName}`}>{children}</div>
    </MotionTag>
  );
}
