"use client";

import { useState } from "react";
import { Trash2 } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { SelectField, TextAreaField, TextField } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime } from "@/lib/datetime";
import { usePrescribing } from "@/hooks/doctor/use-prescribing";
import { CheckPanel, ContextSummary } from "./CheckPanel";
import { MedicineSearch } from "./MedicineSearch";

const FREQUENCIES = [
  ["OD", "Once a day (OD)"],
  ["BD", "Twice a day (BD)"],
  ["TDS", "Three times a day (TDS)"],
  ["QID", "Four times a day (QID)"],
  ["HS", "At bedtime (HS)"],
  ["PRN", "When needed (PRN)"],
] as const;
const MIN_JUSTIFICATION = 20;

/** Write a prescription for the selected patient (active grant): every medicine is checked live
 * against the patient's record; high-risk alerts need a written reason to confirm. Decision
 * support only: the doctor chooses. */
export function PrescribeCard({
  token,
  patientId,
  patientName,
  doctorId,
  doctorName,
}: {
  token: string;
  patientId: number;
  patientName: string;
  doctorId: number;
  doctorName: string;
}) {
  const rx = usePrescribing(token, patientId);
  const [dialogOpen, setDialogOpen] = useState(false);
  const [justifications, setJustifications] = useState<Record<string, string>>({});
  const [notes, setNotes] = useState("");
  const [saved, setSaved] = useState(false);
  const needs = rx.check?.requires_justification ?? [];
  const complete = needs.every((alert) => (justifications[alert.id] ?? "").trim().length >= MIN_JUSTIFICATION);

  async function confirm() {
    const ok = await rx.confirm(justifications, notes);
    if (ok) {
      setDialogOpen(false);
      setJustifications({});
      setNotes("");
      setSaved(true);
    }
  }

  return (
    <section id="prescribe" className="min-w-0 scroll-mt-24 rounded-card border border-line bg-white p-5 shadow-card sm:p-6">
      <div className="mb-5">
        <p className="section-eyebrow">Medication safety</p>
        <h2 className="mt-1.5 break-words text-lg font-semibold text-ink">Prescribe for {patientName}</h2>
        <p className="mt-1 text-xs text-ink-muted">Each medicine is checked against this patient&apos;s record as you add it. Advisory: you decide.</p>
      </div>

      {saved && !rx.items.length ? (
        <Alert tone="success" className="mb-4">
          Prescription saved. It appears below and on the patient&apos;s dashboard.
        </Alert>
      ) : null}

      <MedicineSearch
        token={token}
        onPick={(option) => {
          setSaved(false);
          rx.add(option);
        }}
      />

      {rx.items.length ? (
        <ul className="mt-4 space-y-3">
          {rx.items.map((item) => (
            <li key={item.key} className="grid min-w-0 gap-3 rounded-control border border-line p-3 sm:grid-cols-[1.4fr_1fr_1.2fr_1fr_auto] sm:items-end">
              <TextField label="Medicine" value={item.medicine} onChange={(e) => rx.update(item.key, { medicine: e.target.value })} />
              <TextField label="Dose" placeholder="500 mg" value={item.dose ?? ""} onChange={(e) => rx.update(item.key, { dose: e.target.value })} />
              <SelectField label="How often" value={item.frequency ?? "OD"} onChange={(e) => rx.update(item.key, { frequency: e.target.value })}>
                {FREQUENCIES.map(([value, label]) => (
                  <option key={value} value={value}>
                    {label}
                  </option>
                ))}
              </SelectField>
              <TextField label="For how long" placeholder="7 days" value={item.duration ?? ""} onChange={(e) => rx.update(item.key, { duration: e.target.value })} />
              <Button variant="ghost" size="sm" icon={<Trash2 className="h-4 w-4" aria-hidden />} onClick={() => rx.remove(item.key)} aria-label={`Remove ${item.medicine}`}>
                Remove
              </Button>
              {item.replaced_medicine ? <p className="text-xs text-teal-800 sm:col-span-5">Chosen instead of {item.replaced_medicine}.</p> : null}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-4 rounded-control border border-dashed border-line p-4 text-sm text-ink-muted">No medicines added yet.</p>
      )}

      {rx.items.length ? (
        <div className="mt-5 space-y-4">
          {rx.checking ? (
            <div role="status" aria-label="Checking the prescription" className="space-y-2">
              <Skeleton className="h-16 w-full" />
              <Skeleton className="h-16 w-full" />
            </div>
          ) : null}
          {rx.checkError ? <Alert tone="error">{rx.checkError}</Alert> : null}
          {rx.check ? (
            <>
              <ContextSummary context={rx.check.context} />
              <CheckPanel token={token} check={rx.check} onUseAlternative={rx.replace} />
              <p className="text-xs leading-5 text-ink-muted">{rx.check.note}</p>
            </>
          ) : null}
          <div className="flex flex-wrap items-center justify-end gap-3 border-t border-line pt-4">
            {needs.length ? <p className="text-xs text-rose-800">{needs.length} high-risk alert(s) need your written reason to confirm.</p> : null}
            <Button variant="primary" disabled={!rx.check || rx.checking} onClick={() => (needs.length ? setDialogOpen(true) : void confirm())} loading={rx.confirming && !dialogOpen}>
              {rx.confirming && !dialogOpen ? "Saving..." : "Confirm prescription"}
            </Button>
          </div>
          {rx.confirmError && !dialogOpen ? <Alert tone="error">{rx.confirmError}</Alert> : null}
        </div>
      ) : null}

      <ConfirmDialog
        open={dialogOpen}
        tone="primary"
        title="Prescribe despite high-risk alerts?"
        confirmLabel="Confirm with these reasons"
        pendingLabel="Saving..."
        pending={rx.confirming}
        confirmDisabled={!complete}
        onCancel={() => setDialogOpen(false)}
        onConfirm={() => void confirm()}
        description={
          <div className="space-y-3">
            <p>Your reasons are saved with the prescription, as {doctorName}.</p>
            {needs.map((alert) => (
              <TextAreaField
                key={alert.id}
                label={alert.title}
                hint={`${(justifications[alert.id] ?? "").trim().length}/${MIN_JUSTIFICATION} characters at least`}
                rows={2}
                value={justifications[alert.id] ?? ""}
                onChange={(e) => setJustifications((current) => ({ ...current, [alert.id]: e.target.value }))}
              />
            ))}
            <TextAreaField label="Notes (optional)" rows={2} value={notes} onChange={(e) => setNotes(e.target.value)} />
            {rx.confirmError ? <p className="text-sm text-rose-700">{rx.confirmError}</p> : null}
          </div>
        }
      />

      <div className="mt-6 border-t border-line pt-4">
        <h3 className="mb-2 text-sm font-semibold text-ink">Prescriptions for this patient</h3>
        {!rx.history.loaded ? (
          <Skeleton className="h-12 w-full" />
        ) : rx.history.error ? (
          <Alert tone="error">{rx.history.error}</Alert>
        ) : rx.history.items.length === 0 ? (
          <p className="text-sm text-ink-muted">None yet.</p>
        ) : (
          <ul className="space-y-2">
            {rx.history.items.map((p) => (
              <li key={p.id} className="min-w-0 rounded-control border border-line p-3 text-sm">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <p className="font-medium text-ink">
                    {formatDateTime(p.created_at)} · {p.doctor_name}
                  </p>
                  <div className="flex items-center gap-2">
                    <Badge tone={p.status === "confirmed" ? "success" : "neutral"}>{p.status}</Badge>
                    {p.status === "confirmed" && p.doctor_id === doctorId ? (
                      <Button variant="ghost" size="sm" loading={rx.cancellingId === p.id} onClick={() => void rx.cancel(p.id)}>
                        {rx.cancellingId === p.id ? "Cancelling..." : "Cancel"}
                      </Button>
                    ) : null}
                  </div>
                </div>
                <p className="mt-1 break-words text-ink-muted">
                  {p.items.map((i) => [i.medicine, i.dose, i.frequency, i.duration].filter(Boolean).join(" ")).join("; ")}
                </p>
                {p.overrides.length ? (
                  <p className="mt-1 break-words text-xs text-rose-800">
                    {p.overrides.length} alert(s) overridden: {p.overrides.map((o) => `${o.title} ("${o.justification}")`).join("; ")}
                  </p>
                ) : null}
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  );
}
