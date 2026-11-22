"use client";

import { useState } from "react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { SelectField } from "@/components/ui/field";
import type { PregnancyState, PregnancyStatus } from "@/lib/types";

const LABEL: Record<PregnancyStatus, string> = { not_recorded: "Not recorded", not_pregnant: "Not pregnant", pregnant: "Pregnant" };

/**
 * The pregnancy status: set by the patient or by a doctor with an active grant. Medicine checks use it, so an
 * old "pregnant" status (app rule (demo), `max_months`) counts as not recorded and the page asks for an update.
 */
export function PregnancyControl({
  state,
  gender,
  viewerIsPatient,
  busy,
  onSave,
}: {
  state: PregnancyState | null;
  /** Known for the patient's own view; a status of "pregnant" is refused for patients recorded as male. */
  gender: string | null;
  viewerIsPatient: boolean;
  busy: boolean;
  onSave: (status: PregnancyStatus) => Promise<string | null>;
}) {
  const current = state?.status ?? "not_recorded";
  // null while the person has not touched the list: it then follows what the server says.
  const [picked, setPicked] = useState<PregnancyStatus | null>(null);
  const choice = picked ?? current;
  const [error, setError] = useState("");
  const [saved, setSaved] = useState(false);
  const male = gender?.toLowerCase() === "male";

  async function save() {
    setError("");
    setSaved(false);
    const failure = await onSave(choice);
    if (failure) setError(failure);
    else {
      setSaved(true);
      setPicked(null);
    }
  }

  const who = state?.set_by_role === "doctor" ? "a doctor" : viewerIsPatient ? "you" : "the patient";
  return (
    <section aria-label="Pregnancy status" className="space-y-3 rounded-control border border-line bg-white p-4">
      <h3 className="text-sm font-semibold text-ink">Pregnancy status</h3>
      <p className="text-sm text-ink-muted">
        {current === "not_recorded"
          ? "Not recorded."
          : `${LABEL[current]}, set on ${state?.set_on ?? "an unknown date"} by ${who}.`}{" "}
        It is used by the medicine safety check, for physician review.
      </p>
      {state?.expired ? (
        <Alert tone="warning" title="Please update this status">
          &ldquo;Pregnant&rdquo; was set on {state.set_on}, more than {state.max_months} months ago (app rule (demo)), so it now counts as not
          recorded. {viewerIsPatient ? "Please update it." : "Ask the patient, or update it if you have confirmed it."}
        </Alert>
      ) : null}
      {male && viewerIsPatient ? (
        <p className="text-xs text-ink-muted">Pregnancy status cannot be set to pregnant for a patient recorded as male.</p>
      ) : null}
      <div className="flex flex-wrap items-end gap-3">
        <SelectField
          label="Status"
          wrapperClassName="min-w-0 flex-1 sm:max-w-xs"
          value={choice}
          onChange={(e) => {
            setPicked(e.target.value as PregnancyStatus);
            setSaved(false);
          }}
        >
          {(Object.keys(LABEL) as PregnancyStatus[]).map((value) => (
            <option key={value} value={value} disabled={value === "pregnant" && male && viewerIsPatient}>
              {LABEL[value]}
            </option>
          ))}
        </SelectField>
        <Button variant="secondary" loading={busy} disabled={choice === current && !state?.expired} onClick={() => void save()}>
          {busy ? "Saving..." : "Save status"}
        </Button>
      </div>
      {error ? <Alert tone="error">{error}</Alert> : null}
      {saved ? <p role="status" className="text-xs font-medium text-emerald-700">Pregnancy status saved.</p> : null}
    </section>
  );
}
