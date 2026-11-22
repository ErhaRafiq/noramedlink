"use client";

import { Card, CardHeader } from "@/components/ui/card";
import { BodyMeasurementsPanel } from "@/components/records/BodyMeasurementsPanel";

/** Weight, height and pregnancy status of a patient, for a doctor holding an active access grant. */
export function BodyMeasurementsCard({ patientId, patientName, doctorName }: { patientId: number; patientName: string; doctorName: string }) {
  return (
    <Card id="body-measurements">
      <CardHeader
        eyebrow="Body measurements"
        title={`Weight and height: ${patientName}`}
        description="Used by the weight-based dose check and the clinical summary. Record a reading during the consultation."
      />
      <BodyMeasurementsPanel scope={{ role: "doctor", patientId }} doctorName={doctorName} />
    </Card>
  );
}
