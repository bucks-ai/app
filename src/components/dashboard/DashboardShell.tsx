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
          className="pointer-events-none absolute inset-x-0 top-0 h-[420px]"
          style={{ background: "var(--glow)" }}
        />
        <div className="relative mx-auto max-w-6xl">{children}</div>
      </main>
      <Footer />
    </>
  );
}
