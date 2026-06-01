import { Navbar } from "@/components/shared/Navbar";
import { Footer } from "@/components/shared/Footer";
import { HomeHero } from "@/components/landing/HomeHero";
import { WorkflowSteps } from "@/components/landing/WorkflowSteps";
import { SystemPreview } from "@/components/landing/SystemPreview";
import { AgentTeamPreview } from "@/components/landing/AgentTeamPreview";
import { ClosingCTA } from "@/components/landing/ClosingCTA";

export default function LandingPage() {
  return (
    <div className="theme-transition">
      <Navbar />
      <main>
        <HomeHero />
        <WorkflowSteps />
        <SystemPreview />
        <AgentTeamPreview />
        <ClosingCTA />
      </main>
      <Footer />
    </div>
  );
}
