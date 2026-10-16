import type { Metadata } from "next";
import { Suspense } from "react";

import { SitePage } from "@/components/layout/SitePage";
import { PageContainer } from "@/components/layout/PageHeader";
import { PaymentReceipt } from "@/components/payments/PaymentReceipt";
import { SkeletonCard } from "@/components/ui/skeleton";

export const metadata: Metadata = {
  title: "Payment receipt",
  description: "Receipt for a consultation fee paid with Stripe.",
};

export default function PaymentReceiptPage() {
  return (
    <SitePage>
      {/* PaymentReceipt reads ?id= from the URL, which needs a Suspense boundary. */}
      <Suspense
        fallback={
          <PageContainer narrow>
            <SkeletonCard lines={4} />
          </PageContainer>
        }
      >
        <PaymentReceipt />
      </Suspense>
    </SitePage>
  );
}
