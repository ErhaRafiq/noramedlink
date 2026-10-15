"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { CheckCircle2, Clock, XCircle } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { Alert } from "@/components/ui/alert";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { formatMoney } from "@/lib/money";
import type { Payment } from "@/lib/types";
import { useStoredSession } from "@/hooks/use-stored-session";

const POLL_MS = 2000;
const MAX_POLLS = 8; // Stripe's webhook usually arrives within a few seconds

/** Where Stripe sends the patient after paying. The page only shows what the webhook recorded. */
export function PaymentResult() {
  const sessionId = useSearchParams().get("session_id") ?? "";
  const { ready, session } = useStoredSession();
  const signedIn = session !== null;
  const [payment, setPayment] = useState<Payment | null>(null);
  const [error, setError] = useState("");
  const [gaveUp, setGaveUp] = useState(false);

  useEffect(() => {
    if (!signedIn || !sessionId) return;
    let cancelled = false;
    let timer = 0;
    const poll = (attempt: number) => {
      api
        .paymentForSession(sessionId)
        .then((found) => {
          if (cancelled) return;
          setPayment(found);
          if (found.status === "PENDING") {
            if (attempt + 1 < MAX_POLLS) timer = window.setTimeout(() => poll(attempt + 1), POLL_MS);
            else setGaveUp(true);
          }
        })
        .catch((err: unknown) => {
          if (!cancelled) setError(err instanceof Error ? err.message : "The payment could not be found.");
        });
    };
    poll(0);
    return () => {
      cancelled = true;
      window.clearTimeout(timer);
    };
  }, [sessionId, signedIn]);

  const status = payment?.status ?? "PENDING";
  return (
    <PageContainer narrow>
      <PageHeader eyebrow="Payments" title="Payment result" />
      <section className="rounded-card border border-line bg-white p-6 text-center shadow-card">
        {!sessionId ? (
          <Alert tone="error">This link has no payment session.</Alert>
        ) : ready && !signedIn ? (
          <Alert tone="info">Sign in to see this payment.</Alert>
        ) : error ? (
          <Alert tone="error">{error}</Alert>
        ) : !payment ? (
          <div role="status" aria-label="Checking the payment" className="space-y-3">
            <Skeleton className="mx-auto h-10 w-10 rounded-full" />
            <Skeleton className="mx-auto h-5 w-1/2" />
          </div>
        ) : status === "PAID" ? (
          <>
            <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-600" aria-hidden />
            <h2 className="mt-3 text-lg font-semibold text-ink">Payment received</h2>
            <p className="mt-2 break-words text-sm text-ink-muted">
              {formatMoney(payment.amount, payment.currency)} · {payment.purpose}
            </p>
          </>
        ) : status === "PENDING" ? (
          <>
            <Clock className="mx-auto h-10 w-10 text-amber-500" aria-hidden />
            <h2 className="mt-3 text-lg font-semibold text-ink">{gaveUp ? "Still waiting for Stripe" : "Confirming your payment..."}</h2>
            <p className="mt-2 text-sm text-ink-muted">
              {gaveUp
                ? "Stripe has not confirmed this payment yet. It will show as paid in your payment history once it does."
                : "This takes a few seconds."}
            </p>
          </>
        ) : (
          <>
            <XCircle className="mx-auto h-10 w-10 text-rose-600" aria-hidden />
            <h2 className="mt-3 text-lg font-semibold text-ink">Payment not completed</h2>
            <p className="mt-2 text-sm text-ink-muted">Nothing was charged. You can try again from your payments.</p>
          </>
        )}
        {payment ? <p className="mt-4 inline-block rounded-control bg-surface-soft px-3 py-1.5 font-mono text-xs text-ink">Ref {payment.reference}</p> : null}
        <div className="mt-6">
          <Link href="/payments" className="secondary-button min-h-[40px] px-4 text-sm">
            Back to payments
          </Link>
        </div>
      </section>
    </PageContainer>
  );
}
