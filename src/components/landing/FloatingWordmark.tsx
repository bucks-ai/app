"use client";

import { useEffect, useRef } from "react";

/**
 * Ambient "bucks.ai" wordmark drifting behind the homepage.
 *
 * Three oversized green glyphs on a fixed, pointer-transparent layer. Each
 * drifts on its own slow transform loop, and the whole layer lags scroll by
 * a small factor (parallax) — written via rAF to a single translate3d, so
 * scrolling never blocks on this and no layout property is touched.
 * Reduced-motion parks both the drift and the parallax in CSS.
 */
export function FloatingWordmark() {
  const layer = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    let raf = 0;
    const onScroll = () => {
      cancelAnimationFrame(raf);
      raf = requestAnimationFrame(() => {
        if (layer.current) {
          // Strong enough that glyphs visibly hand off between sections
          // instead of sitting pinned behind every screen.
          layer.current.style.transform = `translate3d(0, ${window.scrollY * -0.16}px, 0)`;
        }
      });
    };
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      cancelAnimationFrame(raf);
    };
  }, []);

  return (
    <div ref={layer} aria-hidden className="wordmark-layer">
      {/* Positioned to miss the hero headline block (top-left) so the two
          display-scale wordsets never layer. */}
      <span
        className="wordmark-glyph wordmark-drift"
        style={{ top: "55%", left: "28%", fontSize: "clamp(8rem, 22vw, 20rem)" }}
      >
        bucks.ai
      </span>
      <span
        className="wordmark-glyph wordmark-drift-alt"
        style={{ top: "110%", right: "-8%", fontSize: "clamp(6rem, 16vw, 15rem)", ["--wm-scale" as string]: 0.8 }}
      >
        bucks.ai
      </span>
      <span
        className="wordmark-glyph wordmark-drift"
        style={{ top: "170%", left: "6%", fontSize: "clamp(5rem, 12vw, 11rem)", ["--wm-scale" as string]: 0.7, animationDelay: "-20s" }}
      >
        bucks.ai
      </span>
    </div>
  );
}
