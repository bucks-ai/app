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
      <main className="relative min-h-screen overflow-hidden bg-[#080808] px-5 pb-20 pt-28 sm:px-6">
        <div
          className="pointer-events-none absolute inset-0"
          style={{
            backgroundImage:
              "linear-gradient(rgba(79,70,229,0.025) 1px, transparent 1px), linear-gradient(90deg, rgba(79,70,229,0.025) 1px, transparent 1px)",
            backgroundSize: "64px 64px",
          }}
        />
        <div className="relative mx-auto max-w-7xl">{children}</div>
      </main>
      <Footer />
    </>
  );
}
