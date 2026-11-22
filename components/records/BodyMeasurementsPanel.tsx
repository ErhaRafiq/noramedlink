"use client";

import { useState } from "react";
import { Pencil, Trash2 } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useBodyMeasurements } from "@/hooks/records/use-body-measurements";
import type { RecordScope } from "@/hooks/records/use-health-record";
import type { BodyMeasurement, BodySummary, DoctorBodySummary } from "@/lib/types";
import { BodyMeasurementForm, type BodyFormValues } from "./BodyMeasurementForm";
import { PregnancyControl } from "./PregnancyControl";

const isDoctorSummary = (summary: BodySummary | DoctorBodySummary): summary is DoctorBodySummary => "bmi_category_note" in summary;

function who(role: "patient" | "doctor", name: string | null, viewerIsPatient: boolean) {
  if (role === "doctor") return name ? `Dr ${name.replace(/^Dr\.?\s+/i, "")}` : "a doctor";
  return viewerIsPatient ? "you" : "the patient";
}

function Tile({ label, value, detail }: { label: string; value: string | null; detail: string }) {
  return (
    <div className="min-w-0 rounded-control border border-line bg-white p-3.5">
      <p className="text-xs font-medium text-ink-muted">{label}</p>
      <p className={value ? "mt-1 break-words text-lg font-semibold text-ink" : "mt-1 text-lg font-semibold text-slate-400"}>{value ?? "Not recorded"}</p>
      <p className="mt-0.5 break-words text-xs text-ink-muted">{detail}</p>
    </div>
  );
}

/**
 * Weight and height of one patient: the latest values with the BMI, the dated history, and the pregnancy status.
 * For the patient (own readings: correct or remove) or a doctor with an active grant (add; correct or remove only
 * readings they entered). Nothing is filled in: a missing value says "Not recorded". Advisory, for physician review.
 */
