"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { CreditCard, Receipt, ShieldCheck, Wallet } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { Alert } from "@/components/ui/alert";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/datetime";
import { formatMoney } from "@/lib/money";
import type { Appointment, Payment } from "@/lib/types";
import { useStoredSession } from "@/hooks/use-stored-session";
import { usePayments } from "@/hooks/payments/use-payments";

const STATUS: Record<string, { label: string; tone: BadgeTone }> = {
  PAID: { label: "Paid", tone: "success" },
  PENDING: { label: "Not completed", tone: "warning" },
  EXPIRED: { label: "Expired", tone: "neutral" },
  FAILED: { label: "Failed", tone: "danger" },
};

function statusBadge(status: string) {
  const known = STATUS[status.toUpperCase()] ?? { label: status.replaceAll("_", " ").toLowerCase(), tone: "neutral" as const };
  return <Badge tone={known.tone}>{known.label}</Badge>;
}

export function PaymentsView() {
  const searchParams = useSearchParams();
  const highlighted = Number(searchParams.get("appointmentId")) || null;
  const cancelled = searchParams.get("cancelled") === "1";
  const { ready, session } = useStoredSession();
  const data = usePayments(session?.user.role === "patient");

  return (
    <PageContainer narrow>
      <PageHeader eyebrow="Payments" title="Consultation payments" description="Pay your doctor's consultation fee by card on Stripe's secure page." />

      {cancelled ? (
        <Alert tone="info" className="mb-6" title="Payment not completed">
          You left the payment page before paying. Nothing was charged; you can pay again below.
        </Alert>
      ) : null}

      {!ready ? (
        <SkeletonList />
      ) : !session || session.user.role !== "patient" ? (
        <section className="rounded-card border border-line bg-white p-5 shadow-card sm:p-6">
          <EmptyState
            icon={Wallet}
            title="Sign in as a patient to pay"
            description="Payments are made for your own appointments."
            action={
              <Link href="/login" className="secondary-button min-h-[36px] px-3 text-xs">
                Sign in
              </Link>
            }
          />
        </section>
      ) : data.status === "loading" ? (
        <SkeletonList />
      ) : data.status === "error" ? (
        <Alert tone="error" title="Payments could not be loaded">
          {data.error}{" "}
          <button type="button" onClick={() => void data.reload()} className="font-semibold underline">
            Try again
          </button>
        </Alert>
      ) : (
        <div className="space-y-6">
          <section aria-labelledby="to-pay-title" className="rounded-card border border-line bg-white p-5 shadow-card sm:p-6">
            <h2 id="to-pay-title" className="text-base font-semibold text-ink">
              Appointments to pay
            </h2>
            {data.toPay.length === 0 ? (
              <EmptyState icon={CreditCard} title="Nothing to pay" description="Unpaid appointments appear here after you book." />
            ) : (
              <ul className="mt-4 space-y-3">
                {data.toPay.map((appointment) => (
                  <ToPayItem
                    key={appointment.id}
                    appointment={appointment}
                    highlighted={appointment.id === highlighted}
                    paying={data.payingId === appointment.id}
                    disabled={data.payingId !== null}
                    error={data.payError?.appointmentId === appointment.id ? data.payError.message : ""}
                    onPay={() => void data.pay(appointment.id)}
                  />
                ))}
              </ul>
            )}
            <p className="mt-4 flex items-start gap-2 text-xs leading-5 text-ink-muted">
              <ShieldCheck className="mt-0.5 h-4 w-4 flex-shrink-0 text-teal-600" aria-hidden />
              You pay on Stripe&apos;s page; Nora MedLink never sees your card details. An appointment shows as paid once Stripe
              confirms the payment.
            </p>
          </section>

          <section aria-labelledby="history-title" className="rounded-card border border-line bg-white p-5 shadow-card sm:p-6">
            <h2 id="history-title" className="text-base font-semibold text-ink">
              Payment history
            </h2>
            {data.payments.length === 0 ? (
              <EmptyState icon={Receipt} title="No payments yet" />
            ) : (
              <ul className="mt-4 divide-y divide-line">
                {data.payments.map((payment) => (
                  <HistoryItem key={payment.id} payment={payment} />
                ))}
              </ul>
            )}
          </section>
        </div>
      )}
    </PageContainer>
  );
}

function ToPayItem({
  appointment,
  highlighted,
  paying,
  disabled,
  error,
  onPay,
}: {
  appointment: Appointment;
  highlighted: boolean;
  paying: boolean;
  disabled: boolean;
  error: string;
  onPay: () => void;
}) {
  const fee = appointment.consultation_fee;
  return (
    <li className={cn("min-w-0 rounded-control border p-4", highlighted ? "border-brand-blue bg-blue-50/40" : "border-line")}>
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0">
          <p className="break-words text-sm font-semibold text-ink">{appointment.doctor_name}</p>
          <p className="text-xs text-ink-muted">{formatDateTime(appointment.date)}</p>
        </div>
        {fee ? (
          <Button variant={highlighted ? "primary" : "secondary"} size="sm" loading={paying} disabled={disabled} icon={<CreditCard className="h-4 w-4" />} onClick={onPay}>
            {paying ? "Opening..." : `Pay ${formatMoney(fee)}`}
          </Button>
        ) : (
          <p className="text-xs text-ink-muted">The doctor has not set a fee yet.</p>
        )}
      </div>
      {error ? (
        <Alert tone="error" className="mt-3 text-xs">
          {error}
        </Alert>
      ) : null}
    </li>
  );
}

function HistoryItem({ payment }: { payment: Payment }) {
  return (
    <li className="flex flex-wrap items-center justify-between gap-2 py-3 first:pt-0 last:pb-0">
      <div className="min-w-0">
        <p className="break-words text-sm font-medium text-ink">{payment.purpose}</p>
        <p className="text-xs text-ink-muted">
          {formatDateTime(payment.paid_at ?? payment.created_at)} · Ref {payment.reference}
        </p>
      </div>
      <div className="flex items-center gap-2">
        <span className="text-sm font-semibold text-ink">{formatMoney(payment.amount, payment.currency)}</span>
        {statusBadge(payment.status)}
      </div>
    </li>
  );
}

function SkeletonList() {
  return (
    <div role="status" aria-label="Loading payments" className="space-y-3 rounded-card border border-line bg-white p-5 shadow-card">
      <Skeleton className="h-5 w-1/3" />
      <Skeleton className="h-16 w-full" />
      <Skeleton className="h-16 w-full" />
    </div>
  );
}
