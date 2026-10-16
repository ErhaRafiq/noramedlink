"use client";

import { Card, CardHeader } from "@/components/ui/card";
import { HealthRecordPanel } from "@/components/records/HealthRecordPanel";

/** The patient's allergies, diagnoses and conditions, for a doctor holding an active access grant. */
export function HealthRecordCard({ patientId, patientName }: { patientId: number; patientName: string }) {
  return (
    <Card id="health-record">
      <CardHeader
        eyebrow="Health record"
        title={`Allergies and conditions: ${patientName}`}
        description="Used by the medication safety check. You can add and change entries; the patient sees who added each one."
      />
      <HealthRecordPanel scope={{ role: "doctor", patientId }} />
    </Card>
  );
}
