"use client";

import { useCallback, useState, type FormEvent } from "react";
import { CalendarCheck2, CalendarDays, Loader2 } from "lucide-react";

import { api } from "@/lib/api";
import type { Appointment, DoctorOption } from "@/lib/types";
import { useAsyncAction } from "@/hooks/use-async-action";
import type { Notify } from "@/hooks/use-toast";
import { formatDateTime } from "./helpers";
import { DashCard } from "./ui";

const EMPTY_FORM = { doctorId: "", specialty: "", date: "", time: "", reason: "" };
const APPOINTMENTS_PREVIEW = 4;

export function AppointmentsSection({
  token,
  doctors,
  appointments,
  notify,
  onSaved,
}: {
  token: string;
  doctors: DoctorOption[];
  appointments: Appointment[];
  notify: Notify;
  onSaved: () => Promise<void>;
}) {
  const [form, setForm] = useState(EMPTY_FORM);

  const book = useAsyncAction(
    useCallback(
      async (doctor: DoctorOption, values: typeof EMPTY_FORM) => {
        try {
          await api.bookAppointment(token, {
            doctorId: doctor.id,
            doctorName: doctor.name,
            specialty: values.specialty || doctor.specialty,
            date: values.date,
            time: values.time,
            reason: values.reason,
          });
          notify("success", "Appointment booked successfully.");
          setForm(EMPTY_FORM);
          await onSaved();
        } catch (err) {
          notify("error", err instanceof Error ? err.message : "Appointment booking failed.");
        }
      },
      [notify, onSaved, token],
    ),
  );

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const doctor = doctors.find((d) => String(d.id) === form.doctorId);
    if (!doctor || !form.date || !form.time || !form.reason) {
      notify("error", "Doctor, date, time, and reason are required.");
      return;
    }
    void book.run(doctor, form);
  }

  return (
    <section id="appointments">
      <DashCard>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-ink">Book an Appointment</h2>
          <CalendarDays className="h-5 w-5 text-violet-500" />
        </div>
        <form className="space-y-3" onSubmit={handleSubmit}>
          <select
            value={form.doctorId}
            aria-label="Doctor"
            onChange={(e) => {
              const selected = doctors.find((d) => String(d.id) === e.target.value);
              setForm((c) => ({ ...c, doctorId: e.target.value, specialty: selected?.specialty ?? c.specialty }));
            }}
            className="form-field"
          >
            <option value="">Select doctor</option>
            {doctors.map((d) => (
              <option key={d.id} value={d.id}>
                {d.name} · {d.specialty}
              </option>
            ))}
          </select>
          <input
            value={form.specialty}
            aria-label="Department or specialty"
            onChange={(e) => setForm((c) => ({ ...c, specialty: e.target.value }))}
            className="form-field"
            placeholder="Department / specialty"
          />
          <div className="grid gap-3 sm:grid-cols-2">
            <input type="date" aria-label="Date" value={form.date} onChange={(e) => setForm((c) => ({ ...c, date: e.target.value }))} className="form-field" />
            <input type="time" aria-label="Time" value={form.time} onChange={(e) => setForm((c) => ({ ...c, time: e.target.value }))} className="form-field" />
          </div>
          <textarea
            value={form.reason}
            aria-label="Reason for visit"
            onChange={(e) => setForm((c) => ({ ...c, reason: e.target.value }))}
            className="form-field min-h-20"
            placeholder="Reason for visit"
          />
          <button type="submit" className="primary-button w-full" disabled={book.pending}>
            {book.pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarCheck2 className="h-4 w-4" />}
            {book.pending ? "Booking..." : "Book Appointment"}
          </button>
        </form>
        {appointments.length > 0 && (
          <div className="mt-4 space-y-2.5">
            {appointments.slice(0, APPOINTMENTS_PREVIEW).map((a) => (
              <div key={a.id} className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                <p className="text-sm font-semibold text-ink">{a.doctor_name}</p>
                <p className="text-xs text-slate-500 mt-0.5">{formatDateTime(a.date)}</p>
                <span className="text-[11px] font-semibold text-slate-400 uppercase tracking-wider">{a.status}</span>
              </div>
            ))}
          </div>
        )}
      </DashCard>
    </section>
  );
}
