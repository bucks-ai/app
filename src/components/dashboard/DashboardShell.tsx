import type { ReactNode } from "react";
import { Footer } from "@/components/shared/Footer";
import { Navbar } from "@/components/shared/Navbar";

type DashboardShellProps = {
  children: ReactNode;
};

export function DashboardShell({ children }: DashboardShellProps) {
  return (
    <>
      <Navbar />
      <main className="relative min-h-screen overflow-hidden bg-background px-5 pb-20 pt-28 sm:px-6">
        <div
          aria-hidden
          className="ambient-orbit pointer-events-none absolute left-1/2 top-0 h-[34rem] w-[60rem] -translate-x-1/2 rounded-full opacity-70 blur-3xl"
          style={{ background: "var(--glow)" }}
        />
        <div aria-hidden className="grid-backdrop pointer-events-none absolute inset-0 opacity-50" />
        <div className="relative mx-auto max-w-6xl">{children}</div>
      </main>
      <Footer />
    </>
  );
}
