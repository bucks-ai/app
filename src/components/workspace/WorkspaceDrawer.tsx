"use client";

import type { ReactNode } from "react";
import { useEffect } from "react";

type WorkspaceDrawerProps = {
  open: boolean;
  onClose: () => void;
  title: string;
  children: ReactNode;
};

export function WorkspaceDrawer({
  open,
  onClose,
  title,
  children,
}: WorkspaceDrawerProps) {
  useEffect(() => {
    if (!open) return;
    function handleKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    window.addEventListener("keydown", handleKey);
    return () => window.removeEventListener("keydown", handleKey);
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
      <aside className="relative z-10 flex h-full w-full max-w-xl flex-col border-l border-border bg-surface shadow-2xl">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border px-5 py-4">
          <p className="font-mono text-xs uppercase tracking-[0.24em] text-accent">
            {title}
          </p>
          <button
            type="button"
            onClick={onClose}
            className="rounded border border-border bg-elevated px-3 py-1.5 font-mono text-[11px] uppercase tracking-widest text-secondary transition-colors hover:text-foreground"
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
