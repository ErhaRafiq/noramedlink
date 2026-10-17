"use client";

import { Activity, CheckCircle2, Inbox, UserPlus, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { formatDateTime } from "@/lib/datetime";
import type { AdminActivity, AdminDashboardStats, AdminDoctor, AdminUser, SymptomStats } from "@/lib/types";
import { PmdcPanel } from "./PmdcPanel";
import type { DoctorDecision } from "@/hooks/admin/use-admin-dashboard";

export function DoctorReviewQueue({
  doctors,
  deciding,
  onApprove,
  onReject,
}: {
  doctors: AdminDoctor[];
  deciding: { doctorId: number; decision: DoctorDecision } | null;
  onApprove: (doctor: AdminDoctor) => void;
  onReject: (doctor: AdminDoctor) => void;
}) {
  return (
    <Card id="doctors">
      <CardHeader
        eyebrow="Verification"
        title="Doctors waiting for review"
        description="Check the PMDC registration number before approving. Approved doctors become visible and bookable; PMDC verification is separate and not required."
        action={<Badge tone={doctors.length > 0 ? "warning" : "neutral"}>{doctors.length} pending</Badge>}
      />
      {doctors.length === 0 ? (
        <EmptyState icon={Inbox} title="No doctors waiting" description="New doctor registrations will appear here." />
      ) : (
        <ul className="space-y-3">
          {doctors.map((doctor) => {
            const busy = deciding?.doctorId === doctor.id;
            return (
              <li key={doctor.id} className="rounded-control border border-line p-4">
                <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
                  <div className="min-w-0">
                    <p className="break-words font-semibold text-ink">{doctor.fullName}</p>
                    <p className="mt-0.5 break-all text-sm text-ink-muted">{doctor.email}</p>
                    <dl className="mt-2 space-y-0.5 text-sm">
                      <div>
                        <dt className="inline text-ink-muted">PMDC/PMC: </dt>
                        <dd className="inline font-medium text-ink">{doctor.pmdcNumber || "Not provided"}</dd>
                      </div>
                      <div>
                        <dt className="inline text-ink-muted">Specialty: </dt>
                        <dd className="inline font-medium text-ink">{doctor.specialization || "Not provided"}</dd>
                      </div>
                      <div>
                        <dt className="inline text-ink-muted">Hospital: </dt>
                        <dd className="inline font-medium text-ink">{doctor.hospitalName || "Not provided"}</dd>
                      </div>
                    </dl>
                  </div>
                  <div className="flex flex-shrink-0 gap-2">
                    <Button
                      size="sm"
                      loading={busy && deciding?.decision === "approve"}
                      disabled={deciding !== null}
                      icon={<CheckCircle2 className="h-4 w-4" />}
                      onClick={() => onApprove(doctor)}
                    >
                      {busy && deciding?.decision === "approve" ? "Approving..." : "Approve"}
                    </Button>
                    <Button variant="danger" size="sm" disabled={deciding !== null} icon={<XCircle className="h-4 w-4" />} onClick={() => onReject(doctor)}>
                      Reject
                    </Button>
                  </div>
                </div>
                <PmdcPanel doctorId={doctor.id} initial={doctor.pmdc} />
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

export function RecentAccounts({ users }: { users: AdminUser[] }) {
  return (
    <Card id="users">
      <CardHeader eyebrow="Accounts" title="Newest sign-ups" />
      {users.length === 0 ? (
        <EmptyState icon={UserPlus} title="No accounts yet" />
      ) : (
        <ul className="divide-y divide-line">
          {users.map((user) => (
            <li key={user.id} className="flex items-center justify-between gap-3 py-3 first:pt-0 last:pb-0">
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-ink">{user.fullName}</p>
                <p className="truncate text-xs text-ink-muted">{user.email}</p>
              </div>
              <div className="flex flex-shrink-0 items-center gap-2">
                {!user.isActive ? <Badge tone="danger">inactive</Badge> : null}
                <Badge tone={user.role === "doctor" ? "info" : user.role === "admin" ? "warning" : "neutral"}>{user.role}</Badge>
              </div>
            </li>
          ))}
        </ul>
      )}
    </Card>
  );
}

export function AccountOverview({ stats, pendingDoctors }: { stats: AdminDashboardStats; pendingDoctors: number }) {
  const metrics = [
    { label: "Patients", value: stats.totalPatients },
    { label: "Active accounts", value: stats.activeUsers },
    { label: "Doctors pending", value: pendingDoctors },
  ];
  return (
    <Card id="overview">
      <CardHeader eyebrow="Accounts" title="Account overview" />
      <dl className="grid gap-3 sm:grid-cols-3">
        {metrics.map((metric) => (
          <div key={metric.label} className="rounded-control border border-line bg-surface-soft p-4">
            <dt className="text-xs font-medium text-ink-muted">{metric.label}</dt>
            <dd className="mt-1 text-2xl font-semibold text-ink">{metric.value}</dd>
          </div>
        ))}
      </dl>
    </Card>
  );
}

/** How the symptom checker is used: counts only, never what people typed. */
export function SymptomUsage({ stats }: { stats: SymptomStats | null }) {
  return (
    <Card id="symptoms">
      <CardHeader eyebrow="Symptom checker" title="How it is used" />
      {stats === null ? (
        <p className="text-sm text-ink-muted">The symptom counts could not be loaded.</p>
      ) : stats.total === 0 ? (
        <p className="text-sm text-ink-muted">No one has used the symptom checker yet.</p>
      ) : (
        <>
          <dl className="grid gap-3 sm:grid-cols-3">
            {[
              { label: "Checks in total", value: stats.total },
              { label: "Last 7 days", value: stats.last_7_days },
              { label: "Sent to emergency advice", value: stats.emergencies },
            ].map((metric) => (
              <div key={metric.label} className="rounded-control border border-line bg-surface-soft p-4">
                <dt className="text-xs font-medium text-ink-muted">{metric.label}</dt>
                <dd className="mt-1 text-2xl font-semibold text-ink">{metric.value}</dd>
              </div>
            ))}
          </dl>
          {stats.by_specialty.length > 0 ? (
            <ul aria-label="Suggestions by specialty" className="mt-4 divide-y divide-line text-sm">
              {stats.by_specialty.map((row) => (
                <li key={row.specialty} className="flex items-center justify-between gap-3 py-2">
                  <span className="min-w-0 break-words text-ink">{row.specialty}</span>
                  <span className="font-semibold text-ink">{row.count}</span>
                </li>
              ))}
            </ul>
          ) : null}
        </>
      )}
    </Card>
  );
}

export function RecentActivity({ activity }: { activity: AdminActivity[] }) {
  return (
    <Card id="activity">
      <CardHeader eyebrow="Platform" title="Recent activity" />
      {activity.length === 0 ? (
        <EmptyState icon={Activity} title="No activity yet" />
      ) : (
        <ol className="space-y-3">
          {activity.map((item) => (
            <li key={item.id} className="flex flex-col gap-1 rounded-control border border-line p-3 sm:flex-row sm:items-start sm:justify-between sm:gap-4">
              <div className="min-w-0">
                <p className="text-sm font-semibold text-ink">{item.title}</p>
                <p className="text-sm text-ink-muted">{item.description}</p>
              </div>
              <time dateTime={item.createdAt} className="flex-shrink-0 text-xs text-ink-muted">
                {formatDateTime(item.createdAt)}
              </time>
            </li>
          ))}
        </ol>
      )}
    </Card>
  );
}
