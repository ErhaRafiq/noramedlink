import { CalendarPlus, MapPin, Star, Wallet } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { formatMoney } from "@/lib/money";
import type { AppointmentDoctor } from "@/lib/types";

function availability(doctor: AppointmentDoctor) {
  if (doctor.available_today === null) return { label: "Availability not set", tone: "neutral" as const };
  return doctor.available_today ? { label: "Available today", tone: "success" as const } : { label: "Not today", tone: "neutral" as const };
}

export function DoctorCard({
  doctor,
  booking,
  disabled,
  onBook,
}: {
  doctor: AppointmentDoctor;
  /** This card's booking is in progress. */
  booking: boolean;
  /** Another booking is in progress. */
  disabled: boolean;
  onBook: (doctor: AppointmentDoctor) => void;
}) {
  const badge = availability(doctor);
  return (
    <article className="flex h-full flex-col rounded-card border border-line bg-white p-5 shadow-card transition-colors hover:border-line-strong">
      <div>
        <h3 className="break-words text-base font-semibold text-ink">{doctor.name}</h3>
        <p className="mt-0.5 text-sm font-medium text-brand-blue">{doctor.specialty}</p>
        <Badge tone={badge.tone} className="mt-2">
          {badge.label}
        </Badge>
      </div>
      <dl className="mt-4 flex-1 space-y-2 text-sm text-ink-muted">
        <div className="flex items-start gap-2">
          <dt className="sr-only">Location</dt>
          <MapPin className="mt-0.5 h-4 w-4 flex-shrink-0 text-slate-400" aria-hidden />
          <dd>{doctor.location || "Location not provided"}</dd>
        </div>
        <div className="flex items-center gap-2">
          <dt className="sr-only">Rating</dt>
          <Star className="h-4 w-4 flex-shrink-0 text-slate-400" aria-hidden />
          <dd>{doctor.rating === null ? "No ratings yet" : `${doctor.rating.toFixed(1)} / 5`}</dd>
        </div>
        <div className="flex items-center gap-2">
          <dt className="sr-only">Consultation fee</dt>
          <Wallet className="h-4 w-4 flex-shrink-0 text-slate-400" aria-hidden />
          <dd>{doctor.consultation_fee ? `${formatMoney(doctor.consultation_fee)} per consultation` : "Fee not set yet"}</dd>
        </div>
      </dl>
      <Button
        className="mt-5 w-full"
        loading={booking}
        disabled={disabled}
        icon={<CalendarPlus className="h-4 w-4" />}
        onClick={() => onBook(doctor)}
      >
        {booking ? "Booking..." : "Book appointment"}
      </Button>
    </article>
  );
}

export function DoctorCardSkeleton() {
  return (
    <div className="rounded-card border border-line bg-white p-5 shadow-card">
      <div className="space-y-2">
        <Skeleton className="h-4 w-3/4" />
        <Skeleton className="h-3 w-1/2" />
        <Skeleton className="h-5 w-24 rounded-full" />
      </div>
      <div className="mt-5 space-y-2">
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-2/3" />
      </div>
      <Skeleton className="mt-5 h-11 w-full" />
    </div>
  );
}
