import { UserRound } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import type { HomeVisitChoice } from "@/lib/types";

/** Doctors who could take this request, nearest and best match first. Distances are straight lines. */
export function DoctorChoices({
  choices,
  sending,
  disabled,
  onChoose,
  onBack,
}: {
  choices: HomeVisitChoice[];
  sending: boolean;
  disabled: boolean;
  onChoose: (doctorId: number) => void;
  onBack: () => void;
}) {
  if (choices.length === 0) {
    return (
      <EmptyState
        icon={UserRound}
        title="No doctor near you can take a home visit right now"
        description="Doctors have to be nearby, switched on for home visits and available. You can try automatic matching, try again later, or book a clinic appointment."
        action={
          <Button variant="secondary" size="sm" onClick={onBack}>
            Back
          </Button>
        }
      />
    );
  }
  return (
    <section aria-label="Doctors near you">
      <p className="text-sm text-ink-muted">
        Choose one doctor. Your request goes to that doctor only, and they have 10 minutes to answer.
      </p>
      <ul className="mt-3 space-y-3">
        {choices.map((doctor) => (
          <li key={doctor.doctor_id} className="rounded-control border border-line bg-white p-4">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="break-words text-sm font-semibold text-ink">{doctor.name}</p>
                <p className="break-words text-xs text-ink-muted">
                  {doctor.specialty}
                  {doctor.hospital ? `, ${doctor.hospital}` : ""}
                </p>
                <p className="mt-1 flex flex-wrap items-center gap-2 text-xs text-ink-muted">
                  <span>{doctor.distance}</span>
                  <Badge tone={doctor.availability === "now" ? "success" : "info"}>
                    {doctor.availability === "now" ? "Available now" : "Starts within 2 hours"}
                  </Badge>
                </p>
              </div>
              <Button
                size="sm"
                loading={sending}
                disabled={disabled}
                onClick={() => onChoose(doctor.doctor_id)}
                aria-label={`Send the request to ${doctor.name}`}
              >
                {sending ? "Sending..." : "Send request"}
              </Button>
            </div>
          </li>
        ))}
      </ul>
      <Button variant="ghost" size="sm" className="mt-3" onClick={onBack}>
        Back
      </Button>
    </section>
  );
}
