"use client";

import { Scale } from "lucide-react";

import { BodyMeasurementsPanel } from "@/components/records/BodyMeasurementsPanel";
import { DashCard } from "./ui";

/** The patient's own weight and height history and pregnancy status: used by dose checks and the doctor's summary. */
export function BodyMeasurementsCard() {
  return (
    <DashCard id="body-measurements">
      <div className="mb-4 flex items-center gap-3">
        <span className="grid h-9 w-9 place-items-center rounded-control bg-teal-50 text-teal-700">
          <Scale className="h-4 w-4" aria-hidden />
        </span>
        <div>
          <h2 className="text-base font-semibold text-ink">Weight and height</h2>
          <p className="text-xs text-ink-muted">Dated readings, BMI and pregnancy status</p>
        </div>
      </div>
      <BodyMeasurementsPanel scope={{ role: "patient" }} />
    </DashCard>
  );
}
