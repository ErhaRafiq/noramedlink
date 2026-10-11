import type { Metadata } from "next";

import { DoctorsView } from "@/components/doctors/DoctorsView";
import { SitePage } from "@/components/layout/SitePage";

export const metadata: Metadata = {
  title: "Find a doctor",
  description: "Book an appointment with a verified doctor.",
};

export default function DoctorsPage() {
  return (
    <SitePage>
      <DoctorsView />
    </SitePage>
  );
}
