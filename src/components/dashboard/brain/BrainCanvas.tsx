"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef } from "react";
import { BrainField } from "./BrainField";
import { BrainOutline } from "./BrainOutline";
import {
  WORLD_H,
  WORLD_W,
  buildBrainNodes,
  cameraFor,
  pathTo,
  visibleNodes,
  type BrainBusiness,
  type BrainNode,
  type Camera,
} from "./brain-model";

type BrainCanvasProps = {
  businesses: BrainBusiness[];
  /** Sample data never animates — motion here is a claim that work is live. */
  sample?: boolean;
};

const ZOOM_MS = 520;

const toneClass: Record<BrainNode["tone"], string> = {
  accent: "tone-accent",
  warning: "tone-warning",
  danger: "tone-danger",
  running: "tone-running",
  neutral: "tone-neutral",
};

function easeOutCubic(t: number) {
  return 1 - Math.pow(1 - t, 3);
}

function prefersReducedMotion() {
  if (typeof window === "undefined") return false;
  return window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/**
 * The dashboard as a zoomable brain.
 *
 * - Focus lives in the URL (`?focus=<nodeId>`), so every level is a real
 *   destination: shareable, bookmarkable, and browser-back works without any
 *   history handling of our own.
 * - One world, one camera. Zooming animates a single transform between framings
 *   computed by `cameraFor`, which is what makes a drill-down read as flying
 *   into the same brain rather than swapping screens.
 * - Nodes are buttons and links in the DOM, not painted shapes, so keyboard and
 *   screen-reader users get the same tree. The SVG underneath is decorative.
 * - Below lg the canvas is replaced by BrainOutline — the same tree as nested
 *   disclosure lists, because pan-and-zoom on a phone is a trap.
 */
export function BrainCanvas({ businesses, sample = false }: BrainCanvasProps) {
  const nodes = useMemo(() => buildBrainNodes(businesses), [businesses]);
  const searchParams = useSearchParams();

  // The URL is the single source of truth for depth. A `focus` that matches no
  // node (stale link, hand-edited param) falls back to the whole brain rather
  // than rendering an empty canvas.
  const requested = searchParams.get("focus");
  const focusId =
    requested && nodes.some((node) => node.id === requested) ? requested : null;

  const viewportRef = useRef<HTMLDivElement>(null);
  const worldRef = useRef<HTMLDivElement>(null);
  const camera = useRef<Camera>({ x: 0, y: 0, k: 1 });
  const anim = useRef(0);
  /* Set by goTo, consumed by the focus effect below — declared up here so the
     callback that writes it is defined after it, not before. */
  const wantsFocus = useRef(false);
  const rootCrumbRef = useRef<HTMLButtonElement>(null);

  const trail = useMemo(() => pathTo(nodes, focusId), [nodes, focusId]);
  const visible = useMemo(() => visibleNodes(nodes, focusId), [nodes, focusId]);
  const live = !sample && businesses.some((business) => business.live);

  const paint = useCallback(() => {
    const world = worldRef.current;
    if (!world) return;
    const { x, y, k } = camera.current;
    world.style.transform = `translate3d(${x}px, ${y}px, 0) scale(${k})`;
  }, []);

  /* Animates to the framing for `target`. Restarting mid-flight picks up from
     wherever the camera currently is, so rapid clicks never jump. */
  const flyTo = useCallback(
    (target: string | null, immediate = false) => {
      const viewport = viewportRef.current;
      if (!viewport) return;

      const next = cameraFor(nodes, target, {
        w: viewport.clientWidth,
        h: viewport.clientHeight,
      });

      cancelAnimationFrame(anim.current);

      if (immediate || prefersReducedMotion()) {
        camera.current = next;
        paint();
        return;
      }

      const from = { ...camera.current };
      const start = performance.now();

      const step = (now: number) => {
        const t = Math.min(1, (now - start) / ZOOM_MS);
        const e = easeOutCubic(t);
        camera.current = {
          x: from.x + (next.x - from.x) * e,
          y: from.y + (next.y - from.y) * e,
          k: from.k + (next.k - from.k) * e,
        };
        paint();
        if (t < 1) anim.current = requestAnimationFrame(step);
      };

      anim.current = requestAnimationFrame(step);
    },
    [nodes, paint]
  );

  // Re-frame on resize without animating — a window drag is not a navigation.
  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const observer = new ResizeObserver(() => flyTo(focusId, true));
    observer.observe(viewport);
    return () => {
      observer.disconnect();
      cancelAnimationFrame(anim.current);
    };
  }, [flyTo, focusId]);

  // Fly whenever depth changes — including via browser back/forward, since
  // popstate updates searchParams and lands here like any other change. The
  // first run is immediate: animating in from a camera never on screen is
  // motion without meaning.
  const flown = useRef(false);
  useEffect(() => {
    flyTo(focusId, !flown.current);
    flown.current = true;
  }, [focusId, flyTo]);

  /* Shallow push: updates the URL and syncs useSearchParams without a server
     round-trip, so browser back walks back out of the brain for free. */
  const goTo = useCallback(
    (id: string | null) => {
      const params = new URLSearchParams(searchParams.toString());
      if (id) {
        params.set("focus", id);
      } else {
        params.delete("focus");
      }
      const query = params.toString();
      window.history.pushState(null, "", query ? `?${query}` : window.location.pathname);
      // Changing depth unmounts every child node and the Back button. Whichever
      // of them held focus takes it to <body> on unmount, so the next Tab
      // restarts from the top of the document (WCAG 2.4.3). Claim focus back
      // deliberately once the new level has committed.
      wantsFocus.current = true;
    },
    [searchParams]
  );

  // Escape climbs one level — the keyboard equivalent of the back crumb. Bound
  // only while the canvas is the live presentation: below lg the shell is
  // display:none and Escape would silently rewrite the URL behind the outline.
  useEffect(() => {
    if (!focusId) return;
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      if (!viewportRef.current?.offsetParent) return;
      const current = nodes.find((node) => node.id === focusId);
      goTo(current?.parentId ?? null);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [focusId, nodes, goTo]);

  /* Land focus on the node the user just zoomed into, so the tab order
     continues from where they are rather than from the document top. At the
     top level there is no such node, so the breadcrumb root takes it. */
  useEffect(() => {
    if (!wantsFocus.current) return;
    wantsFocus.current = false;

    const target = focusId
      ? viewportRef.current?.querySelector<HTMLElement>(".brain-node.is-focus")
      : rootCrumbRef.current;
    target?.focus({ preventScroll: true });
  }, [focusId]);

  const level = trail.length;
  const current = trail[trail.length - 1] ?? null;
  const childCount = visible.filter((entry) => entry.role === "child").length;

  // Named so a screen reader hears what changed after a zoom, which otherwise
  // silently swaps every control on the page (WCAG 4.1.3).
  const levelLabel = current
    ? `${current.label} — ${childCount} ${level === 1 ? "sections" : "panels"}`
    : `Brain — ${childCount} ${childCount === 1 ? "business" : "businesses"}`;

  return (
    <>
      <div className="brain-shell lg:block">
        <div className="brain-chrome">
          <nav aria-label="Brain location" className="brain-crumbs">
            <button
              ref={rootCrumbRef}
              type="button"
              onClick={() => goTo(null)}
              className="brain-crumb"
              aria-current={level === 0 ? "true" : undefined}
            >
              Brain
            </button>
            {trail.map((node) => (
              <span key={node.id} className="contents">
                <span aria-hidden className="brain-crumb-sep">
                  /
                </span>
                <button
                  type="button"
                  onClick={() => goTo(node.id)}
                  className="brain-crumb"
                  aria-current={node.id === focusId ? "true" : undefined}
                >
                  {node.label}
                </button>
              </span>
            ))}
          </nav>

          <div className="brain-actions">
            <Link href="/intake" className="brain-action is-primary">
              New business
            </Link>
            <Link href="/tools" className="brain-action">
              Tool registry
            </Link>
          </div>
        </div>

        {/* The page's only heading. The skip link lands on <main>, and without
            this there is nothing there to say where "here" is. */}
        <h1 className="sr-only">{levelLabel}</h1>
        <p aria-live="polite" className="sr-only">
          {levelLabel}
        </p>

        <div ref={viewportRef} className="brain-viewport">
          <div
            ref={worldRef}
            className="brain-world"
            style={{ width: WORLD_W, height: WORLD_H }}
          >
            <BrainField live={live} />

            {/* A real list: without it a screen reader hears ten sibling
                controls with no parent, depth, or set size. */}
            <ul className="brain-nodes" aria-label={levelLabel}>
              {visible.map(({ node, role }) => {
                const style = {
                  left: node.x,
                  top: node.y,
                  width: node.r * 2,
                  height: node.r * 2,
                };
                const className = [
                  "brain-node",
                  toneClass[node.tone],
                  `is-${role}`,
                  node.live && !sample ? "is-live" : "",
                ]
                  .filter(Boolean)
                  .join(" ");

                const hasCount = typeof node.count === "number" && node.count > 0;
                // The count is the most actionable value on the node, and an
                // aria-label overrides content — so it has to be spelled out
                // here or it reaches no screen-reader user at all.
                const countPhrase = hasCount ? `, ${node.count} awaiting you` : "";

                const body = (
                  <>
                    <span className="brain-node-label">{node.label}</span>
                    {hasCount ? (
                      <span className="brain-node-count">{node.count}</span>
                    ) : null}
                    <span className="brain-node-detail">{node.detail}</span>
                  </>
                );

                return (
                  <li key={node.id} className="brain-node-slot" style={style}>
                    {node.href ? (
                      <Link
                        href={node.href}
                        className={className}
                        aria-label={`${node.label}${countPhrase}, ${node.detail} — open`}
                      >
                        {body}
                      </Link>
                    ) : (
                      <button
                        type="button"
                        className={className}
                        onClick={() =>
                          goTo(role === "focus" ? node.parentId : node.id)
                        }
                        aria-expanded={role === "focus" ? true : undefined}
                        aria-label={
                          role === "focus"
                            ? `${node.label}${countPhrase} — zoom out`
                            : `${node.label}${countPhrase}, ${node.detail} — zoom in`
                        }
                      >
                        {body}
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>

          {level > 0 ? (
            <button
              type="button"
              className="brain-back"
              onClick={() => goTo(trail[trail.length - 1]?.parentId ?? null)}
            >
              <span aria-hidden>&#8592;</span> Back
              <span className="brain-back-hint" aria-hidden>
                Esc
              </span>
            </button>
          ) : null}
        </div>
      </div>

      <BrainOutline nodes={nodes} businesses={businesses} />
    </>
  );
}
