"use client";

import { useRouter } from "next/navigation";
import { CalendarDays, ClipboardList, FileSearch, KeyRound, LayoutDashboard, Pill, Siren, Stethoscope, Users } from "lucide-react";

import { DashboardShell, type DashboardNavItem } from "@/components/layout/DashboardShell";
import { Alert } from "@/components/ui/alert";
import { ButtonLink } from "@/components/ui/button";
import { SkeletonCard } from "@/components/ui/skeleton";
import { ErrorState, PageLoader } from "@/components/ui/spinner";
import { StatCard, StatCardSkeleton } from "@/components/ui/stat-card";
import { signOut as endSession } from "@/lib/auth";
import { useAuthGuard } from "@/hooks/use-auth-guard";
import { useDoctorDashboard } from "@/hooks/doctor/use-doctor-dashboard";
import { ClinicalSummaryCard } from "./doctor/clinical-summary/ClinicalSummaryCard";
import { PrescribeCard } from "./doctor/prescribe/PrescribeCard";
import { ActivePatientsCard, AppointmentsCard, EmergencyCard, PatientFileCard, UnlockCard } from "./doctor/sections";

const NAV: DashboardNavItem[] = [
  { id: "summary", label: "Summary", icon: LayoutDashboard },
  { id: "unlock", label: "Unlock a file", icon: KeyRound },
  { id: "appointments", label: "Appointments", icon: CalendarDays },
  { id: "patient-file", label: "Patient file", icon: FileSearch },
  { id: "clinical-summary", label: "Clinical summary", icon: ClipboardList },
  { id: "prescribe", label: "Prescribe", icon: Pill },
  { id: "emergency", label: "Emergency visits", icon: Siren },
];

const VERIFIED_STATUSES = ["approved", "verified"];

export function DoctorDashboard() {
  const router = useRouter();
  const auth = useAuthGuard("doctor");
  const dashboard = useDoctorDashboard(auth.status === "ready");
  const { profile, overview, notice, selectedPatientId } = dashboard;

  function signOut() {
    void endSession();
    router.replace("/login");
  }

  if (auth.status === "error") return <ErrorState message={auth.message} onRetry={() => window.location.reload()} />;
  if (auth.status !== "ready") return <PageLoader message="Checking your session..." />;

  const doctorName = (profile?.full_name ?? overview?.doctor.name ?? auth.user.full_name ?? "").replace(/^dr\.?\s*/i, "");
  const verification = (profile?.verification_status ?? "").toLowerCase();
  const isVerified = VERIFIED_STATUSES.includes(verification);
  const profileLine = [profile?.specialization, profile?.hospital_name].filter(Boolean).join(" · ");

  const patients = overview?.patients ?? [];
  const activePatient = patients.find((p) => p.id === selectedPatientId) ?? null;
  // A patient picked from the appointment or emergency list without an access grant.
  const selectedWithoutAccess =
    !activePatient && selectedPatientId !== null
      ? (overview?.appointments.find((a) => a.userId === selectedPatientId)?.patientName ??
        overview?.emergencyBookings.find((b) => b.userId === selectedPatientId)?.patientName ??
        null)
      : null;

  return (
    <DashboardShell nav={NAV} userName={doctorName ? `Dr. ${doctorName}` : "Doctor"} userMeta={profile?.email ?? auth.user.email} onSignOut={signOut}>
      <header id="summary" className="flex scroll-mt-24 flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="section-eyebrow">Doctor dashboard</p>
          <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink">{doctorName ? `Welcome back, Dr. ${doctorName}` : "Welcome back"}</h1>
          <p className="mt-1 text-sm text-ink-muted">{profileLine || "Appointments, patient files opened by one-time code, and emergency visits."}</p>
        </div>
        <ButtonLink href="/doctors" variant="secondary" size="sm" icon={<Stethoscope className="h-4 w-4" />}>
          Doctor directory
        </ButtonLink>
      </header>

      {profile && !isVerified ? (
        <Alert tone="warning" title={verification === "rejected" ? "Verification rejected" : "Verification pending"}>
          Patients cannot find or book you until an administrator approves your registration.
        </Alert>
      ) : null}

      {notice ? <Alert tone={notice.tone === "success" ? "success" : "error"}>{notice.text}</Alert> : null}

      {dashboard.isLoading ? (
        <div role="status" aria-label="Loading the doctor dashboard" className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              <StatCardSkeleton key={i} />
            ))}
          </div>
          <div className="grid gap-6 xl:grid-cols-2">
            <SkeletonCard lines={4} />
            <SkeletonCard lines={4} />
          </div>
        </div>
      ) : overview ? (
        <>
          <section aria-label="Summary" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Appointments" value={overview.stats.appointments} detail="recent, booked with you" icon={CalendarDays} />
            <StatCard label="Patients with access" value={overview.stats.patients} detail="unlocked by one-time code" icon={Users} tint="bg-teal-50 text-teal-700" />
            <StatCard label="Emergency visits" value={overview.stats.emergencyBookings} detail="recent, assigned to you" icon={Siren} tint="bg-rose-50 text-rose-600" />
            <StatCard label="Shared reports" value={overview.stats.medicalRecords} detail="from patients with access" icon={FileSearch} tint="bg-violet-50 text-violet-700" />
          </section>

          <div className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
            <UnlockCard isUnlocking={dashboard.isUnlocking} onUnlock={dashboard.unlock} />
            <ActivePatientsCard patients={patients} selectedPatientId={selectedPatientId} onSelect={dashboard.selectPatient} />
          </div>

          <div className="grid items-start gap-6 xl:grid-cols-[0.9fr_1.1fr]">
            <AppointmentsCard appointments={overview.appointments} selectedPatientId={selectedPatientId} onSelect={dashboard.selectPatient} />
            <PatientFileCard
              patient={activePatient}
              selectedWithoutAccess={selectedWithoutAccess}
              reports={activePatient ? overview.medicalRecords.filter((r) => r.userId === activePatient.id) : []}
              medicines={activePatient ? overview.medications.filter((m) => m.userId === activePatient.id) : []}
              isEnding={activePatient !== null && dashboard.endingPatientId === activePatient.id}
              onEndAccess={(id) => void dashboard.endAccess(id)}
            />
          </div>

          {activePatient && auth.status === "ready" ? (
            <>
              <ClinicalSummaryCard key={activePatient.id} patientId={activePatient.id} patientName={activePatient.name} />
              <PrescribeCard
                key={`rx-${activePatient.id}`}
                patientId={activePatient.id}
                patientName={activePatient.name}
                doctorId={auth.user.id}
                doctorName={auth.user.full_name}
              />
            </>
          ) : null}

          <EmergencyCard bookings={overview.emergencyBookings} />

        </>
      ) : null}
    </DashboardShell>
  );
}
