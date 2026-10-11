import type { Metadata } from "next";
import { Suspense } from "react";

import { SitePage } from "@/components/layout/SitePage";
import { PaymentsView } from "@/components/payments/PaymentsView";
import { PageContainer } from "@/components/layout/PageHeader";
import { SkeletonCard } from "@/components/ui/skeleton";

export const metadata: Metadata = {
  title: "Payments",
  description: "Record a consultation payment for the clinic to confirm.",
};

export default function PaymentsPage() {
  return (
    <SitePage>
      {/* PaymentsView reads ?appointmentId= from the URL, which needs a Suspense boundary. */}
      <Suspense
        fallback={
          <PageContainer narrow>
            <SkeletonCard lines={6} />
          </PageContainer>
        }
      >
        <PaymentsView />
      </Suspense>
    </SitePage>
  );
}
