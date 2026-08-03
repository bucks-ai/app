import type { Metadata } from "next";
import { IdeaIntakeWizard } from "@/components/intake/IdeaIntakeWizard";
import { Footer } from "@/components/shared/Footer";
import { Navbar } from "@/components/shared/Navbar";
import { PageField } from "@/components/ui/PageField";

export const metadata: Metadata = {
  title: "Idea Intake | bucks.ai",
  description:
    "Turn an AI/software startup idea into a mock launch blueprint with stack, GTM, permissions, analytics, and next autonomous actions.",
};

export default function IntakePage() {
  return (
    <>
      <Navbar />
      {/* Last route still painting its own background and grid instead of
          using the shared field. */}
      <PageField />
      <main
        id="main-content"
        className="relative min-h-screen overflow-clip px-5 pb-24 pt-32 sm:px-6"
      >
        <div className="relative mx-auto max-w-7xl">
          <IdeaIntakeWizard />
        </div>
      </main>
      <Footer />
    </>
  );
}
