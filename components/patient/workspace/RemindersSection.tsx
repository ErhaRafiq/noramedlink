"use client";

import { useCallback, useState, type FormEvent } from "react";
import { Bell, Loader2, Plus } from "lucide-react";

import { api } from "@/lib/api";
import type { MedicationSchedule } from "@/lib/types";
import { useAsyncAction } from "@/hooks/use-async-action";
import type { Notify } from "@/hooks/use-toast";
import { DashCard } from "./ui";

const EMPTY_REMINDER = { medicationId: "", reminderTime: "", frequency: "Once daily" };
const EMPTY_MEDICATION = { medicineName: "", dosage: "", instructions: "", startDate: "", endDate: "" };

/** Create a reminder for one of the patient's medications, and add medications. */
export function RemindersSection({
  medications,
  notify,
  onSaved,
  beforeCreateReminder,
}: {
  medications: MedicationSchedule[];
  notify: Notify;
  onSaved: () => Promise<void>;
  /** Runs before a reminder is created; used to ask for browser pop-up permission. */
  beforeCreateReminder: () => Promise<void>;
}) {
  const [reminderForm, setReminderForm] = useState(EMPTY_REMINDER);
  const [medicationForm, setMedicationForm] = useState(EMPTY_MEDICATION);

  const createReminder = useAsyncAction(
    useCallback(
      async (medicationId: number, values: typeof EMPTY_REMINDER) => {
        try {
          await beforeCreateReminder();
          await api.createReminder({ medicationId, reminderTime: values.reminderTime, frequency: values.frequency });
          notify("success", "Reminder created.");
          setReminderForm(EMPTY_REMINDER);
          await onSaved();
        } catch (err) {
          notify("error", err instanceof Error ? err.message : "Unable to create reminder.");
        }
      },
      [beforeCreateReminder, notify, onSaved],
    ),
  );

  const saveMedication = useAsyncAction(
    useCallback(
      async (values: typeof EMPTY_MEDICATION) => {
        try {
          await api.createMedicineSchedule({
            medicineName: values.medicineName,
            dosage: values.dosage,
            instructions: values.instructions || null,
            startDate: values.startDate,
            endDate: values.endDate || null,
          });
          notify("success", "Medication saved.");
          setMedicationForm(EMPTY_MEDICATION);
          await onSaved();
        } catch (err) {
          notify("error", err instanceof Error ? err.message : "Unable to save medication.");
        }
      },
      [notify, onSaved],
    ),
  );

  function handleReminderSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const medicationId = Number(reminderForm.medicationId);
    if (!Number.isInteger(medicationId) || medicationId <= 0 || !reminderForm.reminderTime) {
      notify("error", "Select a medication and reminder time.");
      return;
    }
    void createReminder.run(medicationId, reminderForm);
  }

  function handleMedicationSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!medicationForm.medicineName || !medicationForm.dosage || !medicationForm.startDate) {
      notify("error", "Medicine name, dosage, and start date are required.");
      return;
    }
    void saveMedication.run(medicationForm);
  }

  return (
    <section id="reminders">
      <DashCard>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-ink">Create Reminder</h2>
          <Bell className="h-5 w-5 text-rose-500" />
        </div>
        <form className="space-y-3" onSubmit={handleReminderSubmit}>
          <select
            value={reminderForm.medicationId}
            aria-label="Medication"
            onChange={(e) => setReminderForm((c) => ({ ...c, medicationId: e.target.value }))}
            className="form-field"
          >
            <option value="">Select medication</option>
            {medications.map((m) => (
              <option key={m.id} value={m.id}>
                {m.medicine_name}
              </option>
            ))}
          </select>
          <div className="grid gap-3 sm:grid-cols-2">
            <input
              type="datetime-local"
              aria-label="Reminder time"
              value={reminderForm.reminderTime}
              onChange={(e) => setReminderForm((c) => ({ ...c, reminderTime: e.target.value }))}
              className="form-field"
            />
            <input
              value={reminderForm.frequency}
              aria-label="Frequency"
              onChange={(e) => setReminderForm((c) => ({ ...c, frequency: e.target.value }))}
              className="form-field"
              placeholder="Frequency"
            />
          </div>
          <button type="submit" className="primary-button w-full" disabled={createReminder.pending}>
            {createReminder.pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bell className="h-4 w-4" />}
            {createReminder.pending ? "Saving..." : "Create Reminder"}
          </button>
        </form>

        <div className="mt-5 pt-5 border-t border-slate-100">
          <h3 className="text-sm font-semibold text-ink mb-3">Add Medication</h3>
          <form className="space-y-3" onSubmit={handleMedicationSubmit}>
            <div className="grid gap-3 sm:grid-cols-2">
              <input
                value={medicationForm.medicineName}
                aria-label="Medicine name"
                onChange={(e) => setMedicationForm((c) => ({ ...c, medicineName: e.target.value }))}
                className="form-field"
                placeholder="Medicine name"
              />
              <input
                value={medicationForm.dosage}
                aria-label="Dosage"
                onChange={(e) => setMedicationForm((c) => ({ ...c, dosage: e.target.value }))}
                className="form-field"
                placeholder="Dosage"
              />
            </div>
            <input
              value={medicationForm.instructions}
              aria-label="Instructions"
              onChange={(e) => setMedicationForm((c) => ({ ...c, instructions: e.target.value }))}
              className="form-field"
              placeholder="Instructions (optional)"
            />
            <div className="grid gap-3 sm:grid-cols-2">
              <input
                type="date"
                aria-label="Start date"
                value={medicationForm.startDate}
                onChange={(e) => setMedicationForm((c) => ({ ...c, startDate: e.target.value }))}
                className="form-field"
              />
              <input
                type="date"
                aria-label="End date"
                value={medicationForm.endDate}
                onChange={(e) => setMedicationForm((c) => ({ ...c, endDate: e.target.value }))}
                className="form-field"
              />
            </div>
            <button type="submit" className="primary-button w-full" disabled={saveMedication.pending}>
              {saveMedication.pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
              {saveMedication.pending ? "Saving..." : "Save Medication"}
            </button>
          </form>
        </div>
      </DashCard>
    </section>
  );
}
