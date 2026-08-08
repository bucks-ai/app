"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
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
const MIN_SCALE = 0.25;
const MAX_SCALE = 3.2;
const PAN_STEP = 80;
/* Room the preview card needs above a node before it has to flip below. */
const PEEK_CLEARANCE = 190;

const toneClass: Record<BrainNode["tone"], string> = {
  accent: "tone-accent",
  warning: "tone-warning",
  danger: "tone-danger",
  running: "tone-running",
  neutral: "tone-neutral",
};

/* Expo-out, the easing the design-system pass recommended: a fast departure
   that settles rather than coasting. It reads as the camera arriving somewhere
   instead of drifting to a stop. Matches cubic-bezier(0.16, 1, 0.3, 1). */
function easeOutExpo(t: number) {
  return t >= 1 ? 1 : 1 - Math.pow(2, -10 * t);
}

/* What a region contains, for the preview card. This is the literal answer to
   "show me what is inside before I commit" — and it costs nothing, because the
   children are already in the node tree. */
function peekContents(nodes: BrainNode[], node: BrainNode): BrainNode[] {
  return nodes.filter((entry) => entry.parentId === node.id).slice(0, 6);
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
  const drift = useRef({ x: 0, y: 0 });
  const dragRef = useRef<{ id: number; x: number; y: number } | null>(null);
  const [drifted, setDrifted] = useState(false);
  const [peek, setPeek] = useState<{
    node: BrainNode;
    x: number;
    y: number;
    below: boolean;
  } | null>(null);
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

    /* Node chrome counter-scales by this, so type is authored in real pixels
       instead of being multiplied by whatever the camera happens to be. That
       multiplication is why the canvas read as a wireframe: a 13px label
       rendered anywhere between 6px and 15px depending on depth, and no display
       face survives that, which is why the serif could never appear here.
       Clamped so the counter-scale cannot outgrow the disc it sits in. */
    const inverse = Math.min(1.9, Math.max(0.8, 1 / k));
    world.style.setProperty("--brain-inv", inverse.toFixed(4));
  }, []);

  /* Animates to the framing for `target`. Restarting mid-flight picks up from
     wherever the camera currently is, so rapid clicks never jump. */
  const flyTo = useCallback(
    (target: string | null, immediate = false) => {
      const viewport = viewportRef.current;
      if (!viewport) return;

      /* A viewport that measures zero — hidden tab, display:none ancestor, or a
         ResizeObserver firing before first layout — makes cameraFor divide
         against nothing and clamp to its minimum scale, which lands the brain
         at a garbage framing. Wait for a real box instead. */
      if (viewport.clientWidth === 0 || viewport.clientHeight === 0) return;

      const next = cameraFor(nodes, target, {
        w: viewport.clientWidth,
        h: viewport.clientHeight,
      });

      cancelAnimationFrame(anim.current);
      drift.current = { x: 0, y: 0 };

      if (immediate || prefersReducedMotion()) {
        camera.current = next;
        paint();
        return;
      }

      const from = { ...camera.current };
      const start = performance.now();

      const step = (now: number) => {
        const t = Math.min(1, (now - start) / ZOOM_MS);
        const e = easeOutExpo(t);
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

  /* ── Preview before committing ─────────────────────────────────────────
     The card renders in the chrome layer, OUTSIDE `.brain-world`, so its type
     is real pixels rather than whatever the camera scale happens to be. It is
     positioned from the node's projected rect each time it opens. */

  const openPeek = useCallback((node: BrainNode, el: HTMLElement) => {
    const viewport = viewportRef.current;
    if (!viewport) return;
    const rect = el.getBoundingClientRect();
    const box = viewport.getBoundingClientRect();

    /* Flip below when there is not room above. The viewport is `overflow:
       clip`, so a card that overflows the top is silently cut in half rather
       than escaping — which is exactly how it loses its title. */
    const above = rect.top - box.top;
    const below = above < PEEK_CLEARANCE;

    setPeek({
      node,
      x: rect.left - box.left + rect.width / 2,
      y: below ? rect.bottom - box.top : rect.top - box.top,
      below,
    });
  }, []);

  const closePeek = useCallback(() => setPeek(null), []);

  /* ── Pan and zoom ──────────────────────────────────────────────────────
     Free camera movement on top of the framing `cameraFor` computes. `drift`
     only tracks whether the user has moved away from that framing, so the
     "Recenter" affordance can appear; the camera itself is authoritative. */

  const nudge = useCallback(
    (dx: number, dy: number) => {
      cancelAnimationFrame(anim.current);
      camera.current = {
        ...camera.current,
        x: camera.current.x + dx,
        y: camera.current.y + dy,
      };
      drift.current = { x: drift.current.x + dx, y: drift.current.y + dy };
      setDrifted(true);
      paint();
    },
    [paint]
  );

  /* Zooms about a point so the thing under the cursor stays under the cursor —
     without that anchoring, zoom feels like the world is sliding away. */
  const zoomAt = useCallback(
    (factor: number, px?: number, py?: number) => {
      const viewport = viewportRef.current;
      if (!viewport) return;
      cancelAnimationFrame(anim.current);

      const cx = px ?? viewport.clientWidth / 2;
      const cy = py ?? viewport.clientHeight / 2;
      const v = camera.current;
      const k = Math.min(MAX_SCALE, Math.max(MIN_SCALE, v.k * factor));

      camera.current = {
        k,
        x: cx - ((cx - v.x) / v.k) * k,
        y: cy - ((cy - v.y) / v.k) * k,
      };
      drift.current = { x: drift.current.x + 1, y: drift.current.y };
      setDrifted(true);
      paint();
    },
    [paint]
  );

  useEffect(() => {
    const viewport = viewportRef.current;
    if (!viewport) return;

    // Native listener: React's onWheel is passive, so preventDefault (needed to
    // stop ctrl+wheel zooming the whole page) requires this form.
    const onWheel = (event: WheelEvent) => {
      event.preventDefault();
      if (event.ctrlKey || event.metaKey) {
        const rect = viewport.getBoundingClientRect();
        zoomAt(
          Math.exp(-event.deltaY * 0.005),
          event.clientX - rect.left,
          event.clientY - rect.top
        );
      } else {
        nudge(-event.deltaX, -event.deltaY);
      }
    };

    viewport.addEventListener("wheel", onWheel, { passive: false });
    return () => viewport.removeEventListener("wheel", onWheel);
  }, [nudge, zoomAt]);

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    // Drag only from empty canvas — grabbing a node should click it, and
    // grabbing the chrome should not move the world underneath it.
    if ((event.target as HTMLElement).closest("a, button, [data-chrome]")) return;
    dragRef.current = {
      id: event.pointerId,
      x: event.clientX,
      y: event.clientY,
    };
    viewportRef.current?.setPointerCapture(event.pointerId);
    viewportRef.current?.classList.add("is-panning");
  };

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    const drag = dragRef.current;
    if (!drag || drag.id !== event.pointerId) return;
    nudge(event.clientX - drag.x, event.clientY - drag.y);
    dragRef.current = { id: event.pointerId, x: event.clientX, y: event.clientY };
  };

  const endDrag = () => {
    dragRef.current = null;
    viewportRef.current?.classList.remove("is-panning");
  };

  /* Keyboard parity is mandatory, not a nicety: `.brain-viewport` sets
     `touch-action: none` and pan/zoom are pointer gestures, so without these
     the camera is simply unreachable without a mouse (WCAG 2.1.1). */
  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (!viewportRef.current?.offsetParent) return;
      // Never hijack typing, and leave modified keys to the browser.
      const target = event.target as HTMLElement | null;
      if (target?.closest("input, textarea, [contenteditable]")) return;
      if (event.metaKey || event.ctrlKey || event.altKey) return;

      switch (event.key) {
        case "ArrowLeft":
          nudge(PAN_STEP, 0);
          break;
        case "ArrowRight":
          nudge(-PAN_STEP, 0);
          break;
        case "ArrowUp":
          nudge(0, PAN_STEP);
          break;
        case "ArrowDown":
          nudge(0, -PAN_STEP);
          break;
        case "+":
        case "=":
          zoomAt(1.2);
          break;
        case "-":
        case "_":
          zoomAt(1 / 1.2);
          break;
        case "0":
          flyTo(focusId);
          setDrifted(false);
          break;
        default:
          return;
      }
      event.preventDefault();
    };

    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [nudge, zoomAt, flyTo, focusId]);

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

        <div
          ref={viewportRef}
          className="brain-viewport"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
        >
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
                  // The inner wrapper carries scale(1 / camera-k), so the type
                  // inside it is the size it was designed at regardless of depth.
                  <span className="brain-node-chrome">
                    <span className="brain-node-label">{node.label}</span>
                    {hasCount ? (
                      <span className="brain-node-count">{node.count}</span>
                    ) : null}
                    <span className="brain-node-detail">{node.detail}</span>
                  </span>
                );

                // Preview on hover AND focus — a hover-only affordance is
                // invisible to keyboard and touch users.
                const previewHandlers = {
                  onPointerEnter: (event: React.PointerEvent<HTMLElement>) =>
                    openPeek(node, event.currentTarget),
                  onPointerLeave: closePeek,
                  onFocus: (event: React.FocusEvent<HTMLElement>) =>
                    openPeek(node, event.currentTarget),
                  onBlur: closePeek,
                };

                return (
                  <li key={node.id} className="brain-node-slot" style={style}>
                    {node.href ? (
                      <Link
                        href={node.href}
                        className={className}
                        aria-label={`${node.label}${countPhrase}, ${node.detail} — open`}
                        {...previewHandlers}
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
                        {...previewHandlers}
                      >
                        {body}
                      </button>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>

          {/* Decorative: the same facts are already in each node's accessible
              name, so announcing them again on hover would just be noise. */}
          {peek ? (
            <div
              aria-hidden
              data-chrome
              className="brain-peek"
              data-below={peek.below ? "true" : undefined}
              style={{ left: peek.x, top: peek.y }}
            >
              <p className="brain-peek-title">{peek.node.label}</p>
              <p className="brain-peek-detail">{peek.node.detail}</p>
              {peekContents(nodes, peek.node).length > 0 ? (
                <ul className="brain-peek-list">
                  {peekContents(nodes, peek.node).map((child) => (
                    <li key={child.id}>{child.label}</li>
                  ))}
                </ul>
              ) : null}
              {typeof peek.node.count === "number" && peek.node.count > 0 ? (
                <p className="brain-peek-count">
                  {peek.node.count} awaiting you
                </p>
              ) : null}
            </div>
          ) : null}

          <div className="brain-controls" data-chrome>
            {drifted ? (
              <button
                type="button"
                className="brain-control"
                onClick={() => {
                  flyTo(focusId);
                  setDrifted(false);
                }}
              >
                Recenter
                <span className="brain-back-hint" aria-hidden>
                  0
                </span>
              </button>
            ) : null}
            <button
              type="button"
              className="brain-control is-icon"
              onClick={() => zoomAt(1 / 1.25)}
              aria-label="Zoom out"
            >
              <span aria-hidden>&minus;</span>
            </button>
            <button
              type="button"
              className="brain-control is-icon"
              onClick={() => zoomAt(1.25)}
              aria-label="Zoom in"
            >
              <span aria-hidden>+</span>
            </button>
          </div>

          {level > 0 ? (
            <button
              type="button"
              className="brain-back"
              data-chrome
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
