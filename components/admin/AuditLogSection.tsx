"use client";

import { useState } from "react";
import { ScrollText } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { SelectField, TextField } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { NO_FILTERS, useAuditLog, type AuditFilters } from "@/hooks/admin/use-audit-log";
import { formatDateTime } from "@/lib/datetime";

const ROLE_TONE: Record<string, BadgeTone> = { patient: "info", doctor: "success", admin: "warning" };

/** Who viewed or changed whose record, newest first. Rows hold no medical text, only what happened. */
export function AuditLogSection() {
  const [filters, setFilters] = useState<AuditFilters>(NO_FILTERS);
  const log = useAuditLog(true, filters);
  const filtered = filters.action !== "" || filters.actor_role !== "" || filters.subject !== "";
  const set = (patch: Partial<AuditFilters>) => setFilters((current) => ({ ...current, ...patch }));

  return (
    <Card id="audit-log">
      <CardHeader
        eyebrow="Audit log"
        title="Who accessed or changed records"
        description="Every doctor view, access grant, health record change, prescription and override. Rows cannot be edited or deleted."
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <SelectField label="What happened" value={filters.action} onChange={(event) => set({ action: event.target.value })}>
          <option value="">Everything</option>
          {Object.entries(log.actions).map(([value, label]) => (
            <option key={value} value={value}>
              {label}
            </option>
          ))}
        </SelectField>
        <SelectField label="Who did it" value={filters.actor_role} onChange={(event) => set({ actor_role: event.target.value })}>
          <option value="">Anyone</option>
          <option value="doctor">A doctor</option>
          <option value="patient">A patient</option>
          <option value="admin">An administrator</option>
        </SelectField>
        <TextField
          label="About patient number"
          inputMode="numeric"
          placeholder="For example: 42"
          value={filters.subject}
          onChange={(event) => set({ subject: event.target.value.replace(/\D/g, "").slice(0, 9) })}
        />
      </div>
      {filtered ? (
        <Button variant="ghost" size="sm" className="mt-2" onClick={() => setFilters(NO_FILTERS)}>
          Clear filters
        </Button>
      ) : null}

      <div className="mt-5" aria-live="polite">
        {log.status === "loading" ? (
          <div role="status" aria-label="Loading the audit log" className="space-y-2">
            {Array.from({ length: 4 }, (_, i) => (
              <Skeleton key={i} className="h-14 w-full" />
            ))}
          </div>
        ) : log.status === "error" ? (
          <Alert tone="error" title="The audit log could not be loaded">
            {log.error}{" "}
            <button type="button" onClick={log.retry} className="font-semibold underline">
              Try again
            </button>
          </Alert>
        ) : log.rows.length === 0 ? (
          <EmptyState
            icon={ScrollText}
            title={filtered ? "Nothing matches these filters" : "Nothing has been logged yet"}
            description={filtered ? "Try another action or role, or clear the filters." : "Entries appear here as doctors open records and records change."}
          />
        ) : (
          <>
            <p className="mb-2 text-xs text-ink-muted">
              Showing {log.rows.length} of {log.total}
              {log.fetching ? " · updating..." : ""}
            </p>
            <ul className={log.fetching ? "divide-y divide-line opacity-60" : "divide-y divide-line"}>
              {log.rows.map((row) => (
                <li key={row.id} className="min-w-0 py-3 first:pt-0">
                  <div className="flex flex-wrap items-center gap-2">
                    <span className="break-words text-sm font-semibold text-ink">{row.actor_name ?? "Removed account"}</span>
                    <Badge tone={ROLE_TONE[row.actor_role] ?? "neutral"}>{row.actor_role}</Badge>
                  </div>
                  <p className="mt-0.5 break-words text-sm text-ink">
                    {row.action_label}
                    {row.patient_name ? <span className="text-ink-muted"> · patient {row.patient_name} (#{row.patient_id})</span> : null}
                    {row.detail ? <span className="text-ink-muted"> · {row.detail}</span> : null}
                  </p>
                  <p className="mt-0.5 text-xs text-ink-muted">{formatDateTime(row.created_at)}</p>
                </li>
              ))}
            </ul>
            {log.rows.length < log.total ? (
              <Button variant="secondary" size="sm" className="mt-3" loading={log.loadingMore} onClick={() => void log.loadMore()}>
                {log.loadingMore ? "Loading..." : `Show more (${log.total - log.rows.length} left)`}
              </Button>
            ) : null}
          </>
        )}
      </div>
    </Card>
  );
}
