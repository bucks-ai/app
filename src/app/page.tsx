import { Navbar } from "@/components/shared/Navbar";
import { Footer } from "@/components/shared/Footer";
import { CommandHero } from "@/components/landing/CommandHero";
import { ControlRoomStats } from "@/components/landing/ControlRoomStats";
import { FounderTrap } from "@/components/landing/FounderTrap";
import { AgentDepartments } from "@/components/landing/AgentDepartments";
import { AutonomyModel } from "@/components/landing/AutonomyModel";
import { ProductConsoleShowcase } from "@/components/landing/ProductConsoleShowcase";
import { ToolPermissionLayer } from "@/components/landing/ToolPermissionLayer";
import { LaunchTimeline } from "@/components/landing/LaunchTimeline";
import { FinalCTA } from "@/components/landing/FinalCTA";

export default function LandingPage() {
  return (
    <>
      <Navbar />
      <main>
        <CommandHero />
        <ControlRoomStats />
        <FounderTrap />
        <AgentDepartments />
        <AutonomyModel />
        <ProductConsoleShowcase />
        <ToolPermissionLayer />
        <LaunchTimeline />
        <FinalCTA />
      </main>
      <Footer />
    </>
  );
}
