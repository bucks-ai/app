"use client";

import { useEffect, useRef, type ReactNode } from "react";

type LineRevealProps = {
  children: ReactNode;
  className?: string;
  as?: "h1" | "h2" | "h3" | "p";
};

/**
 * Splits its text into visual lines and reveals each from behind a mask as
 * it scrolls in.
 *
 * Three things this deliberately does NOT do, each for a reason:
 *
 *  - It does not split per character. That multiplies DOM nodes by an order
 *    of magnitude, breaks find-on-page, makes copy/paste produce garbage,
 *    and is the version screen readers handle worst. Per line is the right
 *    granularity for display type.
 *
 *  - It does not split during render. The server output and the pre-hydration
 *    DOM are plain text, so there is no hydration mismatch and no flash of
 *    unstyled headline. The split runs in an effect as an enhancement.
 *
 *  - It does not split before fonts are ready. Line breaks measured against
 *    fallback metrics are wrong once the real face swaps in, which produces
 *    both broken wrapping and a layout shift. It waits on document.fonts.
 *
 * Accessibility: splitting destroys the accessible name, so the original
 * string is restored via aria-label on the host and every fragment is
 * aria-hidden. Under prefers-reduced-motion the split is skipped entirely.
 */
export function LineReveal({
  children,
  className = "",
  as: Tag = "h1",
}: LineRevealProps) {
  const ref = useRef<HTMLElement>(null);

  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    // No view-timeline support means the masks would never animate open and
    // the text would stay hidden behind them. Leave it as plain text.
    if (!CSS.supports("animation-timeline", "view()")) return;

    const original = el.textContent ?? "";
    let cancelled = false;

    function split() {
      if (cancelled || !el || !original.trim()) return;

      // Measure line boxes by walking a Range one word at a time and
      // watching for the top offset to change.
      const words = original.split(/(\s+)/);
      el.textContent = "";
      const probe = document.createElement("span");
      el.appendChild(probe);

      const lines: string[] = [];
      let current = "";
      let lastTop: number | null = null;

      for (const token of words) {
        probe.textContent = current + token;
        const rects = probe.getClientRects();
        const top = rects.length ? rects[rects.length - 1].top : null;
        if (lastTop !== null && top !== null && top > lastTop && current.trim()) {
          lines.push(current);
          current = token.trimStart();
          probe.textContent = current;
          const r2 = probe.getClientRects();
          lastTop = r2.length ? r2[r2.length - 1].top : top;
          continue;
        }
        current += token;
        if (top !== null) lastTop = top;
      }
      if (current.trim()) lines.push(current);

      probe.remove();
      if (cancelled) {
        el.textContent = original;
        return;
      }

      el.setAttribute("aria-label", original.trim());
      for (const line of lines) {
        const mask = document.createElement("span");
        mask.className = "line-mask";
        mask.setAttribute("aria-hidden", "true");
        const inner = document.createElement("span");
        inner.textContent = line;
        mask.appendChild(inner);
        el.appendChild(mask);
      }
    }

    const fonts = document.fonts;
    if (fonts?.ready) {
      void fonts.ready.then(() => split());
    } else {
      split();
    }

    return () => {
      cancelled = true;
    };
  }, [children]);

  return (
    <Tag ref={ref as never} className={className}>
      {children}
    </Tag>
  );
}
