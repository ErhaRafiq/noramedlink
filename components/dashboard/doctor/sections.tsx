"use client";

import { useState, type FormEvent, type ReactNode } from "react";
import { Activity, FileSearch, KeyRound, Pill } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState as SharedEmptyState } from "@/components/ui/empty-state";
import { validationLabel } from "@/lib/patient-dashboard";
import type { DoctorOverview } from "@/lib/types";

type Patient = DoctorOverview["patients"][number];
type Report = DoctorOverview["medicalRecords"][number];
type Medicine = DoctorOverview["medications"][number];

export function formatDateTime(value: string | null | undefined) {
  if (!value) return "Not available";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function formatStatus(value: string) {
  return value.replaceAll("_", " ").toLowerCase();
}

function validationTone(status: string | null) {
  if (status === "HIGH_RISK") return "bg-rose-50 text-rose-700 border-rose-100";
  if (status === "CAUTION") return "bg-amber-50 text-amber-700 border-amber-100";
  return "bg-slate-100 text-slate-600 border-slate-200";
}

function AccessBadge({ hasAccess }: { hasAccess: boolean }) {
  return <Badge tone={hasAccess ? "success" : "warning"}>{hasAccess ? "Access active" : "Needs code"}</Badge>;
}

function EmptyState({ title, text }: { title: string; text: string }) {
  return <SharedEmptyState title={title} description={text} />;
}

function SectionHeading({ eyebrow, title, aside }: { eyebrow: string; title: string; aside?: ReactNode }) {
  return (
    <div className="mb-5 flex items-start justify-between gap-4">
      <div>
        <p className="section-eyebrow">{eyebrow}</p>
        <h2 className="mt-1.5 text-lg font-semibold text-ink">{title}</h2>
      </div>
      {aside}
    </div>
  );
}

function selectableClass(selected: boolean) {
  return `w-full rounded-control border p-4 text-left transition-colors ${
    selected ? "border-brand-blue bg-blue-50/60" : "border-line bg-white hover:border-line-strong"
  }`;
}

export function UnlockCard({ isUnlocking, onUnlock }: { isUnlocking: boolean; onUnlock: (code: string) => Promise<boolean> }) {
  const [code, setCode] = useState("");

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (await onUnlock(code)) {
      setCode("");
      document.getElementById("patient-file")?.scrollIntoView({ behavior: "smooth", block: "start" });
    }
  }

  return (
    <Card id="unlock">
      <SectionHeading eyebrow="Patient consent" title="Unlock a patient file" />
      <form className="space-y-3" onSubmit={handleSubmit}>
        <p className="text-sm leading-6 text-slate-500">
          Ask the patient to generate a one-time code on their dashboard (Doctor Access) and enter it here. Access lasts for
          this consultation; end it when you are done.
        </p>
        <label htmlFor="patient-access-code" className="block text-sm font-medium text-slate-700">
          One-time code
        </label>
        <input
          id="patient-access-code"
          value={code}
          onChange={(event) => setCode(event.target.value)}
          inputMode="numeric"
          autoComplete="off"
          placeholder="6-digit code"
          className="form-field"
        />
        <Button type="submit" loading={isUnlocking} icon={<KeyRound className="h-4 w-4" />} className="w-full">
          {isUnlocking ? "Unlocking..." : "Unlock file"}
        </Button>
      </form>
    </Card>
  );
}

export function ActivePatientsCard({
  patients,
  selectedPatientId,
  onSelect,
}: {
  patients: Patient[];
  selectedPatientId: number | null;
  onSelect: (patientId: number) => void;
}) {
  return (
    <Card>
      <SectionHeading eyebrow="Active consultations" title="Patients with access" aside={<span className="soft-badge">{patients.length} active</span>} />
      {patients.length > 0 ? (
        <div className="space-y-3">
          {patients.map((patient) => (
            <button key={patient.id} type="button" onClick={() => onSelect(patient.id)} className={selectableClass(patient.id === selectedPatientId)}>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-ink">{patient.name}</p>
                <span className="text-xs font-medium text-slate-500">
                  {patient.recordCount} report{patient.recordCount === 1 ? "" : "s"}
                </span>
              </div>
              <p className="mt-1 text-xs font-semibold text-slate-500">Access until {formatDateTime(patient.accessExpiresAt)}</p>
            </button>
          ))}
        </div>
      ) : (
        <EmptyState title="No active consultations" text="Patients appear here after you unlock their file with a one-time code." />
      )}
    </Card>
  );
}

export function AppointmentsCard({
  appointments,
  selectedPatientId,
  onSelect,
}: {
  appointments: DoctorOverview["appointments"];
  selectedPatientId: number | null;
  onSelect: (patientId: number) => void;
}) {
  return (
    <Card id="appointments">
      <SectionHeading eyebrow="Schedule" title="Appointments" />
      {appointments.length > 0 ? (
        <div className="space-y-3">
          {appointments.map((appointment) => (
            <button
              key={appointment.id}
              type="button"
              onClick={() => onSelect(appointment.userId)}
              className={selectableClass(appointment.userId === selectedPatientId)}
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-ink">{appointment.patientName}</p>
                <AccessBadge hasAccess={appointment.hasDashboardAccess} />
              </div>
              <p className="mt-1 text-sm font-semibold text-slate-600">{formatDateTime(appointment.date)}</p>
              {appointment.patientEmail ? <p className="mt-1 text-xs text-slate-500">{appointment.patientEmail}</p> : null}
            </button>
          ))}
        </div>
      ) : (
        <EmptyState title="No appointments yet" text="Appointments that patients book with you will appear here." />
      )}
    </Card>
  );
}

