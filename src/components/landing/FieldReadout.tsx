"use client";

import { useEffect, useState } from "react";

/**
 * Edge-anchored live readouts.
 *
 * The reference site pins small live values to the viewport corners — a
 * clock, a temperature, the cursor's coordinates — which is what makes an
 * otherwise static page feel instrumented rather than printed. That idiom
 * suits an operator console better than it suits a portfolio, so the values
 * here are real ones: the visitor's actual local time and their actual
 * pointer position. Nothing is invented, because a product whose whole claim
 * is honest agent state should not open with fake telemetry.
 *
 * Rendered only after mount — a server-rendered clock is wrong the moment it
 * reaches the client, and reading it out of sync is worse than omitting it.
 */
export function FieldReadout() {
  const [time, setTime] = useState<string | null>(null);
  const [zone, setZone] = useState<string>("");
  const [pos, setPos] = useState<{ x: number; y: number } | null>(null);

  useEffect(() => {
    const fmt = new Intl.DateTimeFormat(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
      hour12: false,
    });

    const tick = () => setTime(fmt.format(new Date()));

    // The first write is deferred into a frame callback rather than run in
    // the effect body: these are client-only values (the server's clock and
    // zone are not the visitor's), and writing state synchronously here both
    // trips react-hooks/set-state-in-effect and risks a hydration mismatch.
    const seed = window.requestAnimationFrame(() => {
      const tz = Intl.DateTimeFormat().resolvedOptions().timeZone ?? "";
      setZone(tz.split("/").pop()?.replace(/_/g, " ") ?? "");
      tick();
    });

    const id = window.setInterval(tick, 1000);

    let frame = 0;
    const onMove = (e: PointerEvent) => {
      if (frame) return;
      frame = window.requestAnimationFrame(() => {
        frame = 0;
        setPos({ x: Math.round(e.clientX), y: Math.round(e.clientY) });
      });
    };
    window.addEventListener("pointermove", onMove, { passive: true });

    return () => {
      window.cancelAnimationFrame(seed);
      window.clearInterval(id);
      window.removeEventListener("pointermove", onMove);
      if (frame) window.cancelAnimationFrame(frame);
    };
  }, []);

  if (!time) return null;

  return (
    <div
      aria-hidden
      className="pointer-events-none absolute inset-x-0 bottom-0 hidden select-none px-6 pb-6 font-mono text-[11px] uppercase tracking-[0.18em] text-muted-foreground md:block"
    >
      <div className="mx-auto flex max-w-6xl items-end justify-between gap-6">
        <span>
          {zone ? `${zone} ` : ""}
          {time}
        </span>
        <span className="tabular-nums">
          {pos ? `${String(pos.x).padStart(4, "0")} X ${String(pos.y).padStart(4, "0")} Y` : "—— X —— Y"}
        </span>
      </div>
    </div>
  );
}
