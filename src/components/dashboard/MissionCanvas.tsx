"use client";

import Link from "next/link";
import {
  useCallback,
  useEffect,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { ActivityLog } from "@/components/dashboard/ActivityLog";
import { HumanActionQueue } from "@/components/dashboard/HumanActionQueue";
import type { ActivityItem, HumanAction, StatusVariant } from "@/components/dashboard/mock-data";
import { StatusPill } from "@/components/ui/StatusPill";

export type CanvasBusiness = {
  id: string;
  name: string;
  status: string;
  statusVariant: StatusVariant;
  goal: string;
  businessType: string;
};

type MissionCanvasProps = {
  businesses: CanvasBusiness[];
  humanActions: HumanAction[];
  activity: ActivityItem[];
  deploys: number;
  blockers: number;
  sample?: boolean;
};

/* World-space layout. One fixed coordinate system; pan/zoom is a single
   transform on `.canvas-world`, so nothing here ever reflows. */
const WORLD_W = 1400;
const WORLD_H = 1100;
const HUB = { x: WORLD_W / 2, y: 520 };
const MIN_SCALE = 0.45;
const MAX_SCALE = 1.6;

type BranchKey = "workspaces" | "approvals" | "activity" | "deploys";

type BranchDef = {
  key: BranchKey;
  label: string;
  x: number;
  y: number;
  tone: "accent" | "warning" | "danger" | "neutral";
  live: boolean;
  count: number;
  detail: string;
  /** Bottom-row branches open their panel upward so it stays in frame. */
  up?: boolean;
};

type LinkNodeDef = {
  key: string;
  label: string;
  detail: string;
  href: string;
  x: number;
  y: number;
  primary?: boolean;
};

const toneText: Record<BranchDef["tone"], string> = {
  accent: "text-accent-on-tint",
  warning: "text-warning",
  danger: "text-error",
  neutral: "text-foreground-secondary",
};

function edgePath(x: number, y: number) {
  const mx = (HUB.x + x) / 2;
  return `M ${HUB.x} ${HUB.y} C ${mx} ${HUB.y}, ${mx} ${y}, ${x} ${y}`;
}

/**
 * The dashboard as a pannable, zoomable node canvas (n8n-style).
 *
 * - Navigation is pan (drag / wheel) and zoom (ctrl+wheel / buttons), not
 *   page scroll. The viewport contains its own gestures and never hijacks
 *   document scrolling.
 * - Pan/zoom state lives in refs and is written straight to one transform
 *   via rAF — no React re-render per pointermove, no layout properties.
 * - Edges are a single SVG layer; a dash animation runs only on lanes with
 *   live work (honest motion), and reduced-motion parks it.
 * - Branch panels are mounted only while expanded, so off-screen content
 *   costs nothing.
 * - Below lg the canvas is replaced by a stacked accordion of the same
 *   branches — touch users get taps, not drag-required interactions.
 */
export function MissionCanvas({
  businesses,
  humanActions,
  activity,
  deploys,
  blockers,
  sample = false,
}: MissionCanvasProps) {
  // "Live" motion is a claim that work is waiting on a lane. Sample data is
  // static by definition, so it never animates.
  const branches: BranchDef[] = [
    {
      key: "workspaces",
      label: "Workspaces",
      x: 250,
      y: 290,
      tone: "accent",
      live: !sample && businesses.length > 0,
      count: businesses.length,
      detail: sample ? "sample records" : "saved builds",
    },
    {
      key: "approvals",
      label: "Needs you",
      x: 1150,
      y: 290,
      tone: humanActions.length > 0 ? "warning" : "neutral",
      live: !sample && humanActions.length > 0,
      count: humanActions.length,
      detail: humanActions.length > 0 ? "decisions waiting" : "queue clear",
    },
    {
      key: "deploys",
      label: "Deploys",
      x: 250,
      y: 790,
      tone: "accent",
      live: !sample && deploys > 0,
      count: deploys,
      detail: "live previews",
      up: true,
    },
    {
      key: "activity",
      label: "Activity",
      x: 1150,
      y: 790,
      tone: "neutral",
      live: false,
      count: activity.length,
      detail: "recent agent events",
      up: true,
    },
  ];

  const linkNodes: LinkNodeDef[] = [
    {
      key: "intake",
      label: "New business",
      detail: "start with an idea",
      href: "/intake",
      x: WORLD_W / 2,
      y: 200,
      primary: true,
    },
    {
      key: "tools",
      label: "Tool registry",
      detail: "permissions & stack",
      href: "/tools",
      x: WORLD_W / 2,
      y: 900,
    },
  ];

  const [open, setOpen] = useState<Record<BranchKey, boolean>>({
    workspaces: true,
    approvals: humanActions.length > 0,
    activity: false,
    deploys: false,
  });
  const toggle = useCallback(
    (key: BranchKey) => setOpen((prev) => ({ ...prev, [key]: !prev[key] })),
    []
  );

  /* ── pan / zoom ── */
  const viewportRef = useRef<HTMLDivElement>(null);
  const worldRef = useRef<HTMLDivElement>(null);
  const view = useRef({ x: 0, y: 0, k: 0.85 });
  const raf = useRef(0);
  const drag = useRef<{ id: number; sx: number; sy: number; ox: number; oy: number } | null>(null);

  const apply = useCallback(() => {
    cancelAnimationFrame(raf.current);
    raf.current = requestAnimationFrame(() => {
      const { x, y, k } = view.current;
      if (worldRef.current) {
        worldRef.current.style.transform = `translate3d(${x}px, ${y}px, 0) scale(${k})`;
      }
    });
  }, []);

  const center = useCallback(() => {
    const vp = viewportRef.current;
    if (!vp) return;
    // Never fit below 0.8: an all-in-frame view where no label is legible is
    // worse than a view you pan. Labels stay readable; edges invite panning.
    const k = Math.min(1, Math.max(0.8, vp.clientWidth / (WORLD_W + 100)));
    view.current = {
      k,
      x: vp.clientWidth / 2 - HUB.x * k,
      y: vp.clientHeight / 2 - HUB.y * k,
    };
    apply();
  }, [apply]);

  const zoomAt = useCallback(
    (factor: number, px?: number, py?: number) => {
      const vp = viewportRef.current;
      if (!vp) return;
      const cx = px ?? vp.clientWidth / 2;
      const cy = py ?? vp.clientHeight / 2;
      const v = view.current;
      const k = Math.min(MAX_SCALE, Math.max(MIN_SCALE, v.k * factor));
      // Keep the point under the cursor fixed while scale changes.
      view.current = {
        k,
        x: cx - ((cx - v.x) / v.k) * k,
        y: cy - ((cy - v.y) / v.k) * k,
      };
      apply();
    },
    [apply]
  );

  useEffect(() => {
    center();
    const vp = viewportRef.current;
    if (!vp) return;
    // Native listener: React's onWheel is passive, so preventDefault (needed
    // to keep ctrl+wheel from zooming the whole page) requires this form.
    const onWheel = (e: WheelEvent) => {
      // A wheel over a scrollable open panel scrolls that panel natively —
      // panning the world underneath a list you are reading is hostile.
      const panel = (e.target as HTMLElement).closest?.("[data-panel]");
      if (
        panel instanceof HTMLElement &&
        panel.scrollHeight > panel.clientHeight &&
        !e.ctrlKey &&
        !e.metaKey
      ) {
        return;
      }
      e.preventDefault();
      if (e.ctrlKey || e.metaKey) {
        const rect = vp.getBoundingClientRect();
        zoomAt(Math.exp(-e.deltaY * 0.005), e.clientX - rect.left, e.clientY - rect.top);
      } else {
        view.current.x -= e.deltaX;
        view.current.y -= e.deltaY;
        apply();
      }
    };
    vp.addEventListener("wheel", onWheel, { passive: false });
    // Recenter on viewport resize so the hub can never be stranded offscreen.
    const ro = new ResizeObserver(center);
    ro.observe(vp);
    return () => {
      vp.removeEventListener("wheel", onWheel);
      ro.disconnect();
    };
  }, [center, zoomAt, apply]);

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    // Only pan from the canvas background — dragging a node or panel should
    // scroll/click as normal.
    if ((e.target as HTMLElement).closest("a, button, [data-panel]")) return;
    drag.current = {
      id: e.pointerId,
      sx: e.clientX,
      sy: e.clientY,
      ox: view.current.x,
      oy: view.current.y,
    };
    viewportRef.current?.setPointerCapture(e.pointerId);
    viewportRef.current?.classList.add("is-panning");
  };
  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const d = drag.current;
    if (!d || d.id !== e.pointerId) return;
    view.current.x = d.ox + (e.clientX - d.sx);
    view.current.y = d.oy + (e.clientY - d.sy);
    apply();
  };
  const endDrag = () => {
    drag.current = null;
    viewportRef.current?.classList.remove("is-panning");
  };

  const panelFor = (key: BranchKey): ReactNode => {
    switch (key) {
      case "workspaces":
        return <WorkspaceList businesses={businesses} sample={sample} />;
      case "approvals":
        return humanActions.length > 0 ? (
          <HumanActionQueue actions={humanActions} />
        ) : (
          <EmptyNote text="No pending approvals. Anything needing your sign-off lands here." />
        );
      case "activity":
        return activity.length > 0 ? (
          <ActivityLog items={activity} />
        ) : (
          <EmptyNote text="Activity appears once a blueprint is saved." />
        );
      case "deploys":
        return (
          <EmptyNote
            text={
              deploys > 0
                ? `${deploys} build${deploys === 1 ? "" : "s"} with live deployment state. Open a workspace for the preview URL.`
                : "No live deployments yet. Ship a build and its preview lands here."
            }
          />
        );
    }
  };

  const dotClass = `h-1.5 w-1.5 rounded-full bg-accent-bright${sample ? "" : " pulse-dot"}`;

  const hub = (
    <div className="cloud-hub cloud-bob flex h-52 w-52 flex-col items-center justify-center text-center">
      <span className="inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.18em] text-accent-on-tint">
        <span aria-hidden className={dotClass} />
        Mission Control
      </span>
      <p className="mt-2 font-mono text-4xl font-semibold text-foreground">
        {businesses.length}
      </p>
      <p className="mt-1 font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
        {sample ? "sample workspaces" : "active workspaces"}
      </p>
      {blockers > 0 ? (
        <p className="mt-2 font-mono text-[10px] uppercase tracking-[0.14em] text-error">
          {blockers} blocker{blockers === 1 ? "" : "s"}
        </p>
      ) : null}
    </div>
  );

  return (
    <>
      {/* lg+: the canvas */}
      <section
        aria-label="Mission canvas"
        className="relative hidden h-[calc(100dvh-4.5rem)] overflow-hidden lg:block"
      >
        <div
          ref={viewportRef}
          className="canvas-viewport absolute inset-0"
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={endDrag}
          onPointerCancel={endDrag}
        >
          <div
            ref={worldRef}
            className="canvas-world absolute left-0 top-0"
            style={{ width: WORLD_W, height: WORLD_H }}
          >
            <svg
              aria-hidden
              className="absolute inset-0 h-full w-full"
              viewBox={`0 0 ${WORLD_W} ${WORLD_H}`}
              fill="none"
            >
              {[...branches, ...linkNodes].map((n) => (
                <path
                  key={n.key}
                  d={edgePath(n.x, n.y)}
                  className={"live" in n && n.live ? "rail-flow" : undefined}
                  stroke={
                    "live" in n && n.live
                      ? "color-mix(in srgb, var(--accent) 55%, transparent)"
                      : "color-mix(in srgb, var(--edge-strong) 85%, transparent)"
                  }
                  strokeWidth="2"
                />
              ))}
            </svg>

            <div
              className="absolute -translate-x-1/2 -translate-y-1/2"
              style={{ left: HUB.x, top: HUB.y }}
            >
              {hub}
            </div>

            {branches.map((b, i) => (
              <div
                key={b.key}
                className="absolute w-[24rem] -translate-x-1/2"
                style={{ left: b.x, top: b.y - 28 }}
              >
                {/* Bob only while collapsed: ambient drift on an empty pill
                    sells the cloud; drift under text someone is reading is
                    friction. */}
                <div
                  className={`relative ${
                    open[b.key] ? "" : i % 2 ? "cloud-bob-late" : "cloud-bob"
                  }`}
                >
                  <BranchPill
                    branch={b}
                    open={open[b.key]}
                    onToggle={() => toggle(b.key)}
                  />
                  {open[b.key] ? (
                    <div
                      data-panel
                      className={`cloud-panel max-h-[24rem] overflow-y-auto p-4 ${
                        b.up ? "absolute bottom-full mb-3 w-full" : "mt-3"
                      }`}
                      style={{ contentVisibility: "auto" }}
                    >
                      {panelFor(b.key)}
                    </div>
                  ) : null}
                </div>
              </div>
            ))}

            {linkNodes.map((n) => (
              <Link
                key={n.key}
                href={n.href}
                className={`cloud-node absolute flex min-h-14 -translate-x-1/2 -translate-y-1/2 items-center gap-3 px-6 py-3 ${
                  n.primary
                    ? "border-accent/50 shadow-[0_0_32px_color-mix(in_srgb,var(--accent)_22%,transparent)]"
                    : ""
                }`}
                style={{ left: n.x, top: n.y }}
              >
                <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-foreground">
                  {n.label}
                </span>
                <span className="text-xs text-foreground-secondary">{n.detail}</span>
                <span aria-hidden className="text-accent-on-tint">
                  &#8594;
                </span>
              </Link>
            ))}
          </div>
        </div>

        {/* canvas controls */}
        <div className="absolute bottom-5 right-5 flex items-center gap-2">
          <CanvasButton label="Zoom out" onClick={() => zoomAt(1 / 1.25)}>
            &#8722;
          </CanvasButton>
          <CanvasButton label="Zoom in" onClick={() => zoomAt(1.25)}>
            +
          </CanvasButton>
          <CanvasButton label="Recenter canvas" onClick={center}>
            &#8853;
          </CanvasButton>
        </div>
        <p className="pointer-events-none absolute bottom-6 left-5 font-mono text-[10px] uppercase tracking-[0.16em] text-muted-foreground">
          drag to pan · ctrl+scroll to zoom
        </p>
      </section>

      {/* below lg: same branches as a stacked accordion */}
      <div className="space-y-3 px-5 pb-24 pt-6 lg:hidden">
        <div className="cloud-panel p-5 text-center">
          <span className="inline-flex items-center gap-2 font-mono text-[11px] uppercase tracking-[0.18em] text-accent-on-tint">
            <span aria-hidden className={dotClass} />
            Mission Control · {businesses.length} {sample ? "sample" : "active"}
          </span>
        </div>
        <Link
          href="/intake"
          className="cloud-node flex min-h-12 items-center justify-between px-5 py-3"
        >
          <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-foreground">
            New business
          </span>
          <span aria-hidden className="text-accent-on-tint">
            &#8594;
          </span>
        </Link>
        {[...branches].sort((a, b) => Number(b.live) - Number(a.live)).map((b) => (
          <div key={b.key}>
            <BranchPill branch={b} open={open[b.key]} onToggle={() => toggle(b.key)} />
            {open[b.key] ? (
              <div className="cloud-panel mt-2 p-4">{panelFor(b.key)}</div>
            ) : null}
          </div>
        ))}
        <div className="flex flex-col gap-3 pt-2">
          {linkNodes.filter((n) => !n.primary).map((n) => (
            <Link
              key={n.key}
              href={n.href}
              className="cloud-node flex min-h-12 items-center justify-between px-5 py-3"
            >
              <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-foreground">
                {n.label}
              </span>
              <span aria-hidden className="text-accent-on-tint">
                &#8594;
              </span>
            </Link>
          ))}
        </div>
      </div>
    </>
  );
}

