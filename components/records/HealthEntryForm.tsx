"use client";

import { useId, useState, type FormEvent } from "react";
import { Plus } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { SelectField, TextAreaField, TextField } from "@/components/ui/field";
import type { HealthEntryInput, HealthKind, HealthOptions } from "@/lib/types";

export const KIND_LABEL: Record<HealthKind, string> = {
  allergy: "Allergy",
  diagnosis: "Diagnosis",
  chronic_condition: "Long-term condition",
};

const today = () => new Date().toISOString().slice(0, 10);

/** Adds one entry. The name offers the words the medication check understands, but any name can be saved. */
export function HealthEntryForm({
  options,
  busy,
  onAdd,
}: {
  options: HealthOptions;
  busy: boolean;
  /** Resolves to an error message, or null when saved. */
  onAdd: (entry: HealthEntryInput) => Promise<string | null>;
}) {
  const listId = useId();
  const [kind, setKind] = useState<HealthKind>("allergy");
  const [name, setName] = useState("");
  const [severity, setSeverity] = useState("");
  const [note, setNote] = useState("");
  const [since, setSince] = useState("");
  const [error, setError] = useState("");

  const suggestions = kind === "allergy" ? options.allergies : options.conditions;
  const tooShort = name.trim().length < 2;

  async function submit(event: FormEvent) {
    event.preventDefault();
    if (tooShort || busy) return;
    setError("");
    const failure = await onAdd({
      kind,
      name: name.trim(),
      ...(kind === "allergy" && severity ? { severity: severity as "mild" | "moderate" | "severe" } : {}),
      ...(note.trim() ? { note: note.trim() } : {}),
      ...(since ? { since } : {}),
    });
    if (failure) {
      setError(failure);
      return;
    }
    setName("");
    setSeverity("");
    setNote("");
    setSince("");
  }

  return (
    <form onSubmit={submit} aria-label="Add to the health record" className="space-y-4 rounded-control border border-line bg-surface-soft p-4">
      <p className="text-sm font-semibold text-ink">Add to the record</p>
      <div className="grid gap-4 sm:grid-cols-2">
        <SelectField label="Type" value={kind} onChange={(event) => setKind(event.target.value as HealthKind)}>
          {Object.entries(KIND_LABEL).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </SelectField>
        <div>
          <TextField
            label={kind === "allergy" ? "Allergic to" : "Name"}
            value={name}
            maxLength={160}
            list={listId}
            autoComplete="off"
            placeholder={kind === "allergy" ? "For example: penicillin" : "For example: diabetes"}
            onChange={(event) => setName(event.target.value)}
          />
          <datalist id={listId}>
            {suggestions.map((suggestion) => (
              <option key={suggestion} value={suggestion} />
            ))}
          </datalist>
        </div>
        {kind === "allergy" ? (
          <SelectField label="How serious (optional)" value={severity} onChange={(event) => setSeverity(event.target.value)}>
            <option value="">Not sure</option>
            <option value="mild">Mild</option>
            <option value="moderate">Moderate</option>
            <option value="severe">Severe</option>
          </SelectField>
        ) : null}
        <TextField label="Since (optional)" type="date" max={today()} value={since} onChange={(event) => setSince(event.target.value)} />
      </div>
      <TextAreaField
        label="Note (optional)"
        value={note}
        maxLength={500}
        rows={2}
        placeholder="For example: skin rash after one dose"
        onChange={(event) => setNote(event.target.value)}
      />
      {error ? <Alert tone="error">{error}</Alert> : null}
      <Button type="submit" loading={busy} disabled={tooShort} icon={<Plus className="h-4 w-4" />}>
        {busy ? "Saving..." : "Add to the record"}
      </Button>
    </form>
  );
}
