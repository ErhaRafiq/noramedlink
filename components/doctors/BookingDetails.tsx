import { TextAreaField, TextField } from "@/components/ui/field";
import { toDateTimeInputValue } from "@/lib/datetime";

export type BookingDetailsValue = { date: string; notes: string; accessCode: string };

/** Time, notes and an optional access code, used for whichever doctor the patient books. */
export function BookingDetails({ value, onChange }: { value: BookingDetailsValue; onChange: (next: BookingDetailsValue) => void }) {
  return (
    <section aria-labelledby="booking-details-title" className="rounded-card border border-line bg-white p-5 shadow-card">
      <h2 id="booking-details-title" className="text-base font-semibold text-ink">
        Booking details
      </h2>
      <p className="mt-1 text-sm text-ink-muted">Used for the doctor you book below.</p>
      <div className="mt-4 grid gap-4 sm:grid-cols-2">
        <TextField
          label="Date and time"
          type="datetime-local"
          min={toDateTimeInputValue(new Date())}
          value={value.date}
          onChange={(event) => onChange({ ...value, date: event.target.value })}
        />
        <TextField
          label="Share my file (optional)"
          hint="Paste a one-time code from your dashboard to give this doctor access for the visit."
          inputMode="numeric"
          autoComplete="off"
          value={value.accessCode}
          onChange={(event) => onChange({ ...value, accessCode: event.target.value })}
        />
        <TextAreaField
          label="Notes for the doctor (optional)"
          wrapperClassName="sm:col-span-2"
          rows={3}
          placeholder="Symptoms, how long you have had them, or anything the doctor should know"
          value={value.notes}
          onChange={(event) => onChange({ ...value, notes: event.target.value })}
        />
      </div>
    </section>
  );
}