function BranchPill({
  branch,
  open,
  onToggle,
}: {
  branch: BranchDef;
  open: boolean;
  onToggle: () => void;
}) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      className="cloud-node flex min-h-12 w-full items-center justify-between gap-3 px-5 py-3 text-left"
    >
      <span className="flex items-baseline gap-3">
        <span className="font-mono text-[11px] uppercase tracking-[0.16em] text-muted-foreground">
          {branch.label}
        </span>
        <span className={`font-mono text-lg font-semibold ${toneText[branch.tone]}`}>
          {branch.count}
        </span>
      </span>
      <span className="flex items-center gap-2">
        <span className="truncate text-xs text-foreground-secondary">
          {branch.detail}
        </span>
        <span
          aria-hidden
          className={`text-muted-foreground transition-transform duration-200 ${
            open ? "rotate-180" : ""
          }`}
        >
          &#9662;
        </span>
      </span>
    </button>
  );
}

function WorkspaceList({
  businesses,
  sample,
}: {
  businesses: CanvasBusiness[];
  sample: boolean;
}) {
  if (businesses.length === 0) {
    return (
      <div className="text-center">
        <EmptyNote text="No businesses yet. bucks.ai turns an idea into an execution-ready MVP." />
        <Link
          href="/intake"
          className="cloud-node mt-3 inline-flex min-h-11 items-center gap-2 px-5 py-2.5 text-sm font-medium text-foreground"
        >
          Start with an idea <span aria-hidden>&#8594;</span>
        </Link>
      </div>
    );
  }
  return (
    <ul className="space-y-2">
      {businesses.map((b) => (
        <li key={b.id}>
          <Link
            href={sample ? "/dashboard" : `/dashboard/businesses/${b.id}`}
            className="interactive-surface block rounded-2xl border border-edge bg-[var(--surface-raised)] px-4 py-3"
          >
            <span className="flex items-center justify-between gap-3">
              <span className="truncate text-sm font-semibold text-foreground">
                {b.name}
              </span>
              <StatusPill label={b.status} variant={b.statusVariant} />
            </span>
            <span className="mt-1 block truncate text-xs text-foreground-secondary">
              {b.businessType} · {b.goal}
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}

function EmptyNote({ text }: { text: string }) {
  return (
    <p className="rounded-2xl border border-edge bg-background/60 p-4 text-sm leading-6 text-muted-foreground">
      {text}
    </p>
  );
}

function CanvasButton({
  label,
  onClick,
  children,
}: {
  label: string;
  onClick: () => void;
  children: ReactNode;
}) {
  return (
    <button
      type="button"
      aria-label={label}
      onClick={onClick}
      className="cloud-node flex h-11 w-11 items-center justify-center text-lg text-foreground-secondary hover:text-foreground"
    >
      {children}
    </button>
  );
}
