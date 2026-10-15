"use client";

import { useCallback, useState, type FormEvent } from "react";
import { Activity, Loader2, Plus } from "lucide-react";

import { api } from "@/lib/api";
import type { PatientVitals } from "@/lib/types";
import { useAsyncAction } from "@/hooks/use-async-action";
import type { Notify } from "@/hooks/use-toast";
import { formatDateTime } from "./helpers";
import { DashCard } from "./ui";

/** The simple BP + sugar log: an entry form and the latest readings. */
export function VitalsSection({
  history,
  notify,
  onSaved,
}: {
  history: PatientVitals[];
  notify: Notify;
  onSaved: () => Promise<void>;
}) {
  const [form, setForm] = useState({ bloodPressure: "", sugarLevel: "" });

  const save = useAsyncAction(
    useCallback(
      async (bloodPressure: string, sugarLevel: string) => {
        try {
          await api.addBasicVitals({ blood_pressure: bloodPressure, sugar_level: sugarLevel });
          notify("success", "Vitals saved.");
          setForm({ bloodPressure: "", sugarLevel: "" });
          await onSaved();
        } catch (err) {
          notify("error", err instanceof Error ? err.message : "Unable to save vitals.");
        }
      },
      [notify, onSaved],
    ),
  );

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const bloodPressure = form.bloodPressure.trim();
    const sugarLevel = form.sugarLevel.trim();
    if (!bloodPressure || !sugarLevel) {
      notify("error", "Enter both blood pressure and sugar level.");
      return;
    }
    void save.run(bloodPressure, sugarLevel);
  }

  return (
    <section id="vitals" className="grid gap-5 xl:grid-cols-[0.8fr_1.2fr]">
      <DashCard>
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-base font-semibold text-ink">Add Vitals</h2>
          <Activity className="h-5 w-5 text-blue-500" />
        </div>
        <form className="space-y-3" onSubmit={handleSubmit}>
          <div>
            <label htmlFor="vitals-bp" className="text-xs font-semibold text-slate-600">Blood pressure</label>
            <input
              id="vitals-bp"
              value={form.bloodPressure}
              onChange={(e) => setForm((c) => ({ ...c, bloodPressure: e.target.value }))}
              className="form-field mt-1"
              placeholder="120/80 mmHg"
            />
          </div>
          <div>
            <label htmlFor="vitals-sugar" className="text-xs font-semibold text-slate-600">Sugar level</label>
            <input
              id="vitals-sugar"
              value={form.sugarLevel}
              onChange={(e) => setForm((c) => ({ ...c, sugarLevel: e.target.value }))}
              className="form-field mt-1"
              placeholder="110 mg/dL"
            />
          </div>
          <button type="submit" className="primary-button w-full" disabled={save.pending}>
            {save.pending ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
            {save.pending ? "Saving..." : "Save Vitals"}
          </button>
        </form>
      </DashCard>
      <DashCard>
        <h2 className="text-base font-semibold text-ink">Vitals History</h2>
        <p className="text-[11px] text-slate-400 mt-0.5 mb-3">
          Your latest readings. Your doctor sees them during an unlocked consultation.
        </p>
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <thead>
              <tr className="border-b border-slate-100 text-[11px] font-semibold uppercase tracking-wider text-slate-400">
                <th className="py-2 pr-4">Date</th>
                <th className="py-2 pr-4">Blood pressure</th>
                <th className="py-2">Sugar level</th>
              </tr>
            </thead>
            <tbody>
              {history.length === 0 ? (
                <tr>
                  <td colSpan={3} className="py-3 text-sm text-slate-500">No vitals recorded yet.</td>
                </tr>
              ) : (
                history.map((v) => (
                  <tr key={v.id} className="border-b border-slate-50 last:border-0">
                    <td className="py-2 pr-4 text-slate-500">{formatDateTime(v.created_at)}</td>
                    <td className="py-2 pr-4 font-semibold text-ink">{v.blood_pressure}</td>
                    <td className="py-2 font-semibold text-ink">{v.sugar_level}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </DashCard>
    </section>
  );
}
