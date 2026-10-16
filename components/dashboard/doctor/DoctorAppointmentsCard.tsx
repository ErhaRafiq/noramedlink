"use client";

import { useState } from "react";

import { MODE_LABEL } from "@/components/doctors/BookingDialog";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { clinicDateTime } from "@/lib/datetime";
import type { DoctorOverview } from "@/lib/types";

type Appointment = DoctorOverview["appointments"][number];
type Change = "COMPLETED" | "NO_SHOW" | "CANCELLED";

const LABEL: Record<string, string> = { BOOKED: "Booked", COMPLETED: "Completed", NO_SHOW: "Missed", CANCELLED: "Cancelled" };
const TONE: Record<string, BadgeTone> = { BOOKED: "success", COMPLETED: "info", NO_SHOW: "danger", CANCELLED: "danger" };

/**
 * The doctor's appointments, upcoming first. A visit that has started can be completed or marked as missed;
 * a booked visit can be cancelled (the patient is told and the time opens up again).
 */
export function DoctorAppointmentsCard({
  appointments,
  selectedPatientId,
  onSelect,
  changingId,
  onChange,
}: {
  appointments: Appointment[];
  selectedPatientId: number | null;
  onSelect: (patientId: number) => void;
  changingId: number | null;
  onChange: (id: number, status: Change) => void;
}) {
  const [now] = useState(() => Date.now()); // when the dashboard was opened
  const [cancelling, setCancelling] = useState<Appointment | null>(null);
  const live = appointments.filter((a) => a.status === "BOOKED").sort((a, b) => +new Date(a.date) - +new Date(b.date));
  const past = appointments.filter((a) => a.status !== "BOOKED");
  const ordered = [...live, ...past];

  return (
    <Card id="appointments">
      <p className="section-eyebrow">Schedule</p>
      <h2 className="mb-4 mt-1.5 text-lg font-semibold text-ink">Appointments</h2>
      {ordered.length === 0 ? (
        <EmptyState title="No appointments yet" description="Appointments that patients book with you will appear here. Publish your weekly hours on your profile so they can." />
      ) : (
        <ul className="space-y-3">
          {ordered.map((a) => {
            const started = new Date(a.date).getTime() <= now;
            const busy = changingId === a.id;
            return (
              <li key={a.id} className={`rounded-control border p-4 ${a.userId === selectedPatientId ? "border-brand-blue bg-blue-50/40" : "border-line"}`}>
                <button type="button" onClick={() => onSelect(a.userId)} className="block w-full text-left">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <p className="break-words text-sm font-semibold text-ink">{a.patientName}</p>
                    <Badge tone={TONE[a.status] ?? "neutral"}>{LABEL[a.status] ?? a.status.toLowerCase()}</Badge>
                  </div>
                  <p className="mt-1 text-sm font-semibold text-slate-600">{clinicDateTime(a.date)} PKT</p>
                  <p className="text-xs text-ink-muted">
                    {a.durationMinutes} min · {MODE_LABEL[a.mode] ?? a.mode} · {a.paymentStatus === "PAID" ? "Paid" : "Not paid"}
                    {a.hasDashboardAccess ? " · File shared" : ""}
                  </p>
                </button>
                {a.status === "BOOKED" ? (
                  <div className="mt-3 flex flex-wrap gap-2">
                    {started ? (
                      <>
                        <Button size="sm" loading={busy} disabled={changingId !== null} onClick={() => onChange(a.id, "COMPLETED")}>
                          Mark completed
                        </Button>
                        <Button variant="secondary" size="sm" disabled={changingId !== null} onClick={() => onChange(a.id, "NO_SHOW")}>
                          Patient did not come
                        </Button>
                      </>
                    ) : null}
                    <Button variant="danger" size="sm" disabled={changingId !== null} onClick={() => setCancelling(a)}>
                      Cancel
                    </Button>
                  </div>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}
      <ConfirmDialog
        open={cancelling !== null}
        title="Cancel this appointment?"
        description={cancelling ? `${cancelling.patientName}, ${clinicDateTime(cancelling.date)} PKT. They will be told, and the time opens up again.` : null}
        confirmLabel="Cancel appointment"
        pendingLabel="Cancelling..."
        pending={cancelling !== null && changingId === cancelling.id}
        onCancel={() => setCancelling(null)}
        onConfirm={() => {
          if (cancelling) onChange(cancelling.id, "CANCELLED");
          setCancelling(null);
        }}
      />
    </Card>
  );
}
