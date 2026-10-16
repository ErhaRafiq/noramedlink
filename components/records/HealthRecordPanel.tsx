"use client";

import { useState } from "react";
import { AlertTriangle, RotateCcw, Trash2, CheckCheck } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { Skeleton } from "@/components/ui/skeleton";
import { useHealthOptions, useHealthRecord, type RecordScope } from "@/hooks/records/use-health-record";
import { formatDateTime } from "@/lib/datetime";
import type { HealthEntry, HealthKind } from "@/lib/types";
import { HealthEntryForm, KIND_LABEL } from "./HealthEntryForm";

const GROUPS: { kind: HealthKind; title: string; empty: string }[] = [
  { kind: "allergy", title: "Allergies", empty: "No allergy recorded." },
  { kind: "diagnosis", title: "Diagnoses", empty: "No diagnosis recorded." },
  { kind: "chronic_condition", title: "Long-term conditions", empty: "No long-term condition recorded." },
];

const SEVERITY_TONE = { mild: "info", moderate: "warning", severe: "danger" } as const;

/**
 * The structured health record, for the patient (who can edit and remove) or for a doctor with an
 * active access grant (who can add and change, not remove). "Nothing recorded" never means "none":
 * it only says nothing has been entered.
 */
export function HealthRecordPanel({ scope }: { scope: RecordScope }) {
  const record = useHealthRecord(scope);
  const options = useHealthOptions();
  const [removing, setRemoving] = useState<HealthEntry | null>(null);
  const [problem, setProblem] = useState("");
  const isPatient = scope.role === "patient";

  async function change(entry: HealthEntry, status: "active" | "resolved") {
    setProblem("");
    const failure = await record.change(entry.id, { status });
    if (failure) setProblem(failure);
  }

  async function confirmRemove() {
    if (!removing) return;
    const failure = await record.remove(removing.id);
    if (failure) setProblem(failure);
    setRemoving(null);
  }

  if (record.status === "loading") {
    return (
      <div role="status" aria-label="Loading the health record" className="space-y-3">
        <Skeleton className="h-5 w-1/3" />
        <Skeleton className="h-16 w-full" />
        <Skeleton className="h-16 w-full" />
      </div>
    );
  }
  if (record.status === "error") {
    return (
      <Alert tone="error" title="The health record could not be loaded">
        {record.error}{" "}
        <button type="button" onClick={record.retry} className="font-semibold underline">
          Try again
        </button>
      </Alert>
    );
  }

  const unusable = record.entries.filter((e) => e.status === "active" && !e.recognised);

  return (
    <div className="space-y-6">
      {problem ? <Alert tone="error">{problem}</Alert> : null}

      {GROUPS.map((group) => {
        const items = record.entries.filter((e) => e.kind === group.kind);
        const active = items.filter((e) => e.status === "active");
        const resolved = items.filter((e) => e.status === "resolved");
        return (
          <section key={group.kind} aria-label={group.title}>
            <h3 className="text-sm font-semibold text-ink">{group.title}</h3>
            {items.length === 0 ? (
              <p className="mt-2 rounded-control border border-dashed border-line p-3 text-sm text-ink-muted">{group.empty}</p>
            ) : (
              <ul className="mt-2 space-y-2">
                {[...active, ...resolved].map((entry) => (
                  <EntryRow
                    key={entry.id}
                    entry={entry}
                    busy={record.busyId === entry.id}
                    disabled={record.busyId !== null}
                    canRemove={isPatient}
                    viewerIsPatient={isPatient}
                    onResolve={() => void change(entry, entry.status === "active" ? "resolved" : "active")}
                    onRemove={() => setRemoving(entry)}
                  />
                ))}
              </ul>
            )}
          </section>
        );
      })}

      {unusable.length > 0 ? (
        <Alert tone="info" title="Some entries are not used by the medication check">
          The check only knows the names in its own list. {unusable.map((e) => e.name).join(", ")}{" "}
          {unusable.length > 1 ? "stay" : "stays"} on the record for doctors to read, but {unusable.length > 1 ? "are" : "is"} not checked
          against new medicines. Pick a name from the suggestions to have {unusable.length > 1 ? "them" : "it"} checked.
        </Alert>
      ) : null}

      <HealthEntryForm options={options} busy={record.busyId === "new"} onAdd={record.add} />

      <p className="text-xs leading-5 text-ink-muted">
        {isPatient
          ? "This list helps the medication safety check and your doctors. It is advisory only and not a diagnosis. A doctor you give your one-time code to can add to it, and every view or change is written to your access history."
          : "Entries you add are shown to the patient, marked as added by you, and used by the medication safety check. Every view and change is written to the audit log. You cannot remove entries; mark them resolved instead."}
      </p>

      <ConfirmDialog
        open={removing !== null}
        title="Remove this entry?"
        description={removing ? `${removing.name} will be taken off your health record and will no longer be used by the medication check.` : ""}
        confirmLabel="Remove"
        pendingLabel="Removing..."
        pending={removing !== null && record.busyId === removing.id}
        onConfirm={() => void confirmRemove()}
        onCancel={() => setRemoving(null)}
      />
    </div>
  );
}