export function PatientFileCard({
  patient,
  selectedWithoutAccess,
  reports,
  medicines,
  isEnding,
  onEndAccess,
}: {
  patient: Patient | null;
  /** Name of a patient picked from a list who has not granted access. */
  selectedWithoutAccess: string | null;
  reports: Report[];
  medicines: Medicine[];
  isEnding: boolean;
  onEndAccess: (patientId: number) => void;
}) {
  return (
    <Card id="patient-file">
      <SectionHeading
        eyebrow="Patient file"
        title={patient ? patient.name : (selectedWithoutAccess ?? "No patient open")}
        aside={
          patient ? (
            <Button variant="danger" size="sm" loading={isEnding} onClick={() => onEndAccess(patient.id)}>
              {isEnding ? "Ending..." : "End consultation"}
            </Button>
          ) : null
        }
      />

      {patient ? (
        <div className="space-y-5">
          <p className="text-xs font-semibold text-slate-500">
            {patient.email ? `${patient.email} · ` : ""}Access until {formatDateTime(patient.accessExpiresAt)}
          </p>

          <div>
            <p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              <Activity className="h-3.5 w-3.5" /> Latest vitals
            </p>
            {patient.latestVitals ? (
              <div className="grid gap-3 sm:grid-cols-3">
                <VitalTile label="Blood pressure" value={patient.latestVitals.bloodPressure} />
                <VitalTile label="Sugar level" value={patient.latestVitals.sugarLevel} />
                <VitalTile label="Recorded" value={formatDateTime(patient.latestVitals.createdAt)} small />
              </div>
            ) : (
              <p className="text-sm text-slate-500">The patient has not recorded any vitals.</p>
            )}
          </div>

          <div>
            <p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              <FileSearch className="h-3.5 w-3.5" /> Reports ({reports.length})
            </p>
            {reports.length > 0 ? (
              <div className="space-y-3">
                {reports.slice(0, 5).map((report) => (
                  <article key={report.id} className="rounded-control border border-line bg-white p-4">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-sm font-semibold text-ink">{report.title}</p>
                      <span className={`rounded-full border px-2.5 py-0.5 text-[11px] font-semibold ${validationTone(report.validationStatus)}`}>
                        {validationLabel(report.validationStatus)}
                      </span>
                    </div>
                    <p className="mt-1 text-xs font-semibold text-slate-500">
                      {report.department} · {formatDateTime(report.createdAt)} · OCR {formatStatus(report.scanStatus)}
                    </p>
                    {report.summary || report.extractedText ? (
                      <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">{report.summary || report.extractedText}</p>
                    ) : (
                      <p className="mt-2 text-sm text-slate-500">No text was extracted from this report.</p>
                    )}
                  </article>
                ))}
                <p className="text-[11px] leading-5 text-slate-400">Summaries are AI-generated and advisory only. Verify against the original report.</p>
              </div>
            ) : (
              <p className="text-sm text-slate-500">The patient has not uploaded any reports.</p>
            )}
          </div>

          <div>
            <p className="mb-2 flex items-center gap-2 text-xs font-semibold uppercase tracking-wider text-slate-500">
              <Pill className="h-3.5 w-3.5" /> Medicines ({medicines.length})
            </p>
            {medicines.length > 0 ? (
              <div className="space-y-2">
                {medicines.map((medicine) => (
                  <div key={medicine.id} className="flex flex-wrap items-center justify-between gap-2 rounded-control border border-line bg-surface-soft px-4 py-3">
                    <p className="text-sm font-semibold text-ink">
                      {medicine.name}
                      {medicine.dosage ? <span className="font-semibold text-slate-500"> · {medicine.dosage}</span> : null}
                    </p>
                    <span className="text-xs font-medium capitalize text-slate-500">{formatStatus(medicine.status)}</span>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-slate-500">The patient has not added any medicines.</p>
            )}
          </div>
        </div>
      ) : selectedWithoutAccess ? (
        <EmptyState
          title="No access to this patient's records"
          text={`Ask ${selectedWithoutAccess} to generate a one-time code on their dashboard and enter it under Unlock a patient file.`}
        />
      ) : (
        <EmptyState
          title="No patient file open"
          text="Enter a one-time code from a patient to open their vitals, reports and medicines for this consultation."
        />
      )}
    </Card>
  );
}

function VitalTile({ label, value, small = false }: { label: string; value: string; small?: boolean }) {
  return (
    <div className="rounded-control border border-line bg-surface-soft p-3">
      <p className="text-xs font-medium text-slate-500">{label}</p>
      <p className={small ? "mt-1 text-sm font-semibold text-ink" : "mt-1 text-lg font-semibold text-ink"}>{value}</p>
    </div>
  );
}

export function EmergencyCard({ bookings }: { bookings: DoctorOverview["emergencyBookings"] }) {
  return (
    <Card id="emergency">
      <SectionHeading eyebrow="Urgent" title="Emergency visits" />
      {bookings.length > 0 ? (
        <div className="grid gap-3 lg:grid-cols-2">
          {bookings.map((booking) => (
            <article key={booking.id} className="rounded-control border border-line bg-surface-soft p-4">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="text-sm font-semibold text-ink">{booking.patientName}</p>
                <div className="flex items-center gap-2">
                  <span className="rounded-full bg-white px-3 py-1 text-xs font-medium capitalize text-slate-600">{formatStatus(booking.status)}</span>
                  <AccessBadge hasAccess={booking.hasDashboardAccess} />
                </div>
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-600">{booking.symptoms}</p>
              <p className="mt-1 text-xs font-semibold text-slate-500">
                {booking.phone} · {booking.address} · Requested {formatDateTime(booking.createdAt)}
              </p>
            </article>
          ))}
        </div>
      ) : (
        <EmptyState title="No emergency visits" text="Emergency visit requests assigned to you will appear here." />
      )}
    </Card>
  );
}
