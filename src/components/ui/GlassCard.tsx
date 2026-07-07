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
};

export function GlassCard({
  children,
  className = "",
  innerClassName = "",
  interactive = false,
  delay = 0,
  as = "div",
}: GlassCardProps) {
  const reducedMotion = useReducedMotion();
  const MotionTag =
    as === "section" ? motion.section : as === "article" ? motion.article : motion.div;

  return (
    <MotionTag
      className={`glass-surface glass-highlight relative overflow-hidden rounded-card ${
        interactive ? "cursor-pointer" : ""
      } ${className}`}
      initial={reducedMotion ? false : { opacity: 0, y: 18 }}
      animate={reducedMotion ? undefined : { opacity: 1, y: 0 }}
      whileInView={reducedMotion ? undefined : { opacity: 1, y: 0 }}
      viewport={{ once: true, margin: "-8% 0px" }}
      whileHover={
        interactive && !reducedMotion
          ? {
              y: -5,
              scale: 1.01,
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
