"use client";

import { useState, type FormEvent } from "react";
import { Wallet } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { TextField } from "@/components/ui/field";
import { api } from "@/lib/api";
import { formatMoney } from "@/lib/money";

const MIN_FEE = 200;
const MAX_FEE = 100_000;

/** The doctor's consultation fee: what patients pay online with Stripe for one appointment. */
export function ConsultationFeeCard({ initialFee }: { initialFee: number | null }) {
  const [saved, setSaved] = useState<number | null>(initialFee);
  const [value, setValue] = useState(initialFee ? String(initialFee) : "");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<{ tone: "success" | "error"; text: string } | null>(null);

  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const fee = value.trim() ? Number(value) : null;
    if (fee !== null && (!Number.isInteger(fee) || fee < MIN_FEE || fee > MAX_FEE)) {
      setMessage({ tone: "error", text: `Enter a whole amount from ${formatMoney(MIN_FEE)} to ${formatMoney(MAX_FEE)}, or leave it empty.` });
      return;
    }
    setSaving(true);
    setMessage(null);
    try {
      const result = await api.setConsultationFee(fee);
      setSaved(result.consultation_fee);
      setMessage({ tone: "success", text: result.consultation_fee ? "Fee saved. New payments use it." : "Fee cleared: patients cannot pay online until you set one." });
    } catch (err) {
      setMessage({ tone: "error", text: err instanceof Error ? err.message : "The fee could not be saved." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <section id="fee" aria-labelledby="fee-title" className="min-w-0 scroll-mt-24 rounded-card border border-line bg-white p-5 shadow-card sm:p-6">
      <div className="flex items-center gap-3">
        <span className="grid h-9 w-9 place-items-center rounded-control bg-teal-50 text-teal-700">
          <Wallet className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0">
          <h2 id="fee-title" className="text-base font-semibold text-ink">
            Consultation fee
          </h2>
          <p className="text-xs text-ink-muted">{saved ? `Patients pay ${formatMoney(saved)} online, by card.` : "Not set: patients cannot pay you online yet."}</p>
        </div>
      </div>
      <form className="mt-4 flex flex-wrap items-end gap-3" onSubmit={save} noValidate>
        <div className="min-w-0 flex-1 basis-48">
          <TextField label="Fee (PKR)" type="number" inputMode="numeric" min={MIN_FEE} max={MAX_FEE} placeholder="1500" value={value} onChange={(e) => setValue(e.target.value)} />
        </div>
        <Button type="submit" variant="secondary" loading={saving}>
          {saving ? "Saving..." : "Save fee"}
        </Button>
      </form>
      {message ? (
        <Alert tone={message.tone} className="mt-3">
          {message.text}
        </Alert>
      ) : null}
    </section>
  );
}
