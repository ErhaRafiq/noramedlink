import { History, PhoneCall } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { formatDateTime } from "@/lib/datetime";
import type { LegacyHomeVisitRequest, PatientHomeVisit } from "@/lib/types";

const TONE: Partial<Record<PatientHomeVisit["status"], BadgeTone>> = {
  closed: "success",
  referred_emergency: "danger",
  no_doctor_found: "warning",
  expired: "warning",
  declined: "warning",
  cancelled: "neutral",
};

function Summary({ visit }: { visit: PatientHomeVisit }) {
  if (!visit.summary) return null;
  return (
    <dl className="mt-3 space-y-2 rounded-control bg-surface-soft p-3 text-sm">
      <div>
        <dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">What the doctor found</dt>
        <dd className="mt-0.5 break-words text-ink">{visit.summary.findings}</dd>
      </div>
      <div>
        <dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Advice</dt>
        <dd className="mt-0.5 break-words text-ink">{visit.summary.advice}</dd>
      </div>
      <div>
        <dt className="text-xs font-semibold uppercase tracking-wide text-ink-muted">Follow-up</dt>
        <dd className="mt-0.5 break-words text-ink">{visit.summary.follow_up}</dd>
      </div>
    </dl>
  );
}

/** Past visits with their summaries, and requests from before the home-visit service (read-only). */
export function VisitHistory({ visits, legacy }: { visits: PatientHomeVisit[]; legacy: LegacyHomeVisitRequest[] }) {
  if (visits.length === 0 && legacy.length === 0) return null;
  return (
    <section aria-labelledby="history-title" className="mt-6 rounded-card border border-line bg-white p-5 shadow-card sm:p-6">
      <h2 id="history-title" className="flex items-center gap-2 text-base font-semibold text-ink">
        <History className="h-4 w-4 text-ink-muted" aria-hidden />
        Earlier requests
      </h2>
      <ul className="mt-4 space-y-4">
        {visits.map((visit) => (
          <li key={visit.id} className="rounded-control border border-line p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-medium text-ink">{formatDateTime(visit.created_at)}</p>
              <Badge tone={TONE[visit.status] ?? "neutral"}>{visit.status_label}</Badge>
            </div>
            <p className="mt-1 break-words text-xs text-ink-muted">
              {visit.specialty}
              {visit.doctor ? `, with ${visit.doctor.name}` : ""}
            </p>
            {visit.emergency_notice ? (
              <Alert tone="error" className="mt-3" title="Your doctor advised emergency care">
                <span className="inline-flex items-start gap-2">
                  <PhoneCall className="mt-1 h-4 w-4 flex-shrink-0" aria-hidden />
                  {visit.emergency_notice}
                </span>
              </Alert>
            ) : null}
            <Summary visit={visit} />
          </li>
        ))}
        {legacy.map((old) => (
          <li key={`old-${old.id}`} className="rounded-control border border-dashed border-line p-4">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-medium text-ink">{formatDateTime(old.created_at)}</p>
              <Badge>Before the service</Badge>
            </div>
            <p className="mt-1 text-xs text-ink-muted">{old.note}</p>
            <p className="mt-2 break-words text-sm text-ink">{old.symptoms}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}
