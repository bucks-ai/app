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
      <main className="min-h-screen bg-[radial-gradient(circle_at_top,_rgba(16,185,129,0.12),_transparent_30%),linear-gradient(180deg,#020202_0%,#050505_35%,#09090b_100%)] px-6 pb-20 pt-28">
        <div className="mx-auto max-w-7xl">
          <IdeaIntakeWizard />
        </div>
      </main>
      <Footer />
    </>
  );
}
