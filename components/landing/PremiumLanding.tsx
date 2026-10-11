import { SiteHeader } from "@/components/layout/SiteHeader";

import { AmbientBackground } from "./AmbientBackground";
import { CallToAction } from "./CallToAction";
import { FeatureGrid } from "./FeatureGrid";
import { Hero } from "./Hero";
import { HowItWorks } from "./HowItWorks";
import { LandingFooter } from "./LandingFooter";
import { SafetyNote } from "./SafetyNote";

const LANDING_LINKS = [
  { href: "/#features", label: "Features" },
  { href: "/#how-it-works", label: "How it works" },
  { href: "/#safety", label: "Safety" },
  { href: "/doctors", label: "Find a doctor" },
  { href: "/about", label: "About" },
];

/** The public landing page. Server component; interactive parts are client islands. */
export function PremiumLanding() {
  return (
    <div className="premium-page">
      <AmbientBackground />
      <SiteHeader links={LANDING_LINKS} />
      <main className="relative">
        <Hero />
        <FeatureGrid />
        <HowItWorks />
        <SafetyNote />
        <CallToAction />
      </main>
      <LandingFooter />
    </div>
  );
}
