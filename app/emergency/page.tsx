import type { Metadata } from "next";

import { EmergencyView } from "@/components/emergency/EmergencyView";
import { SitePage } from "@/components/layout/SitePage";

export const metadata: Metadata = {
  title: "Home visit request",
  description: "Request a home visit. Not an emergency service: in an emergency call 1122.",
};

export default function EmergencyPage() {
  return (
    <SitePage>
      <EmergencyView />
    </SitePage>
  );
}
