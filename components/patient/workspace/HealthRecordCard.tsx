"use client";

import { ClipboardList } from "lucide-react";

import { HealthRecordPanel } from "@/components/records/HealthRecordPanel";
import { DashCard } from "./ui";

/** The patient's own allergies, diagnoses and long-term conditions: used by the medication safety check. */
export function HealthRecordCard() {
  return (
    <DashCard id="health-record">
      <div className="mb-4 flex items-center gap-3">
        <span className="grid h-9 w-9 place-items-center rounded-control bg-blue-50 text-brand-blue">
          <ClipboardList className="h-4 w-4" aria-hidden />
        </span>
        <div>
          <h2 className="text-base font-semibold text-ink">My health record</h2>
          <p className="text-xs text-ink-muted">Allergies, diagnoses and long-term conditions</p>
        </div>
      </div>
      <HealthRecordPanel scope={{ role: "patient" }} />
    </DashCard>
  );
}
