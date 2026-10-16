import type { Metadata } from "next";

import { SitePage } from "@/components/layout/SitePage";
import { SymptomChecker } from "@/components/symptoms/SymptomChecker";

export const metadata: Metadata = {
  title: "Check symptoms",
  description: "Describe how you feel and see which kind of doctor to see first. Advisory only; in an emergency call 1122.",
};

export default function SymptomsPage() {
  return (
    <SitePage>
      <SymptomChecker />
    </SitePage>
  );
}
