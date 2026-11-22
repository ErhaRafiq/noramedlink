"use client";

import { useState, type FormEvent } from "react";
import { Plus, Save } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { SelectField, TextField } from "@/components/ui/field";
import { localToday } from "@/lib/datetime";
import type { BodyMeasurement } from "@/lib/types";

export type BodyFormValues = { weight: number | null; unit: "kg" | "lb"; height: number | null; date: string };

/** Parses a typed number; null when empty, NaN when it is not a number. */
function parse(text: string): number | null {
  const trimmed = text.trim().replace(",", ".");
  return trimmed === "" ? null : Number(trimmed);
}

/**
 * Adds a weight and/or height reading, or corrects one (`editing`). Nothing is pre-filled except the date
 * (today): a weight is never guessed. The server checks the ranges and says what is wrong.
 */
export function BodyMeasurementForm({
  editing,
  busy,
  onSubmit,
  onCancel,
}: {
  editing?: BodyMeasurement;
  busy: boolean;
  /** Resolves to an error message, or null when saved. */
  onSubmit: (values: BodyFormValues) => Promise<string | null>;
  onCancel?: () => void;
}) {
  const [weight, setWeight] = useState(editing?.weight_kg != null ? String(editing.weight_kg) : "");
  const [unit, setUnit] = useState<"kg" | "lb">("kg");
  const [height, setHeight] = useState(editing?.height_cm != null ? String(editing.height_cm) : "");
  const [date, setDate] = useState(editing?.measured_on ?? localToday());
  const [errors, setErrors] = useState<{ weight?: string; height?: string; date?: string; form?: string }>({});

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (busy) return;
    const w = parse(weight);
    const h = parse(height);
    const next: typeof errors = {};
    if (w !== null && !(w > 0)) next.weight = "Enter a weight as a number, for example 72.5.";
    if (h !== null && !(h > 0)) next.height = "Enter a height in centimetres, for example 165.";
    if (!date || date > localToday()) next.date = "Enter a date that is not in the future.";
    if (w === null && h === null) next.form = "Enter a weight, a height, or both.";
    setErrors(next);
    if (Object.keys(next).length) return;
    const failure = await onSubmit({ weight: w, unit, height: h, date });
    if (failure) {
      setErrors({ form: failure });
      return;
    }
    if (!editing) {
      setWeight("");
      setHeight("");
      setDate(localToday());
    }
  }

  const label = editing ? "Correct this reading" : "Add a reading";
  return (
    <form onSubmit={submit} noValidate aria-label={label} className="space-y-4 rounded-control border border-line bg-surface-soft p-4">
      <p className="text-sm font-semibold text-ink">{label}</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <div className="grid grid-cols-[1fr_6rem] gap-3">
          <TextField label="Weight" inputMode="decimal" value={weight} error={errors.weight} onChange={(e) => setWeight(e.target.value)} placeholder="Not recorded" />
          <SelectField label="Unit" value={unit} onChange={(e) => setUnit(e.target.value as "kg" | "lb")}>
            <option value="kg">kg</option>
            <option value="lb">lb</option>
          </SelectField>
        </div>
        <TextField label="Height (cm)" inputMode="decimal" value={height} error={errors.height} onChange={(e) => setHeight(e.target.value)} placeholder="Not recorded" />
        <TextField label="Measured on" type="date" max={localToday()} value={date} error={errors.date} onChange={(e) => setDate(e.target.value)} />
      </div>
      <p className="text-xs text-ink-muted">Weight is saved in kg; pounds are converted. Leave a box empty if you do not know it.</p>
      {errors.form ? <Alert tone="error">{errors.form}</Alert> : null}
      <div className="flex flex-wrap gap-2">
        <Button type="submit" loading={busy} icon={editing ? <Save className="h-4 w-4" /> : <Plus className="h-4 w-4" />}>
          {busy ? "Saving..." : editing ? "Save correction" : "Save reading"}
        </Button>
        {onCancel ? (
          <Button type="button" variant="secondary" disabled={busy} onClick={onCancel}>
            Cancel
          </Button>
        ) : null}
      </div>
    </form>
  );
}
