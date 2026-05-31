"use client";

import { useState } from "react";
import type { TabKey } from "@/components/workspace/WorkspaceTabs";

type CommandMenuHintProps = {
  onTabChange: (tab: TabKey) => void;
};

const shortcuts: { label: string; tab: TabKey }[] = [
  { label: "Overview", tab: "overview" },
  { label: "Research", tab: "research" },
  { label: "Actions", tab: "actions" },
  { label: "Build", tab: "build" },
  { label: "Deploy", tab: "deploy" },
  { label: "Validation", tab: "validation" },
  { label: "Tools", tab: "tools" },
  { label: "Activity", tab: "activity" },
];

export function CommandMenuHint({ onTabChange }: CommandMenuHintProps) {
  const [open, setOpen] = useState(false);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="rounded border border-[#1C1C1C] bg-[#0F0F0F] px-3 py-2 font-mono text-[10px] uppercase tracking-widest text-[#666] transition-colors hover:border-[#4F46E5]/45 hover:text-[#A5B4FC]"
      >
        Search actions / Cmd K coming soon
      </button>

      {open ? (
        <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/60 px-4 pt-24 backdrop-blur-sm">
          <div className="w-full max-w-md rounded-lg border border-[#1C1C1C] bg-[#0A0A0A] p-3 shadow-2xl">
            <div className="flex items-center justify-between border-b border-[#1C1C1C] px-2 pb-3">
              <p className="font-mono text-[11px] uppercase tracking-[0.2em] text-[#A5B4FC]">
                Workspace shortcuts
              </p>
              <button
                type="button"
                onClick={() => setOpen(false)}
                className="rounded border border-[#1C1C1C] px-2 py-1 font-mono text-[10px] uppercase tracking-widest text-[#666] hover:text-[#F0F0F0]"
              >
                Close
              </button>
            </div>
            <div className="pt-2">
              {shortcuts.map((shortcut) => (
                <button
                  key={shortcut.tab}
                  type="button"
                  onClick={() => {
                    onTabChange(shortcut.tab);
                    setOpen(false);
                  }}
                  className="flex w-full items-center justify-between rounded px-3 py-2.5 text-left text-sm text-[#D4D4D4] transition-colors hover:bg-[#141414]"
                >
                  {shortcut.label}
                  <span className="font-mono text-[10px] uppercase tracking-widest text-[#444]">
                    Open
                  </span>
                </button>
              ))}
            </div>
          </div>
        </div>
      ) : null}
    </>
  );
}
