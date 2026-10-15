import type { Metadata } from "next";
import { Suspense } from "react";

import { SitePage } from "@/components/layout/SitePage";
import { PageContainer } from "@/components/layout/PageHeader";
import { PaymentResult } from "@/components/payments/PaymentResult";
import { SkeletonCard } from "@/components/ui/skeleton";

export const metadata: Metadata = {
  title: "Payment result",
  description: "The result of a consultation payment made with Stripe.",
};

export default function PaymentResultPage() {
  return (
    <SitePage>
      {/* PaymentResult reads ?session_id= from the URL, which needs a Suspense boundary. */}
      <Suspense
        fallback={
          <PageContainer narrow>
            <SkeletonCard lines={3} />
          </PageContainer>
        }
      >
        <PaymentResult />
      </Suspense>
    </SitePage>
  );
}
