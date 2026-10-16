import type { Metadata } from "next";

import { SitePage } from "@/components/layout/SitePage";
import { NotificationsView } from "@/components/notifications/NotificationsView";

export const metadata: Metadata = {
  title: "Notifications",
  description: "Appointment confirmations, changes and reminders.",
};

export default function NotificationsPage() {
  return (
    <SitePage>
      <NotificationsView />
    </SitePage>
  );
}
