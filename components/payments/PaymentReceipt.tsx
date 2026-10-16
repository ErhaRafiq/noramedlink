"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useEffect, useState } from "react";
import { ArrowLeft, Printer } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { Alert } from "@/components/ui/alert";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import { formatDateTime } from "@/lib/datetime";
import { formatMoney } from "@/lib/money";
import type { Payment } from "@/lib/types";
import { useStoredSession } from "@/hooks/use-stored-session";

const STATUS: Record<string, { label: string; tone: BadgeTone }> = {
  PAID: { label: "Paid", tone: "success" },
  REFUND_PENDING: { label: "Refund on its way", tone: "info" },
  REFUNDED: { label: "Refunded", tone: "neutral" },
  REFUND_FAILED: { label: "Refund needs attention", tone: "danger" },
};

/** A printable receipt for one of the signed-in patient's own payments. It shows only what the server recorded. */
export function PaymentReceipt() {
  const id = Number(useSearchParams().get("id")) || null;
  const { ready, session } = useStoredSession();
  const signedIn = session !== null;
  const [payment, setPayment] = useState<Payment | null>(null);
  const [error, setError] = useState("");

  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!signedIn || !id) return;
    let live = true;
    api
      .payment(id)
      .then((found) => live && setPayment(found))
      .catch((err: unknown) => live && setError(err instanceof Error ? err.message : "The receipt could not be loaded."));
    return () => {
      live = false;
    };
  }, [signedIn, id, attempt]);

  function retry() {
    setError("");
    setAttempt((n) => n + 1);
  }

  const known = payment ? (STATUS[payment.status.toUpperCase()] ?? { label: payment.status.toLowerCase(), tone: "neutral" as const }) : null;

  return (
    <PageContainer narrow>
      <PageHeader eyebrow="Payments" title="Payment receipt" />
      {!id ? (
        <Alert tone="error">This link has no payment.</Alert>
      ) : ready && !signedIn ? (
        <Alert tone="info">Sign in to see this receipt.</Alert>
      ) : error ? (
        <Alert tone="error" title="Receipt not available">
          {error}{" "}
          <button type="button" onClick={retry} className="font-semibold underline">
            Try again
          </button>
        </Alert>
      ) : !payment || !known ? (
        <div role="status" aria-label="Loading the receipt" className="space-y-3 rounded-card border border-line bg-white p-6 shadow-card">
          <Skeleton className="h-6 w-1/3" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-2/3" />
          <Skeleton className="h-4 w-1/2" />
        </div>
      ) : (
        <article aria-label="Receipt" className="rounded-card border border-line bg-white p-5 shadow-card sm:p-6">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div className="min-w-0">
              <p className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Receipt</p>
              <p className="break-words text-lg font-semibold text-ink">{payment.invoice_number ?? payment.reference}</p>
            </div>
            <Badge tone={known.tone}>{known.label}</Badge>
          </div>

          <dl className="mt-5 grid gap-x-6 gap-y-3 text-sm sm:grid-cols-2">
            <Row label="For" value={payment.purpose} />
            <Row label="Billed to" value={session?.user.full_name ?? ""} />
            <Row label="Amount" value={formatMoney(payment.amount, payment.currency)} strong />
            <Row label="Paid with" value="Card, through Stripe" />
            <Row label="Paid on" value={formatDateTime(payment.paid_at ?? payment.created_at)} />
            <Row label="Payment reference" value={payment.reference} />
            {payment.status === "REFUNDED" && payment.refunded_at ? <Row label="Refunded on" value={formatDateTime(payment.refunded_at)} /> : null}
          </dl>

          {payment.status === "REFUND_PENDING" ? (
            <Alert tone="info" className="mt-5">
              The appointment was cancelled and a full refund was requested. Your bank may take several days to show it.
            </Alert>
          ) : null}
          {payment.status === "REFUND_FAILED" ? (
            <Alert tone="error" className="mt-5">
              The appointment was cancelled, but the refund could not be requested automatically. Please contact support and quote reference{" "}
              {payment.reference}.
            </Alert>
          ) : null}

          <p className="mt-5 text-xs leading-5 text-ink-muted">
            Nora MedLink is an academic prototype running in Stripe test mode. This receipt is not an official tax invoice.
          </p>

          <div className="mt-5 flex flex-wrap gap-2 print:hidden">
            <Button variant="secondary" icon={<Printer className="h-4 w-4" />} onClick={() => window.print()}>
              Print receipt
            </Button>
            <Link href="/payments" className="secondary-button inline-flex items-center gap-2">
              <ArrowLeft className="h-4 w-4" aria-hidden />
              Back to payments
            </Link>
          </div>
        </article>
      )}
    </PageContainer>
  );
}

function Row({ label, value, strong = false }: { label: string; value: string; strong?: boolean }) {
  return (
    <div className="min-w-0">
      <dt className="text-xs text-ink-muted">{label}</dt>
      <dd className={strong ? "break-words text-base font-semibold text-ink" : "break-words text-ink"}>{value}</dd>
    </div>
  );
}
