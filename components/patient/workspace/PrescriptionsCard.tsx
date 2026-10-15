"use client";

import { Pill } from "lucide-react";

import type { PatientPrescription } from "@/lib/types";
import { formatDate } from "./helpers";
import { DashCard } from "./ui";

/** Prescriptions doctors confirmed for this patient: read-only, in everyday words. */
export function PrescriptionsCard({ prescriptions, onRetry }: { prescriptions: PatientPrescription[] | null; onRetry: () => void }) {
  return (
    <DashCard id="prescriptions">
      <div className="mb-4 flex items-center gap-3">
        <span className="grid h-9 w-9 place-items-center rounded-control bg-teal-50 text-teal-700">
          <Pill className="h-4 w-4" aria-hidden />
        </span>
        <h2 className="text-base font-semibold text-ink">Prescriptions from your doctors</h2>
      </div>
      {prescriptions === null ? (
        <p role="status" className="rounded-control border border-line bg-surface-soft p-3 text-sm text-ink-muted">
          Prescriptions could not be loaded.{" "}
          <button type="button" onClick={onRetry} className="font-semibold text-brand-blue hover:underline">
            Try again
          </button>
        </p>
      ) : prescriptions.length === 0 ? (
        <p className="rounded-control border border-line bg-surface-soft p-3 text-sm text-ink-muted">No prescriptions from a doctor in the app yet.</p>
      ) : (
        <ul className="space-y-3">
          {prescriptions.map((p) => (
            <li key={p.id} className="min-w-0 rounded-control border border-line p-3.5">
              <p className="text-xs text-ink-muted">
                {formatDate(p.created_at)} · {p.doctor_name}
                {p.status === "cancelled" ? <span className="ml-2 font-semibold text-rose-700">Cancelled by the doctor</span> : null}
              </p>
              <ul className="mt-1.5 space-y-1 text-sm">
                {p.items.map((item, index) => (
                  <li key={index} className={p.status === "cancelled" ? "break-words text-ink-muted line-through" : "break-words text-ink"}>
                    <span className="font-semibold">{item.medicine}</span>: {item.how_to_take}
                    {item.duration ? `, for ${item.duration}` : ""}
                    {item.instructions ? <span className="block text-xs text-ink-muted">{item.instructions}</span> : null}
                  </li>
                ))}
              </ul>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-4 text-xs leading-5 text-ink-muted">Take medicines only as your doctor told you. Ask your doctor or pharmacist if anything is unclear.</p>
    </DashCard>
  );
}
