import { Navbar } from "@/components/shared/Navbar";
import { Footer } from "@/components/shared/Footer";
import { Hero } from "@/components/sections/Hero";
import { WhatWeDo } from "@/components/sections/WhatWeDo";
import { HowItWorks } from "@/components/sections/HowItWorks";
import { AutonomyBoundaries } from "@/components/sections/AutonomyBoundaries";
import { BuiltFor } from "@/components/sections/BuiltFor";
import { EarlyAccess } from "@/components/sections/EarlyAccess";

export default function LandingPage() {
  return (
    <>
      <Navbar />
      <main>
        <Hero />
        <WhatWeDo />
        <HowItWorks />
        <AutonomyBoundaries />
        <BuiltFor />
        <EarlyAccess />
      </main>
      <Footer />
    </>
  );
}
