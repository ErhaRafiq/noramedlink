import { Award, CalendarPlus, Clock, Languages, MapPin, Wallet } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { clinicDay, clinicTime } from "@/lib/datetime";
import { formatMoney } from "@/lib/money";
import type { AppointmentDoctor } from "@/lib/types";
import { MODE_LABEL } from "./BookingDialog";
import { PmdcBadge } from "./PmdcBadge";
import { RatingSummary } from "./Stars";

function availability(doctor: AppointmentDoctor) {
  if (!doctor.has_schedule) return { label: "No times published yet", tone: "neutral" as const };
  if (doctor.available_today) return { label: "Available today", tone: "success" as const };
  if (doctor.next_available) {
    return { label: `Next: ${clinicDay(doctor.next_available)}, ${clinicTime(doctor.next_available)}`, tone: "info" as const };
  }
  if (!doctor.has_schedule) return { label: "Has not published appointment times yet", tone: "neutral" as const };
  return { label: "Fully booked for two weeks", tone: "warning" as const };
}

export function DoctorCard({ doctor, canBook, onBook }: { doctor: AppointmentDoctor; canBook: boolean; onBook: (doctor: AppointmentDoctor) => void }) {
  const badge = availability(doctor);
  const bookable = doctor.has_schedule && doctor.next_available !== null;
  return (
    <article className="flex h-full flex-col rounded-card border border-line bg-white p-5 shadow-card transition-colors hover:border-line-strong">
      <div>
        <h3 className="break-words text-base font-semibold text-ink">{doctor.name}</h3>
        <p className="mt-0.5 text-sm font-medium text-brand-blue">{doctor.specialty}</p>
        <PmdcBadge verified={doctor.pmdc_verified} checkedAt={doctor.pmdc_checked_at} className="mt-1.5" />
        <RatingSummary rating={doctor.rating} count={doctor.rating_count} className="mt-1.5" />
        <Badge tone={badge.tone} className="mt-2 max-w-full whitespace-normal text-left">
          <Clock className="mr-1 inline h-3 w-3" aria-hidden />
          {badge.label}
        </Badge>
      </div>
      {doctor.consultation_modes.length ? (
        <ul aria-label="Consultation types" className="mt-3 flex flex-wrap gap-1.5">
          {doctor.consultation_modes.map((mode) => (
            <li key={mode}>
              <Badge tone="info">{MODE_LABEL[mode]}</Badge>
            </li>
          ))}
        </ul>
      ) : null}
      <dl className="mt-4 flex-1 space-y-2 text-sm text-ink-muted">
        <div className="flex items-start gap-2">
          <dt className="sr-only">Location</dt>
          <MapPin className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-400" aria-hidden />
          <dd>{[doctor.location, doctor.city].filter(Boolean).join(", ") || "Location not provided"}</dd>
        </div>
        {doctor.qualifications || doctor.experience_years !== null ? (
          <div className="flex items-start gap-2">
            <dt className="sr-only">Qualifications and experience</dt>
            <Award className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-400" aria-hidden />
            <dd className="break-words">
              {[doctor.qualifications, doctor.experience_years !== null ? `${doctor.experience_years} years of experience` : null].filter(Boolean).join(" · ")}
            </dd>
          </div>
        ) : null}
        {doctor.languages.length ? (
          <div className="flex items-start gap-2">
            <dt className="sr-only">Languages</dt>
            <Languages className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-400" aria-hidden />
            <dd>{doctor.languages.join(", ")}</dd>
          </div>
        ) : null}
        <div className="flex items-center gap-2">
          <dt className="sr-only">Consultation fee</dt>
          <Wallet className="h-4 w-4 flex-shrink-0 text-slate-400" aria-hidden />
          <dd>{doctor.consultation_fee ? `${formatMoney(doctor.consultation_fee)} per consultation` : "Fee not set yet"}</dd>
        </div>
      </dl>
      {doctor.bio ? <p className="mt-3 line-clamp-3 break-words text-sm leading-6 text-ink-muted">{doctor.bio}</p> : null}
      <Button className="mt-5 w-full" disabled={!bookable || !canBook} icon={<CalendarPlus className="h-4 w-4" />} onClick={() => onBook(doctor)}>
        {bookable ? "Book appointment" : doctor.has_schedule ? "No free times" : "Times not published yet"}
      </Button>
    </article>
  );
}

export function DoctorCardSkeleton() {
  return (
    <div className="rounded-card border border-line bg-white p-5 shadow-card">
      <div className="space-y-2">
        <Skeleton className="h-5 w-2/3" />
        <Skeleton className="h-4 w-1/3" />
        <Skeleton className="h-6 w-1/2" />
      </div>
      <div className="mt-4 space-y-2">
        <Skeleton className="h-4 w-full" />
        <Skeleton className="h-4 w-4/5" />
      </div>
      <Skeleton className="mt-5 h-11 w-full" />
    </div>
  );
}
