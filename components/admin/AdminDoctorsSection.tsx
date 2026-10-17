"use client";

import { useState } from "react";
import { Stethoscope } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { SelectField, TextField } from "@/components/ui/field";
import { Skeleton } from "@/components/ui/skeleton";
import { NO_DOCTOR_FILTERS, useAdminDoctors, type DoctorFilters } from "@/hooks/admin/use-admin-doctors";
import { PmdcPanel } from "./PmdcPanel";

const APPROVAL: Record<string, { label: string; tone: BadgeTone }> = {
  pending: { label: "Waiting for review", tone: "warning" },
  approved: { label: "Approved", tone: "success" },
  rejected: { label: "Rejected", tone: "danger" },
};

/**
 * Every doctor with the approval status and the PMDC verification, so a doctor who was approved earlier can be
 * checked later too. PMDC verification is separate from approval: a doctor can be active without it.
 */
export function AdminDoctorsSection({ refreshKey }: { refreshKey: number }) {
  const [filters, setFilters] = useState<DoctorFilters>(NO_DOCTOR_FILTERS);
  const list = useAdminDoctors(true, filters, refreshKey);
  const filtered = filters.approval !== "" || filters.pmdc !== "" || filters.q !== "";
  const set = (patch: Partial<DoctorFilters>) => setFilters((current) => ({ ...current, ...patch }));

  return (
    <Card id="all-doctors">
      <CardHeader
        eyebrow="Doctors"
        title="All doctors and PMDC verification"
        description="A doctor can be approved and active without PMDC verification. A verified doctor shows a badge to patients."
      />

      <div className="grid gap-4 sm:grid-cols-3">
        <SelectField label="Approval" value={filters.approval} onChange={(event) => set({ approval: event.target.value })}>
          <option value="">Any</option>
          <option value="pending">Waiting for review</option>
          <option value="approved">Approved</option>
          <option value="rejected">Rejected</option>
        </SelectField>
        <SelectField label="PMDC" value={filters.pmdc} onChange={(event) => set({ pmdc: event.target.value })}>
          <option value="">Any</option>
          <option value="verified">PMDC verified</option>
          <option value="unverified">Not PMDC verified</option>
        </SelectField>
        <TextField label="Name or number" placeholder="For example: Rafiq or 12345-P" value={filters.q} maxLength={80} onChange={(event) => set({ q: event.target.value })} />
      </div>
      {filtered ? (
        <Button variant="ghost" size="sm" className="mt-2" onClick={() => setFilters(NO_DOCTOR_FILTERS)}>
          Clear filters
        </Button>
      ) : null}

      <div className="mt-5" aria-live="polite">
        {list.status === "loading" ? (
          <div role="status" aria-label="Loading doctors" className="space-y-3">
            {Array.from({ length: 3 }, (_, i) => (
              <Skeleton key={i} className="h-28 w-full" />
            ))}
          </div>
        ) : list.status === "error" ? (
          <Alert tone="error" title="The doctor list could not be loaded">
            {list.error}{" "}
            <button type="button" onClick={list.retry} className="font-semibold underline">
              Try again
            </button>
          </Alert>
        ) : list.rows.length === 0 ? (
          <EmptyState
            icon={Stethoscope}
            title={filtered ? "No doctor matches these filters" : "No doctors yet"}
            description={filtered ? "Try another status, or clear the filters." : "Doctors appear here after they sign up."}
          />
        ) : (
          <>
            <p className="mb-2 text-xs text-ink-muted">
              Showing {list.rows.length} of {list.total}
              {list.fetching ? " · updating..." : ""}
            </p>
            <ul className={list.fetching ? "space-y-3 opacity-60" : "space-y-3"}>
              {list.rows.map((doctor) => {
                const approval = APPROVAL[doctor.verification_status] ?? { label: doctor.verification_status, tone: "neutral" as const };
                return (
                  <li key={doctor.id} className="min-w-0 rounded-control border border-line p-4">
                    <div className="flex flex-wrap items-center gap-2">
                      <span className="break-words font-semibold text-ink">{doctor.full_name}</span>
                      <Badge tone={approval.tone}>{approval.label}</Badge>
                    </div>
                    <p className="mt-0.5 break-all text-sm text-ink-muted">{doctor.email}</p>
                    <p className="mt-0.5 break-words text-sm text-ink-muted">
                      {doctor.specialization} · {doctor.hospital_name}
                    </p>
                    <PmdcPanel doctorId={doctor.id} initial={doctor.pmdc} />
                  </li>
                );
              })}
            </ul>
            {list.rows.length < list.total ? (
              <Button variant="secondary" size="sm" className="mt-3" loading={list.loadingMore} onClick={() => void list.loadMore()}>
                {list.loadingMore ? "Loading..." : `Show more (${list.total - list.rows.length} left)`}
              </Button>
            ) : null}
          </>
        )}
      </div>
    </Card>
  );
}
