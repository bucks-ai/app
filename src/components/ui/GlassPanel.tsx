"use client";

import type { ReactNode } from "react";
import { motion, useReducedMotion } from "framer-motion";

type GlassPanelProps = {
  children: ReactNode;
  className?: string;
  innerClassName?: string;
  interactive?: boolean;
  as?: "div" | "section" | "article";
};

export function GlassPanel({
  children,
  className = "",
  innerClassName = "",
  interactive = false,
  as = "div",
}: GlassPanelProps) {
  const reducedMotion = useReducedMotion();
  const MotionTag =
    as === "section" ? motion.section : as === "article" ? motion.article : motion.div;

  return (
    <MotionTag
      className={`glass-surface glass-highlight relative overflow-hidden rounded-card ${
        interactive ? "group" : ""
      } ${className}`}
      initial={false}
      whileInView={reducedMotion ? undefined : { opacity: 1, y: 0, rotateX: 0 }}
      viewport={{ once: true, margin: "-10% 0px" }}
      whileHover={
        interactive && !reducedMotion
          ? {
              y: -4,
              borderColor: "rgba(166, 180, 255, 0.38)",
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