export function BodyMeasurementsPanel({ scope, doctorName }: { scope: RecordScope; doctorName?: string }) {
  const body = useBodyMeasurements(scope);
  const [editing, setEditing] = useState<BodyMeasurement | null>(null);
  const [removing, setRemoving] = useState<BodyMeasurement | null>(null);
  const [problem, setProblem] = useState("");
  const isPatient = scope.role === "patient";

  const canChange = (row: BodyMeasurement) =>
    isPatient ? row.added_by_role === "patient" : row.added_by_role === "doctor" && row.added_by_name === doctorName;

  async function save(values: BodyFormValues): Promise<string | null> {
    if (editing) {
      const failure = await body.change(editing.id, {
        weight: values.weight,
        weight_unit: values.unit,
        height_cm: values.height,
        measured_on: values.date,
      });
      if (!failure) setEditing(null);
      return failure;
    }
    return body.add({
      ...(values.weight !== null ? { weight: values.weight, weight_unit: values.unit } : {}),
      ...(values.height !== null ? { height_cm: values.height } : {}),
      measured_on: values.date,
    });
  }

  async function confirmRemove() {
    if (!removing) return;
    const failure = await body.remove(removing.id);
    if (failure) setProblem(failure);
    setRemoving(null);
  }

  if (body.status === "loading") {
    return (
      <div role="status" aria-label="Loading weight and height" className="space-y-3">
        <div className="grid gap-3 sm:grid-cols-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-20 w-full" />
        </div>
        <Skeleton className="h-14 w-full" />
        <Skeleton className="h-14 w-full" />
      </div>
    );
  }
  if (body.status === "error" || !body.summary) {
    return (
      <Alert tone="error" title="Weight and height could not be loaded">
        {body.error}{" "}
        <button type="button" onClick={body.retry} className="font-semibold underline">
          Try again
        </button>
      </Alert>
    );
  }

  const summary = body.summary;
  const doctorView = isDoctorSummary(summary) ? summary : null;
  const weight = summary.weight;
  const height = summary.height;
  const entered = (reading: typeof weight, row: BodyMeasurement | undefined) =>
    reading ? `${reading.measured_on}, entered by ${who(reading.added_by_role, row?.added_by_name ?? null, isPatient)}` : "No reading yet";
  const latestWeightRow = body.rows.find((r) => r.weight_kg !== null && r.measured_on === weight?.measured_on);
  const latestHeightRow = body.rows.find((r) => r.height_cm !== null && r.measured_on === height?.measured_on);

  return (
    <div className="space-y-6">
      {problem ? <Alert tone="error">{problem}</Alert> : null}

      <section aria-label="Latest weight and height" className="grid gap-3 sm:grid-cols-3">
        <Tile label="Weight" value={weight ? `${weight.value} kg` : null} detail={entered(weight, latestWeightRow)} />
        <Tile label="Height" value={height ? `${height.value} cm` : null} detail={entered(height, latestHeightRow)} />
        <Tile
          label="BMI"
          value={summary.bmi !== null ? `${summary.bmi} kg/m²` : null}
          detail={
            summary.bmi !== null
              ? doctorView
                ? (doctorView.bmi_category ?? doctorView.bmi_category_note ?? "")
                : (summary.bmi_note ?? "")
              : weight && !height
                ? "Needs a height"
                : height && !weight
                  ? "Needs a weight"
                  : "Needs a weight and a height"
          }
        />
      </section>

      {doctorView ? (
        <div className="space-y-3">
          {doctorView.weight_current === false ? (
            <Alert tone="warning" title="Weight is out of date">
              The last weight is older than {doctorView.weight_max_age_days} days (app rule (demo)). Re-measure before weight-based dose checks; the
              medicine check will say &ldquo;weight needed for dose check&rdquo;.
            </Alert>
          ) : null}
          {doctorView.weight === null ? (
            <Alert tone="info" title="Weight not recorded">
              Weight-based dose checks need a recorded weight. Nothing is assumed.
            </Alert>
          ) : null}
          {doctorView.weight_change_flags.map((flag) => (
            <Alert key={flag.window_days} tone="warning" title={`${flag.wording[0].toUpperCase()}${flag.wording.slice(1)}`}>
              {flag.percent > 0 ? "+" : ""}
              {flag.percent}% within {flag.window_days} days ({flag.from_kg} kg on {flag.from_date} to {flag.to_kg} kg on {flag.to_date}). Basis:{" "}
              {flag.basis}
              {flag.percent > 0 ? " (app rule (demo))" : ""}.
            </Alert>
          ))}
          {doctorView.bmi_asian_note ? <p className="text-xs leading-5 text-ink-muted">{doctorView.bmi_asian_note}</p> : null}
        </div>
      ) : summary.bmi !== null ? (
        <p className="text-xs leading-5 text-ink-muted">The BMI is a number from your weight and height. It is not a diagnosis; your doctor reads it with your history.</p>
      ) : null}

      <PregnancyControl
        state={body.pregnancy}
        gender={body.gender}
        viewerIsPatient={isPatient}
        busy={body.busyId === "pregnancy"}
        onSave={body.setPregnancyStatus}
      />

      <section aria-label="Weight and height history">
        <h3 className="text-sm font-semibold text-ink">History</h3>
        {body.rows.length === 0 ? (
          <p className="mt-2 rounded-control border border-dashed border-line p-3 text-sm text-ink-muted">No weight or height recorded yet.</p>
        ) : (
          <ul className="mt-2 space-y-2">
            {body.rows.map((row) => (
              <li key={row.id} className="min-w-0 rounded-control border border-line bg-white p-3.5">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="break-words text-sm font-semibold text-ink">
                      {row.weight_kg !== null ? `${row.weight_kg} kg` : "Weight not recorded"}
                      {" · "}
                      {row.height_cm !== null ? `${row.height_cm} cm` : "height not recorded"}
                    </p>
                    <p className="mt-1 text-xs text-ink-muted">
                      {row.measured_on} · entered by {who(row.added_by_role, row.added_by_name, isPatient)}
                    </p>
                    {row.added_by_role === "doctor" && isPatient ? (
                      <Badge tone="info" className="mt-1.5">
                        Added by your doctor
                      </Badge>
                    ) : null}
                  </div>
                  {canChange(row) ? (
                    <div className="flex flex-shrink-0 gap-2">
                      <Button
                        variant="secondary"
                        size="sm"
                        disabled={body.busyId !== null}
                        icon={<Pencil className="h-4 w-4" />}
                        onClick={() => setEditing(row)}
                        aria-label={`Correct the reading of ${row.measured_on}`}
                      >
                        Correct
                      </Button>
                      <Button
                        variant="ghost"
                        size="sm"
                        disabled={body.busyId !== null}
                        icon={<Trash2 className="h-4 w-4" />}
                        onClick={() => setRemoving(row)}
                        aria-label={`Remove the reading of ${row.measured_on}`}
                      >
                        Remove
                      </Button>
                    </div>
                  ) : null}
                </div>
              </li>
            ))}
          </ul>
        )}
        {body.rows.length < body.total ? (
          <Button
            variant="secondary"
            size="sm"
            className="mt-3"
            loading={body.busyId === "more"}
            onClick={async () => setProblem((await body.loadMore()) ?? "")}
          >
            {body.busyId === "more" ? "Loading..." : `Show more (${body.total - body.rows.length} older)`}
          </Button>
        ) : null}
      </section>

      <BodyMeasurementForm
        key={editing ? `edit-${editing.id}` : "new"}
        editing={editing ?? undefined}
        busy={editing ? body.busyId === editing.id : body.busyId === "new"}
        onSubmit={save}
        onCancel={editing ? () => setEditing(null) : undefined}
      />

      <p className="text-xs leading-5 text-ink-muted">
        {isPatient
          ? "Your doctors and the medicine safety check use these values. Advisory only; it is not a diagnosis. A doctor you give your one-time code to can add a reading, but only you can correct or remove yours. Every change is written to your access history."
          : (doctorView?.disclaimer ??
            "Advisory only, for physician review. You can add readings and correct or remove the ones you entered; the patient is told about every change and sees who entered each reading.")}
      </p>

      <ConfirmDialog
        open={removing !== null}
        title="Remove this reading?"
        description={removing ? `The reading of ${removing.measured_on} will be taken off the record. This cannot be undone.` : ""}
        confirmLabel="Remove"
        pendingLabel="Removing..."
        pending={removing !== null && body.busyId === removing.id}
        onConfirm={() => void confirmRemove()}
        onCancel={() => setRemoving(null)}
      />
    </div>
  );
}
