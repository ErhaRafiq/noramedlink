import type { Metadata } from "next";

import { HomeVisitView } from "@/components/home-visits/HomeVisitView";
import { SitePage } from "@/components/layout/SitePage";

export const metadata: Metadata = {
  title: "Home visit",
  description: "Ask for a doctor at home for a problem that is not an emergency. Not an emergency service: in an emergency call 1122.",
};

export default function EmergencyPage() {
  return (
    <SitePage>
      <HomeVisitView />
    </SitePage>
  );
}
