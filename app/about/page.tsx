import type { Metadata } from "next";

import { AboutStory } from "@/components/landing/AboutStory";

export const metadata: Metadata = {
  title: "About Nora MedLink",
  description: "The human-centered story behind Nora MedLink.",
};

export default function AboutPage() {
  return <AboutStory />;
}
