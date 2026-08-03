"use client";

import { useEffect, useRef } from "react";

/**
 * The single atmosphere for a route.
 *
 * Every section used to paint its own background and aurora, which is what
 * gave the page hard horizontal seams. This renders one fixed gradient field
 * behind the entire document instead: content scrolls through the light, and
 * sections are separated by space and type weight rather than by a band edge.
 *
 * The bloom drifts on a slow loop and shifts a little with scroll, so long
 * pages don't feel like they're standing still. Both are transform/opacity
 * only, and both are parked by prefers-reduced-motion.
 *
 * Render once, at the top of a route. Nothing else should be full-bleed.
 */
export function PageField({ grid = true }: { grid?: boolean }) {
  const bloomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const bloom = bloomRef.current;
    if (!bloom) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    let frame = 0;

    const onScroll = () => {
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        frame = 0;
        // Deliberately shallow: the field should lag the page, not race it.
        const offset = Math.min(window.scrollY * 0.12, 220);
        bloom.style.transform = `translate3d(0, ${offset}px, 0)`;
      });
    };

    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => {
      window.removeEventListener("scroll", onScroll);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);

  return (
    <div aria-hidden className="page-field">
      <div ref={bloomRef} className="page-field-parallax absolute inset-0">
        <div className="page-field-bloom field-breathe" />
      </div>
      {grid ? <div className="grid-backdrop-soft absolute inset-0" /> : null}
    </div>
  );
}
