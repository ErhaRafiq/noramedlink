"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { CalendarDays, FileSearch, KeyRound, LayoutDashboard, LogOut, ShieldAlert, Siren, Stethoscope, Users } from "lucide-react";

import { Sidebar, StatCard } from "@/components/ui/saas-shell";
import { clearSession } from "@/lib/auth";
import { useAuthGuard } from "@/hooks/use-auth-guard";
import { useDoctorDashboard } from "@/hooks/doctor/use-doctor-dashboard";
import { ActivePatientsCard, AppointmentsCard, EmergencyCard, PatientFileCard, UnlockCard } from "./doctor/sections";

const sidebarItems = [
  { href: "/dashboard/doctor", label: "Dashboard", icon: LayoutDashboard, active: true },
  { href: "/dashboard/doctor#unlock", label: "Unlock Patient", icon: KeyRound },
  { href: "/dashboard/doctor#appointments", label: "Appointments", icon: CalendarDays },
  { href: "/dashboard/doctor#patient-file", label: "Patient File", icon: FileSearch },
  { href: "/dashboard/doctor#emergency", label: "Emergency Visits", icon: Siren },
];

const VERIFIED_STATUSES = ["approved", "verified"];

export function DoctorDashboard() {
  const router = useRouter();
  const auth = useAuthGuard("doctor");
  const dashboard = useDoctorDashboard(auth.status === "ready" ? auth.token : null);
  const { profile, overview, notice, selectedPatientId } = dashboard;

  function logout() {
    clearSession();
    router.replace("/login");
  }

  if (auth.status === "error") {
    return (
      <main className="app-shell grid min-h-screen place-items-center px-4">
        <p role="alert" className="glass-card max-w-md p-8 text-center text-sm font-semibold text-rose-700">
          {auth.message}
        </p>
      </main>
    );
  }

  if (auth.status !== "ready" || dashboard.isLoading) {
    return (
      <main className="app-shell grid min-h-screen place-items-center px-4">
        <div role="status" className="glass-card p-8 text-sm font-bold text-slate-500">
          Loading doctor workspace...
        </div>
      </main>
    );
  }

  const doctorName = (profile?.full_name ?? overview?.doctor.name ?? "").replace(/^dr\.?\s*/i, "");
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
    <main className="app-shell min-h-screen">
      <div className="mx-auto grid max-w-[1520px] gap-6 px-4 py-5 lg:grid-cols-[286px_1fr] lg:px-6">
        <Sidebar
          items={sidebarItems}
          userName={doctorName ? `Dr. ${doctorName}` : "Doctor"}
          userMeta={profile?.email ?? overview?.doctor.email}
          action={
            <button
              type="button"
              onClick={logout}
              className="flex w-full items-center gap-3 rounded-[16px] px-4 py-3 text-left text-sm font-bold text-red-100 transition hover:bg-red-400/10"
            >
              <LogOut className="h-4 w-4" />
              Logout
            </button>
          }
        />

        <section className="space-y-6">
          <header className="dashboard-topbar">
            <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
              <div>
                <p className="section-eyebrow">Doctor dashboard</p>
                <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">
                  {doctorName ? `Welcome back, Dr. ${doctorName}` : "Welcome back"}
                </h1>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
                  {profileLine || "Appointments, patient files opened by one-time code, and emergency visits."}
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <Link href="/dashboard/doctor#unlock" className="gradient-button gap-2 px-4 py-3">
                  <KeyRound className="h-4 w-4" />
                  Unlock Patient
                </Link>
                <Link href="/doctors" className="secondary-button gap-2 px-4 py-3">
                  <Stethoscope className="h-4 w-4" />
                  Doctor Directory
                </Link>
              </div>
            </div>
          </header>

          {profile && !isVerified ? (
            <div className="flex items-start gap-3 rounded-2xl border border-amber-200 bg-amber-50 px-5 py-4 text-sm text-amber-800">
              <ShieldAlert className="mt-0.5 h-4 w-4 flex-shrink-0" />
              <p>
                <span className="font-black">{verification === "rejected" ? "Verification rejected." : "Verification pending."}</span>{" "}
                Patients cannot find or book you until an admin approves your account.
              </p>
            </div>
          ) : null}

          {notice ? (
            <p
              role={notice.tone === "error" ? "alert" : "status"}
              className={`rounded-2xl border px-5 py-4 text-sm font-semibold ${
                notice.tone === "success" ? "border-emerald-100 bg-emerald-50 text-emerald-700" : "border-red-100 bg-red-50 text-red-700"
              }`}
            >
              {notice.text}
            </p>
          ) : null}

          {overview ? (
            <>
              <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard label="Appointments" value={overview.stats.appointments} detail="recent, booked with you" icon={CalendarDays} />
                <StatCard label="Patients with access" value={overview.stats.patients} detail="unlocked by one-time code" icon={Users} />
                <StatCard label="Emergency visits" value={overview.stats.emergencyBookings} detail="recent, assigned to you" icon={Siren} />
                <StatCard label="Shared reports" value={overview.stats.medicalRecords} detail="from patients with access" icon={FileSearch} />
              </section>

              <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
                <UnlockCard isUnlocking={dashboard.isUnlocking} onUnlock={dashboard.unlock} />
                <ActivePatientsCard patients={patients} selectedPatientId={selectedPatientId} onSelect={dashboard.selectPatient} />
              </section>

              <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
                <AppointmentsCard appointments={overview.appointments} selectedPatientId={selectedPatientId} onSelect={dashboard.selectPatient} />
                <PatientFileCard
                  patient={activePatient}
                  selectedWithoutAccess={selectedWithoutAccess}
                  reports={activePatient ? overview.medicalRecords.filter((r) => r.userId === activePatient.id) : []}
                  medicines={activePatient ? overview.medications.filter((m) => m.userId === activePatient.id) : []}
                  isEnding={activePatient !== null && dashboard.endingPatientId === activePatient.id}
                  onEndAccess={(id) => void dashboard.endAccess(id)}
                />
              </section>

              <EmergencyCard bookings={overview.emergencyBookings} />
            </>
          ) : null}
        </section>
      </div>
    </main>
  );
}
