import type { Metadata } from "next";
import { IdeaIntakeWizard } from "@/components/intake/IdeaIntakeWizard";
import { Footer } from "@/components/shared/Footer";
import { Navbar } from "@/components/shared/Navbar";

export const metadata: Metadata = {
  title: "Idea Intake | bucks.ai",
  description:
    "Turn an AI/software startup idea into a mock launch blueprint with stack, GTM, permissions, analytics, and next autonomous actions.",
};

export default function IntakePage() {
  return (
    <>
      <Navbar />
      <main className="relative min-h-screen overflow-clip bg-background px-5 pb-20 pt-28 sm:px-6">
        <div aria-hidden className="grid-backdrop pointer-events-none absolute inset-0" />
        <div className="relative mx-auto max-w-7xl">
          <IdeaIntakeWizard />
        </div>
      </main>
      <Footer />
    </>
  );
}
