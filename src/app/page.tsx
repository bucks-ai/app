import { Navbar } from "@/components/shared/Navbar";
import { Footer } from "@/components/shared/Footer";
import { PageField } from "@/components/ui/PageField";
import { FloatingWordmark } from "@/components/landing/FloatingWordmark";
import { HomeHero } from "@/components/landing/HomeHero";
import { WorkflowSteps } from "@/components/landing/WorkflowSteps";
import { ExecutionLoop } from "@/components/landing/ExecutionLoop";
import { SystemPreview } from "@/components/landing/SystemPreview";
import { PhaseExplorer } from "@/components/landing/PhaseExplorer";
import { ClosingCTA } from "@/components/landing/ClosingCTA";

export default function LandingPage() {
  return (
    <div className="theme-transition">
      <Navbar />
      {/* One atmosphere for the entire route. Sections below contribute
          spacing and type, never their own background band. */}
      <PageField />
      <FloatingWordmark />
      <main id="main-content" className="relative">
        <HomeHero />
        <WorkflowSteps />
        <ExecutionLoop />
        <SystemPreview />
        <PhaseExplorer />
        <ClosingCTA />
      </main>
      <Footer />
    </div>
  );
}
