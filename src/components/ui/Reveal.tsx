"use client";

import {
  useEffect,
  useRef,
  type CSSProperties,
  type ElementType,
  type ReactNode,
} from "react";

type RevealProps = {
  children: ReactNode;
  /** Stagger delay in ms, applied via --reveal-delay */
  delay?: number;
  className?: string;
  as?: "div" | "section" | "li" | "span";
};

/**
 * Scroll-driven reveal. Adds .is-visible once the element enters the
 * viewport; the transition lives in globals.css and is disabled under
 * prefers-reduced-motion. The class is toggled directly on the DOM node so
 * revealing never re-renders the subtree.
 */
export function Reveal({
  children,
  delay = 0,
  className = "",
  as = "div",
}: RevealProps) {
  const ref = useRef<HTMLElement | null>(null);

  useEffect(() => {
    const node = ref.current;
    if (!node) return;

    if (typeof IntersectionObserver === "undefined") {
      node.classList.add("is-visible");
      return;
    }

    // Anything at or above the fold on mount is already "arrived" — deep
    // links, a restored scroll position, or a fast flick would otherwise
    // leave it stuck at opacity 0 forever, because it never intersects on
    // the way in.
    if (node.getBoundingClientRect().top < window.innerHeight) {
      node.classList.add("is-visible");
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          // threshold 0 + a negative bottom margin: fires as soon as any part
          // crosses into the lower tenth of the viewport. A 0.1 area
          // threshold never resolved for panels taller than the screen.
          if (entry.isIntersecting) {
            node.classList.add("is-visible");
            observer.disconnect();
            window.clearTimeout(failsafe);
          }
        }
      },
      { rootMargin: "0px 0px -8% 0px", threshold: 0 }
    );

    observer.observe(node);

    // Content that starts at opacity 0 must never be able to stay there. A
    // hidden document (opened in a background tab, prerendered) does not
    // deliver intersections at all, so if nothing has arrived by the time
    // the entrance would have finished anyway, just show it.
    const failsafe = window.setTimeout(() => {
      node.classList.add("is-visible");
      observer.disconnect();
    }, 2500);

    return () => {
      observer.disconnect();
      window.clearTimeout(failsafe);
    };
  }, []);

  const Tag = as as ElementType;

  return (
    <Tag
      ref={ref}
      className={`reveal ${className}`}
      style={{ "--reveal-delay": `${delay}ms` } as CSSProperties}
    >
      {children}
    </Tag>
  );
}
