"use client";

import { useEffect } from "react";

/**
 * Scrolls to the panel named by `?section=` after arriving from the brain's
 * level-3 nodes, and moves keyboard focus there.
 *
 * Focus, not just scroll: a screen-reader or keyboard user who follows a link
 * into a specific panel should land *in* it, otherwise the next Tab press
 * starts from the top of the document and the deep link bought them nothing
 * (WCAG 2.4.3, and the focus-on-route-change rule).
 *
 * Tabs load their data client-side, so the target usually does not exist on the
 * first paint. This retries on a short interval and gives up rather than
 * spinning forever.
 */
export function useSectionFocus(section: string | null, activeTab: string) {
  useEffect(() => {
    if (!section) return;

    let attempts = 0;
    let cancelled = false;

    const tick = () => {
      if (cancelled) return;

      const target = document.getElementById(section);
      if (!target) {
        // ~4s of retries: enough for a slow workspace fetch, bounded so a
        // stale section id cannot leave a timer running.
        if (attempts++ > 40) return;
        timer = window.setTimeout(tick, 100);
        return;
      }

      const reduced = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      target.scrollIntoView({
        behavior: reduced ? "auto" : "smooth",
        block: "start",
      });

      // Programmatic focus needs a tabindex, but a permanent one would put an
      // extra stop in everyone's tab order, so it is removed on blur.
      target.setAttribute("tabindex", "-1");
      target.focus({ preventScroll: true });
      target.addEventListener("blur", () => target.removeAttribute("tabindex"), {
        once: true,
      });
    };

    let timer = window.setTimeout(tick, 60);

    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [section, activeTab]);
}
