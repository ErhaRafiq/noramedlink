import type { Metadata } from "next";

import { AboutStory } from "@/components/landing/AboutStory";
import { SitePage } from "@/components/layout/SitePage";

export const metadata: Metadata = {
  title: "About",
  description: "Why Nora MedLink exists and the principles it follows.",
};

export default function AboutPage() {
  return (
    <SitePage>
      <AboutStory />
    </SitePage>
  );
}
