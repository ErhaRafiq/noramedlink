"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { useState, type FormEvent } from "react";
import { Banknote, CheckCircle2, Smartphone, Wallet } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { TextField } from "@/components/ui/field";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import { useStoredSession } from "@/hooks/use-stored-session";

type Method = "EASYPAISA" | "JAZZCASH" | "NAYAPAY" | "CASH";

const METHODS: Array<{ value: Method; title: string; description: string; icon: typeof Wallet }> = [
  { value: "EASYPAISA", title: "Easypaisa", description: "Mobile wallet", icon: Smartphone },
  { value: "JAZZCASH", title: "JazzCash", description: "Mobile wallet", icon: Smartphone },
  { value: "NAYAPAY", title: "NayaPay", description: "Digital wallet", icon: Wallet },
  { value: "CASH", title: "Cash on visit", description: "Pay at the clinic", icon: Banknote },
];

type Recorded = { reference: string; status: string; method: string };

export function PaymentsView() {
  const searchParams = useSearchParams();
  const appointmentId = searchParams.get("appointmentId");
  const { ready, session } = useStoredSession();

  const [amount, setAmount] = useState("");
  const [method, setMethod] = useState<Method>("EASYPAISA");
  const [phone, setPhone] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [recorded, setRecorded] = useState<Recorded | null>(null);
  const isCash = method === "CASH";

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (submitting || !session) return;
    setError("");
    const value = Number(amount);
    if (!Number.isFinite(value) || value <= 0) {
      setError("Enter the amount in PKR.");
      return;
    }
    if (!isCash && !phone.trim()) {
      setError("Enter the wallet phone number.");
      return;
    }
    setSubmitting(true);
    try {
      const payment = await api.createPayment(session.token, {
        amount: value,
        method,
        phone: isCash ? undefined : phone.trim(),
        purpose: appointmentId ? `Appointment payment #${appointmentId}` : "Doctor consultation",
        appointment_id: appointmentId ? Number(appointmentId) : undefined,
      });
      setRecorded({ reference: payment.reference, status: payment.status, method: METHODS.find((m) => m.value === method)?.title ?? method });
    } catch (err) {
      setError(err instanceof Error ? err.message : "The payment could not be recorded. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <PageContainer narrow>
      <PageHeader
        eyebrow="Payments"
        title="Record a consultation payment"
        description={appointmentId ? `For appointment #${appointmentId}.` : "For a doctor consultation or home visit."}
      />

      <Alert tone="info" className="mb-6" title="No money is transferred here">
        This prototype has no payment gateway. It records your payment so the clinic can confirm it: wallet payments stay
        pending until an administrator confirms them, and cash is collected at the visit.
      </Alert>

      <section className="rounded-card border border-line bg-white p-5 shadow-card sm:p-6">
        {!ready ? null : !session ? (
          <EmptyState
            icon={Wallet}
            title="Sign in to record a payment"
            action={
              <Link href="/login" className="secondary-button min-h-[36px] px-3 text-xs">
                Sign in
              </Link>
            }
          />
        ) : recorded ? (
          <div className="text-center">
            <CheckCircle2 className="mx-auto h-10 w-10 text-emerald-600" aria-hidden />
            <h2 className="mt-3 text-lg font-semibold text-ink">Payment recorded</h2>
            <p className="mt-2 text-sm text-ink-muted">
              {recorded.status === "PAY_ON_VISIT"
                ? "Pay in cash at your visit."
                : `${recorded.method} payment is pending until the clinic confirms it.`}
            </p>
            <p className="mt-3 inline-block rounded-control bg-surface-soft px-3 py-1.5 font-mono text-sm text-ink">Reference {recorded.reference}</p>
            <div className="mt-6">
              <Button variant="secondary" onClick={() => setRecorded(null)}>
                Record another payment
              </Button>
            </div>
          </div>
        ) : (
          <form className="space-y-6" onSubmit={handleSubmit} noValidate>
            <fieldset>
              <legend className="text-sm font-medium text-slate-700">Payment method</legend>
              <div className="mt-2 grid gap-3 sm:grid-cols-2">
                {METHODS.map(({ value, title, description, icon: Icon }) => {
                  const selected = method === value;
                  return (
                    <label
                      key={value}
                      className={cn(
                        "flex cursor-pointer items-center gap-3 rounded-control border p-3.5 transition-colors has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-brand-blue",
                        selected ? "border-brand-blue bg-blue-50/60" : "border-line bg-white hover:border-line-strong",
                      )}
                    >
                      <input type="radio" name="method" value={value} checked={selected} onChange={() => setMethod(value)} className="sr-only" />
                      <span className={cn("grid h-9 w-9 place-items-center rounded-control", selected ? "bg-brand-blue text-white" : "bg-surface-soft text-ink-muted")}>
                        <Icon className="h-4 w-4" aria-hidden />
                      </span>
                      <span>
                        <span className="block text-sm font-semibold text-ink">{title}</span>
                        <span className="block text-xs text-ink-muted">{description}</span>
                      </span>
                    </label>
                  );
                })}
              </div>
            </fieldset>

            <div className="grid gap-4 sm:grid-cols-2">
              <TextField label="Amount (PKR)" type="number" min={1} inputMode="numeric" value={amount} onChange={(e) => setAmount(e.target.value)} />
              <TextField
                label={isCash ? "Phone number (optional)" : "Wallet phone number"}
                type="tel"
                autoComplete="tel"
                placeholder="03XX XXXXXXX"
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
              />
            </div>

            {error ? <Alert tone="error">{error}</Alert> : null}
            <Button type="submit" size="lg" loading={submitting} className="w-full">
              {submitting ? "Recording..." : "Record payment"}
            </Button>
          </form>
        )}
      </section>
    </PageContainer>
  );
}
