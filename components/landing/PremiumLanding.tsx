import { AmbientBackground } from "./AmbientBackground";
import { CallToAction } from "./CallToAction";
import { FeatureGrid } from "./FeatureGrid";
import { Hero } from "./Hero";
import { HowItWorks } from "./HowItWorks";
import { LandingFooter } from "./LandingFooter";
import { LandingNav } from "./LandingNav";
import { SafetyNote } from "./SafetyNote";

/** The public landing page. Server component; interactive parts are client islands. */
export function PremiumLanding() {
  return (
    <div className="premium-page">
      <AmbientBackground />
      <LandingNav />
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
