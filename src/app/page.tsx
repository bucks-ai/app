import { Navbar } from "@/components/shared/Navbar";
import { Footer } from "@/components/shared/Footer";
import { PageField } from "@/components/ui/PageField";
import { HomeHero } from "@/components/landing/HomeHero";
import { WorkflowSteps } from "@/components/landing/WorkflowSteps";
import { ExecutionLoop } from "@/components/landing/ExecutionLoop";
import { SystemPreview } from "@/components/landing/SystemPreview";
import { AgentTeamPreview } from "@/components/landing/AgentTeamPreview";
import { ClosingCTA } from "@/components/landing/ClosingCTA";

export default function LandingPage() {
  return (
    <div className="theme-transition">
      <Navbar />
      {/* One atmosphere for the entire route. Sections below contribute
          spacing and type, never their own background band. */}
      <PageField />
      <main id="main-content">
        <HomeHero />
        <WorkflowSteps />
        <ExecutionLoop />
        <SystemPreview />
        <AgentTeamPreview />
        <ClosingCTA />
      </main>
      <Footer />
    </div>
  );
}
