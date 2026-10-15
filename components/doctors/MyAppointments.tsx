"use client";

import Link from "next/link";
import { useState, type FormEvent } from "react";
import { CalendarClock, CreditCard, RefreshCw, XCircle } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime, toDateTimeInputValue } from "@/lib/datetime";
import { formatMoney } from "@/lib/money";
import type { Appointment } from "@/lib/types";
import type { useMyAppointments } from "@/hooks/doctors/use-my-appointments";

type Appointments = ReturnType<typeof useMyAppointments>;

function statusTone(status: string): BadgeTone {
  const value = status.toUpperCase();
  if (value === "BOOKED" || value === "CONFIRMED") return "success";
  if (value === "CANCELLED") return "danger";
  if (value === "COMPLETED") return "info";
  return "warning";
}

export function MyAppointments({ signedInAsPatient, list }: { signedInAsPatient: boolean; list: Appointments }) {
  return (
    <aside aria-labelledby="my-appointments-title" className="h-fit rounded-card border border-line bg-white p-5 shadow-card">
      <div className="flex items-center justify-between gap-3">
        <h2 id="my-appointments-title" className="text-base font-semibold text-ink">
          My appointments
        </h2>
        {signedInAsPatient ? (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => void list.reload()}
            disabled={list.status === "loading"}
            aria-label="Refresh appointments"
            icon={<RefreshCw className={list.status === "loading" ? "h-4 w-4 animate-spin" : "h-4 w-4"} />}
          />
        ) : null}
      </div>

      <div className="mt-4 space-y-3">
        {!signedInAsPatient ? (
          <EmptyState
            icon={CalendarClock}
            title="Sign in to book"
            description="Patients can book and manage appointments after signing in."
            action={
              <Link href="/login" className="secondary-button min-h-[36px] px-3 text-xs">
                Sign in
              </Link>
            }
          />
        ) : list.status === "loading" && list.appointments.length === 0 ? (
          Array.from({ length: 2 }, (_, i) => (
            <div key={i} className="space-y-2 rounded-control border border-line p-4">
              <Skeleton className="h-4 w-2/3" />
              <Skeleton className="h-3 w-1/2" />
            </div>
          ))
        ) : list.status === "error" ? (
          <Alert tone="error">{list.error}</Alert>
        ) : list.appointments.length === 0 ? (
          <EmptyState icon={CalendarClock} title="No appointments yet" description="Book a doctor from the list to see it here." />
        ) : (
          list.appointments.map((appointment) => (
            <AppointmentItem
              key={appointment.id}
              appointment={appointment}
              busy={list.busyId === appointment.id}
              disabled={list.busyId !== null}
              onCancel={list.cancel}
              onReschedule={list.reschedule}
            />
          ))
        )}
      </div>
    </aside>
  );
}

function AppointmentItem({
  appointment,
  busy,
  disabled,
  onCancel,
  onReschedule,
}: {
  appointment: Appointment;
  busy: boolean;
  disabled: boolean;
  onCancel: (id: number) => Promise<string | null>;
  onReschedule: (id: number, isoDate: string) => Promise<string | null>;
}) {
  const [newDate, setNewDate] = useState(() => toDateTimeInputValue(new Date(appointment.date)));
  const [action, setAction] = useState<"cancel" | "reschedule" | null>(null);
  const [error, setError] = useState("");
  const cancelled = appointment.status.toUpperCase() === "CANCELLED";

  async function run(kind: "cancel" | "reschedule", task: () => Promise<string | null>) {
    setAction(kind);
    setError((await task()) ?? "");
    setAction(null);
  }

  function handleReschedule(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const date = new Date(newDate);
    if (Number.isNaN(date.getTime())) {
      setError("Choose a valid date and time.");
      return;
    }
    void run("reschedule", () => onReschedule(appointment.id, date.toISOString()));
  }

  return (
    <article className="rounded-control border border-line p-4">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-sm font-semibold text-ink">{appointment.doctor_name}</h3>
          <p className="mt-0.5 text-xs text-ink-muted">{formatDateTime(appointment.date)}</p>
        </div>
        <Badge tone={statusTone(appointment.status)}>{appointment.status.replaceAll("_", " ").toLowerCase()}</Badge>
      </div>
      {appointment.notes ? <p className="mt-3 rounded-control bg-surface-soft px-3 py-2 text-xs leading-5 text-slate-600">{appointment.notes}</p> : null}
      <PaymentLine appointment={appointment} cancelled={cancelled} />

      {!cancelled ? (
        <form className="mt-3 space-y-2" onSubmit={handleReschedule}>
          <label className="block">
            <span className="sr-only">New date and time</span>
            <input
              type="datetime-local"
              min={toDateTimeInputValue(new Date())}
              value={newDate}
              onChange={(event) => setNewDate(event.target.value)}
              className="form-field py-2 text-xs"
            />
          </label>
          <div className="grid grid-cols-2 gap-2">
            <Button type="submit" variant="secondary" size="sm" loading={busy && action === "reschedule"} disabled={disabled}>
              Reschedule
            </Button>
            <Button
              variant="danger"
              size="sm"
              loading={busy && action === "cancel"}
              disabled={disabled}
              icon={<XCircle className="h-3.5 w-3.5" />}
              onClick={() => void run("cancel", () => onCancel(appointment.id))}
            >
              Cancel
            </Button>
          </div>
        </form>
      ) : null}
      {error ? <Alert tone="error" className="mt-3 text-xs">{error}</Alert> : null}
    </article>
  );
}

function PaymentLine({ appointment, cancelled }: { appointment: Appointment; cancelled: boolean }) {
  if (appointment.payment_status.toUpperCase() === "PAID") {
    return (
      <p className="mt-2 text-xs font-medium text-emerald-700">
        Paid{appointment.consultation_fee ? ` · ${formatMoney(appointment.consultation_fee)}` : ""}
      </p>
    );
  }
  if (cancelled) return null;
  if (!appointment.consultation_fee) return <p className="mt-2 text-xs text-ink-muted">Payment: the doctor has not set a fee yet.</p>;
  return (
    <Link
      href={`/payments?appointmentId=${appointment.id}`}
      className="mt-2 inline-flex items-center gap-1.5 text-xs font-semibold text-brand-blue hover:underline"
    >
      <CreditCard className="h-3.5 w-3.5" aria-hidden />
      Pay {formatMoney(appointment.consultation_fee)}
    </Link>
  );
}
