import type { Metadata } from "next";

import { SitePage } from "@/components/layout/SitePage";
import { ProfileView } from "@/components/profile/ProfileView";

export const metadata: Metadata = {
  title: "My profile",
  description: "Your account details and, for doctors, the profile patients see.",
};

export default function ProfilePage() {
  return (
    <SitePage>
      <ProfileView />
    </SitePage>
  );
}
