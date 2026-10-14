"use client";

import { RefreshCw } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { SelectField } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { formatDateTime } from "@/lib/datetime";
import type { ClinicalSummaryVersion } from "@/lib/types";
import { useClinicalSummary } from "@/hooks/doctor/use-clinical-summary";
import { SummarySections } from "./SummarySections";

function versionLine(summary: ClinicalSummaryVersion) {
  return `Version ${summary.version} · ${formatDateTime(summary.generated_at)} · ${summary.trigger}`;
}

/** The clinical summary of the selected patient (active access grant only). Built by fixed rules;
 * AI may only word the key findings. Out of date: the previous version stays, labelled, while a new
 * one is built. */
export function ClinicalSummaryCard({ token, patientId, patientName }: { token: string; patientId: number; patientName: string }) {
  const summary = useClinicalSummary(token, patientId);
  const current = summary.status?.summary ?? null;
  const shown = summary.viewing ?? current;
  const busy = summary.phase === "loading" || summary.phase === "updating";

  return (
    <section id="clinical-summary" className="min-w-0 scroll-mt-24 rounded-card border border-line bg-white p-5 shadow-card sm:p-6">
      <div className="mb-5 flex flex-wrap items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="section-eyebrow">Clinical summary</p>
          <h2 className="mt-1.5 break-words text-lg font-semibold text-ink">{patientName}</h2>
          {current ? <p className="mt-1 break-words text-xs text-ink-muted">{versionLine(current)}</p> : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {summary.phase === "current" && <Badge tone="success">Up to date</Badge>}
          {summary.phase === "updating" && current && <Badge tone="info">Out of date, updating…</Badge>}
          {summary.phase === "update-failed" && <Badge tone="warning">Out of date</Badge>}
          <Button
            variant="secondary"
            size="sm"
            icon={<RefreshCw className="h-4 w-4" aria-hidden />}
            loading={summary.phase === "updating"}
            disabled={busy}
            onClick={summary.regenerate}
          >
            {summary.phase === "updating" ? "Updating..." : "Regenerate"}
          </Button>
        </div>
      </div>

      {summary.phase === "loading" || (summary.phase === "updating" && !current) ? (
        <div role="status" aria-label={summary.phase === "loading" ? "Loading the clinical summary" : "Building the first summary"} className="space-y-3">
          <Skeleton className="h-20 w-full" />
          <Skeleton className="h-4 w-48" />
          <Skeleton className="h-14 w-full" />
          <Skeleton className="h-14 w-full" />
        </div>
      ) : summary.phase === "error" ? (
        <Alert tone="error" title="The clinical summary could not be loaded">
          {summary.error}{" "}
          <button type="button" className="font-semibold underline" onClick={() => void summary.reload()}>
            Try again
          </button>
        </Alert>
      ) : !shown ? (
        <Alert tone="error" title="No summary yet">
          {summary.error ?? "The first summary could not be built."}{" "}
          <button type="button" className="font-semibold underline" onClick={summary.regenerate}>
            Try again
          </button>
        </Alert>
      ) : (
        <>
          {summary.phase === "update-failed" && current ? (
            <Alert tone="warning" title={`Out of date: showing version ${current.version} from ${formatDateTime(current.generated_at)}`} className="mb-4">
              {summary.status?.pending_change ? `Changed since: ${summary.status.pending_change} ` : null}
              Updating failed: {summary.error}
            </Alert>
          ) : null}
          {summary.phase === "updating" && summary.status?.pending_change ? (
            <Alert tone="info" className="mb-4">
              Out of date ({summary.status.pending_change}). Showing version {current?.version} while the new one is built.
            </Alert>
          ) : null}
          {summary.viewing ? (
            <Alert tone="info" title={`Viewing an earlier version (${summary.viewing.version})`} className="mb-4">
              {versionLine(summary.viewing)}.{" "}
              <button type="button" className="font-semibold underline" onClick={() => void summary.viewVersion(null)}>
                Back to the current version
              </button>
            </Alert>
          ) : null}

          <SummarySections content={shown.content} />

          <div className="mt-6 flex flex-col gap-3 border-t border-line pt-4 sm:flex-row sm:items-end sm:justify-between">
            <p className="max-w-2xl text-xs leading-5 text-ink-muted">{shown.note}</p>
            <div className="w-full sm:w-56" onFocus={() => summary.versions === null && void summary.loadVersions()}>
              <SelectField
                label="Version"
                value={shown.version}
                onChange={(event) => void summary.viewVersion(Number(event.target.value))}
                onMouseDown={() => summary.versions === null && void summary.loadVersions()}
              >
                {(summary.versions ?? [current ?? shown]).map((v) => (
                  <option key={v.version} value={v.version}>
                    Version {v.version}
                    {v.is_current ? " (current)" : ""} · {formatDateTime(v.generated_at)}
                  </option>
                ))}
              </SelectField>
              {summary.viewError ? <p className="mt-1 text-xs text-rose-700">{summary.viewError}</p> : null}
            </div>
          </div>
        </>
      )}
    </section>
  );
}
