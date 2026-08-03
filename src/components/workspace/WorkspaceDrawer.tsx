"use client";

import type { ReactNode } from "react";
import { useEffect, useId, useRef } from "react";

type WorkspaceDrawerProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
};

const FOCUSABLE =
  'a[href],button:not([disabled]),textarea:not([disabled]),input:not([disabled]),select:not([disabled]),[tabindex]:not([tabindex="-1"])';

/**
 * Slide-over panel.
 *
 * It behaves as a modal — it covers the page and Escape closes it — but it
 * carried none of the semantics: no dialog role, no accessible name, focus
 * stayed behind on the trigger, Tab walked straight out into the obscured
 * page, and closing left focus wherever it happened to be. All of that is
 * handled here now; the panel is labelled by its own title.
 */
export function WorkspaceDrawer({
  open,
  onClose,
  title,
  children,
}: WorkspaceDrawerProps) {
  const titleId = useId();
  const panelRef = useRef<HTMLElement>(null);
  const restoreRef = useRef<HTMLElement | null>(null);

  useEffect(() => {
    if (!open) return;

    // Remember where focus came from so it can go back on close.
    restoreRef.current = document.activeElement as HTMLElement | null;

    const panel = panelRef.current;
    panel?.focus();

    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") {
        onClose();
        return;
      }
      if (e.key !== "Tab" || !panel) return;

      const items = Array.from(
        panel.querySelectorAll<HTMLElement>(FOCUSABLE),
      ).filter((el) => el.offsetParent !== null);
      if (items.length === 0) {
        e.preventDefault();
        panel.focus();
        return;
      }

      const first = items[0];
      const last = items[items.length - 1];
      const active = document.activeElement;

      if (e.shiftKey && (active === first || active === panel)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && active === last) {
        e.preventDefault();
        first.focus();
      }
    }

    window.addEventListener("keydown", handleKey);
    return () => {
      window.removeEventListener("keydown", handleKey);
      restoreRef.current?.focus?.();
    };
  }, [open, onClose]);

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex justify-end">
      {/* Backdrop */}
      <div
        className="absolute inset-0 bg-black/60 backdrop-blur-sm"
        onClick={onClose}
        aria-hidden="true"
      />

      {/* Panel */}
      <aside
        ref={panelRef}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        tabIndex={-1}
        className="glass-surface relative z-10 flex h-full w-full max-w-xl flex-col border-l border-border shadow-2xl outline-none"
      >
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <p
            id={titleId}
            className="font-mono text-xs uppercase tracking-[0.24em] text-accent"
          >
            {title}
          </p>
          <button
            type="button"
            onClick={onClose}
            className="min-h-11 rounded-lg border border-border bg-elevated px-3 py-2 font-mono text-[11px] uppercase tracking-widest text-foreground-secondary transition-colors hover:border-accent/40 hover:text-foreground"
          >
            Close
          </button>
        </div>

        {/* Content */}
        <div className="flex-1 overflow-y-auto p-5">{children}</div>
      </aside>
    </div>
  );
}
