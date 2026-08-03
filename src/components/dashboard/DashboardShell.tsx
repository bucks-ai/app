import type { ReactNode } from "react";
import { Footer } from "@/components/shared/Footer";
import { Navbar } from "@/components/shared/Navbar";
import { PageField } from "@/components/ui/PageField";

type DashboardShellProps = {
  children: ReactNode;
};

export function DashboardShell({ children }: DashboardShellProps) {
  return (
    <>
      <Navbar />
      {/* Same atmosphere as the marketing routes, so crossing from the
          landing page into the console reads as one product rather than two
          separately-styled apps. */}
      <PageField />
      <main id="main-content" className="relative min-h-screen px-5 pb-24 pt-32 sm:px-6">
        <div className="relative mx-auto max-w-6xl">{children}</div>
      </main>
      <Footer />
    </>
  );
}