function EntryRow({
  entry,
  busy,
  disabled,
  canRemove,
  viewerIsPatient,
  onResolve,
  onRemove,
}: {
  entry: HealthEntry;
  busy: boolean;
  disabled: boolean;
  canRemove: boolean;
  viewerIsPatient: boolean;
  onResolve: () => void;
  onRemove: () => void;
}) {
  const resolved = entry.status === "resolved";
  return (
    <li className="min-w-0 rounded-control border border-line bg-white p-3.5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className={resolved ? "break-words text-sm font-semibold text-ink-muted line-through" : "break-words text-sm font-semibold text-ink"}>
            {entry.name}
          </p>
          <div className="mt-1.5 flex flex-wrap items-center gap-1.5">
            <Badge>{KIND_LABEL[entry.kind]}</Badge>
            {entry.severity ? <Badge tone={SEVERITY_TONE[entry.severity]}>{entry.severity}</Badge> : null}
            {resolved ? <Badge tone="success">Resolved</Badge> : null}
            {!entry.recognised && !resolved ? (
              <Badge tone="warning">
                <AlertTriangle className="mr-1 inline h-3 w-3" aria-hidden />
                Not used by the check
              </Badge>
            ) : null}
          </div>
          {entry.note ? <p className="mt-2 break-words text-sm text-ink-muted">{entry.note}</p> : null}
          <p className="mt-1.5 text-xs text-ink-muted">
            {entry.added_by_role === "doctor" ? `Added by ${entry.added_by_name ?? "a doctor"}` : viewerIsPatient ? "Added by you" : "Added by the patient"} ·{" "}
            {formatDateTime(entry.created_at)}
            {entry.since ? ` · since ${entry.since}` : ""}
          </p>
        </div>
        <div className="flex flex-shrink-0 gap-2">
          <Button
            variant="secondary"
            size="sm"
            loading={busy}
            disabled={disabled}
            icon={resolved ? <RotateCcw className="h-4 w-4" /> : <CheckCheck className="h-4 w-4" />}
            onClick={onResolve}
            aria-label={`${resolved ? "Mark as current again" : "Mark as resolved"}: ${entry.name}`}
          >
            {busy ? "Saving..." : resolved ? "Reopen" : "Mark resolved"}
          </Button>
          {canRemove ? (
            <Button variant="ghost" size="sm" disabled={disabled} icon={<Trash2 className="h-4 w-4" />} onClick={onRemove} aria-label={`Remove ${entry.name}`}>
              Remove
            </Button>
          ) : null}
        </div>
      </div>
    </li>
  );
}
