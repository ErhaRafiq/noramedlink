"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";
import type { ReactNode } from "react";
import {
  Activity,
  CalendarDays,
  FileSearch,
  KeyRound,
  LayoutDashboard,
  Loader2,
  LogOut,
  Pill,
  ShieldAlert,
  Siren,
  Stethoscope,
  Users,
} from "lucide-react";

import { DashboardCard, Sidebar, StatCard } from "@/components/ui/saas-shell";
import { api } from "@/lib/api";
import { clearSession, dashboardPathForRole, getSession, updateStoredUser } from "@/lib/auth";
import { validationLabel } from "@/lib/patient-dashboard";
import type { DoctorDashboard as DoctorProfileResponse, DoctorOverview } from "@/lib/types";

type DoctorProfile = DoctorProfileResponse["doctor"];
type Notice = { tone: "error" | "success"; text: string } | null;

const sidebarItems = [
  { href: "/dashboard/doctor", label: "Dashboard", icon: LayoutDashboard, active: true },
  { href: "/dashboard/doctor#unlock", label: "Unlock Patient", icon: KeyRound },
  { href: "/dashboard/doctor#appointments", label: "Appointments", icon: CalendarDays },
  { href: "/dashboard/doctor#patient-file", label: "Patient File", icon: FileSearch },
  { href: "/dashboard/doctor#emergency", label: "Emergency Visits", icon: Siren },
];

const VERIFIED_STATUSES = ["approved", "verified"];

function formatDateTime(value: string | null | undefined) {
  if (!value) return "Not available";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function formatStatus(value: string) {
  return value.replaceAll("_", " ").toLowerCase();
}

function validationTone(status: string | null) {
  if (status === "HIGH_RISK") return "bg-rose-50 text-rose-700 border-rose-100";
  if (status === "CAUTION") return "bg-amber-50 text-amber-700 border-amber-100";
  if (status === "SAFE") return "bg-emerald-50 text-emerald-700 border-emerald-100";
  return "bg-slate-100 text-slate-600 border-slate-200";
}

function AccessBadge({ hasAccess }: { hasAccess: boolean }) {
  return (
    <span
      className={`rounded-full px-3 py-1 text-xs font-bold ${
        hasAccess ? "bg-emerald-100 text-emerald-700" : "bg-amber-100 text-amber-700"
      }`}
    >
      {hasAccess ? "Access active" : "Needs code"}
    </span>
  );
}

function EmptyState({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-2xl border border-dashed border-[#DCE8F5] bg-[#F8FBFF] p-5 text-center">
      <p className="text-sm font-black text-slate-950">{title}</p>
      <p className="mt-1 text-sm leading-6 text-slate-500">{text}</p>
    </div>
  );
}

function SectionHeading({ eyebrow, title, aside }: { eyebrow: string; title: string; aside?: ReactNode }) {
  return (
    <div className="mb-5 flex items-start justify-between gap-4">
      <div>
        <p className="section-eyebrow">{eyebrow}</p>
        <h2 className="mt-2 text-2xl font-black text-slate-950">{title}</h2>
      </div>
      {aside}
    </div>
  );
}

export function DoctorDashboard() {
  const router = useRouter();
  const [profile, setProfile] = useState<DoctorProfile | null>(null);
  const [overview, setOverview] = useState<DoctorOverview | null>(null);
  const [notice, setNotice] = useState<Notice>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [accessCode, setAccessCode] = useState("");
  const [isUnlocking, setIsUnlocking] = useState(false);
  const [endingPatientId, setEndingPatientId] = useState<number | null>(null);
  const [selectedPatientId, setSelectedPatientId] = useState<number | null>(null);

  function applyOverview(data: DoctorOverview, preferPatientId?: number | null) {
    setOverview(data);
    setSelectedPatientId((current) => {
      const wanted = preferPatientId ?? current;
      if (wanted !== null && wanted !== undefined) return wanted;
      return data.patients[0]?.id ?? null;
    });
  }

  useEffect(() => {
    const session = getSession();
    if (!session) {
      router.replace("/login");
      return;
    }
    const token = session.token;

    void (async () => {
      try {
        const user = await api.me(token);
        if (user.role !== "doctor") {
          router.replace(dashboardPathForRole(user.role));
          return;
        }
        updateStoredUser(user);
      } catch {
        clearSession();
        router.replace("/login");
        return;
      }

      try {
        const [doctor, data] = await Promise.all([api.doctorDashboard(token), api.doctorOverview(token)]);
        setProfile(doctor.doctor);
        applyOverview(data);
      } catch (error) {
        setNotice({ tone: "error", text: error instanceof Error ? error.message : "Unable to load the doctor dashboard." });
      } finally {
        setIsLoading(false);
      }
    })();
  }, [router]);

  async function reloadOverview(preferPatientId?: number | null) {
    const session = getSession();
    if (!session) {
      router.replace("/login");
      return;
    }
    applyOverview(await api.doctorOverview(session.token), preferPatientId);
  }

  async function handleUnlock(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const code = accessCode.trim();
    if (!code) {
      setNotice({ tone: "error", text: "Enter the one-time code the patient shared with you." });
      return;
    }
    const session = getSession();
    if (!session) {
      router.replace("/login");
      return;
    }
    setIsUnlocking(true);
    setNotice(null);
    try {
      const data = await api.unlockPatientDashboard(session.token, code);
      setAccessCode("");
      setNotice({ tone: "success", text: data.message });
      await reloadOverview(data.patient.id);
      document.getElementById("patient-file")?.scrollIntoView({ behavior: "smooth", block: "start" });
    } catch (error) {
      setNotice({ tone: "error", text: error instanceof Error ? error.message : "Unable to unlock the patient file." });
    } finally {
      setIsUnlocking(false);
    }
  }

  async function handleEndAccess(patientId: number) {
    const session = getSession();
    if (!session) {
      router.replace("/login");
      return;
    }
    setEndingPatientId(patientId);
    setNotice(null);
    try {
      const data = await api.endPatientDashboardAccess(session.token, patientId);
      setNotice({ tone: "success", text: data.message });
      setSelectedPatientId(null);
      await reloadOverview(null);
    } catch (error) {
      setNotice({ tone: "error", text: error instanceof Error ? error.message : "Unable to end the consultation." });
    } finally {
      setEndingPatientId(null);
    }
  }

  function logout() {
    clearSession();
    router.replace("/login");
  }

  if (isLoading) {
    return (
      <main className="app-shell grid min-h-screen place-items-center px-4">
        <div className="glass-card p-8 text-sm font-bold text-slate-500">Loading doctor workspace...</div>
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
      ? overview?.appointments.find((a) => a.userId === selectedPatientId)?.patientName ??
        overview?.emergencyBookings.find((b) => b.userId === selectedPatientId)?.patientName ??
        null
      : null;
  const patientReports = activePatient
    ? (overview?.medicalRecords ?? []).filter((r) => r.userId === activePatient.id)
    : [];
  const patientMedicines = activePatient
    ? (overview?.medications ?? []).filter((m) => m.userId === activePatient.id)
    : [];

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
                <span className="font-black">
                  {verification === "rejected" ? "Verification rejected." : "Verification pending."}
                </span>{" "}
                Patients cannot find or book you until an admin approves your account.
              </p>
            </div>
          ) : null}

          {notice ? (
            <p
              className={`rounded-2xl border px-5 py-4 text-sm font-semibold ${
                notice.tone === "success"
                  ? "border-emerald-100 bg-emerald-50 text-emerald-700"
                  : "border-red-100 bg-red-50 text-red-700"
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
                <DashboardCard id="unlock">
                  <SectionHeading eyebrow="Patient consent" title="Unlock a patient file" />
                  <form className="space-y-3" onSubmit={handleUnlock}>
                    <p className="text-sm leading-6 text-slate-500">
                      Ask the patient to generate a one-time code on their dashboard (Doctor Access) and enter it here.
                      Access lasts for this consultation; end it when you are done.
                    </p>
                    <label htmlFor="patient-access-code" className="block text-xs font-bold text-slate-600">
                      One-time code
                    </label>
                    <input
                      id="patient-access-code"
                      value={accessCode}
                      onChange={(event) => setAccessCode(event.target.value)}
                      inputMode="numeric"
                      autoComplete="off"
                      placeholder="6-digit code"
                      className="form-field"
                    />
                    <button type="submit" disabled={isUnlocking} className="primary-button w-full">
                      {isUnlocking ? <Loader2 className="h-4 w-4 animate-spin" /> : <KeyRound className="h-4 w-4" />}
                      {isUnlocking ? "Unlocking..." : "Unlock"}
                    </button>
                  </form>
                </DashboardCard>

                <DashboardCard>
                  <SectionHeading
                    eyebrow="Active consultations"
                    title="Patients with access"
                    aside={<span className="soft-badge">{patients.length} active</span>}
                  />
                  {patients.length > 0 ? (
                    <div className="space-y-3">
                      {patients.map((patient) => (
                        <button
                          key={patient.id}
                          type="button"
                          onClick={() => setSelectedPatientId(patient.id)}
                          className={`w-full rounded-2xl border p-4 text-left transition ${
                            patient.id === selectedPatientId
                              ? "border-teal-300 bg-teal-50"
                              : "border-[#DCE8F5] bg-[#F8FBFF] hover:border-blue-200"
                          }`}
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="text-sm font-black text-slate-950">{patient.name}</p>
                            <span className="text-xs font-bold text-slate-500">
                              {patient.recordCount} report{patient.recordCount === 1 ? "" : "s"}
                            </span>
                          </div>
                          <p className="mt-1 text-xs font-semibold text-slate-500">
                            Access until {formatDateTime(patient.accessExpiresAt)}
                          </p>
                        </button>
                      ))}
                    </div>
                  ) : (
                    <EmptyState
                      title="No active consultations"
                      text="Patients appear here after you unlock their file with a one-time code."
                    />
                  )}
                </DashboardCard>
              </section>

              <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
                <DashboardCard id="appointments">
                  <SectionHeading eyebrow="Schedule" title="Appointments" />
                  {overview.appointments.length > 0 ? (
                    <div className="space-y-3">
                      {overview.appointments.map((appointment) => (
                        <button
                          key={appointment.id}
                          type="button"
                          onClick={() => setSelectedPatientId(appointment.userId)}
                          className={`w-full rounded-2xl border p-4 text-left transition ${
                            appointment.userId === selectedPatientId
                              ? "border-teal-300 bg-teal-50"
                              : "border-[#DCE8F5] bg-[#F8FBFF] hover:border-blue-200"
                          }`}
                        >
                          <div className="flex flex-wrap items-center justify-between gap-2">
                            <p className="text-sm font-black text-slate-950">{appointment.patientName}</p>
                            <AccessBadge hasAccess={appointment.hasDashboardAccess} />
                          </div>
                          <p className="mt-1 text-sm font-semibold text-slate-600">{formatDateTime(appointment.date)}</p>
                          {appointment.patientEmail ? (
                            <p className="mt-1 text-xs text-slate-500">{appointment.patientEmail}</p>
                          ) : null}
                        </button>
                      ))}
                    </div>
                  ) : (
                    <EmptyState title="No appointments yet" text="Appointments that patients book with you will appear here." />
                  )}
                </DashboardCard>

                <DashboardCard id="patient-file">
                  <SectionHeading
                    eyebrow="Patient file"
                    title={activePatient ? activePatient.name : selectedWithoutAccess ?? "No patient open"}
                    aside={
                      activePatient ? (
                        <button
                          type="button"
                          onClick={() => void handleEndAccess(activePatient.id)}
                          disabled={endingPatientId === activePatient.id}
                          className="rounded-xl border border-rose-200 bg-rose-50 px-4 py-2 text-sm font-bold text-rose-700 transition hover:bg-rose-100 disabled:opacity-60"
                        >
                          {endingPatientId === activePatient.id ? "Ending..." : "End Consultation"}
                        </button>
                      ) : null
                    }
                  />

                  {activePatient ? (
                    <div className="space-y-5">
                      <p className="text-xs font-semibold text-slate-500">
                        {activePatient.email ? `${activePatient.email} · ` : ""}Access until{" "}
                        {formatDateTime(activePatient.accessExpiresAt)}
                      </p>

                      <div>
                        <p className="mb-2 flex items-center gap-2 text-xs font-black uppercase tracking-wider text-slate-500">
                          <Activity className="h-3.5 w-3.5" /> Latest vitals
                        </p>
                        {activePatient.latestVitals ? (
                          <div className="grid gap-3 sm:grid-cols-3">
                            <div className="rounded-2xl border border-[#DCE8F5] bg-[#F8FBFF] p-3">
                              <p className="text-xs font-bold text-slate-500">Blood pressure</p>
                              <p className="mt-1 text-lg font-black text-slate-950">{activePatient.latestVitals.bloodPressure}</p>
                            </div>
                            <div className="rounded-2xl border border-[#DCE8F5] bg-[#F8FBFF] p-3">
                              <p className="text-xs font-bold text-slate-500">Sugar level</p>
                              <p className="mt-1 text-lg font-black text-slate-950">{activePatient.latestVitals.sugarLevel}</p>
                            </div>
                            <div className="rounded-2xl border border-[#DCE8F5] bg-[#F8FBFF] p-3">
                              <p className="text-xs font-bold text-slate-500">Recorded</p>
                              <p className="mt-1 text-sm font-black text-slate-950">
                                {formatDateTime(activePatient.latestVitals.createdAt)}
                              </p>
                            </div>
                          </div>
                        ) : (
                          <p className="text-sm text-slate-500">The patient has not recorded any vitals.</p>
                        )}
                      </div>

                      <div>
                        <p className="mb-2 flex items-center gap-2 text-xs font-black uppercase tracking-wider text-slate-500">
                          <FileSearch className="h-3.5 w-3.5" /> Reports ({patientReports.length})
                        </p>
                        {patientReports.length > 0 ? (
                          <div className="space-y-3">
                            {patientReports.slice(0, 5).map((report) => (
                              <article key={report.id} className="rounded-2xl border border-[#DCE8F5] bg-white p-4">
                                <div className="flex flex-wrap items-center justify-between gap-2">
                                  <p className="text-sm font-black text-slate-950">{report.title}</p>
                                  <span
                                    className={`rounded-full border px-2.5 py-0.5 text-[11px] font-black ${validationTone(report.validationStatus)}`}
                                  >
                                    {validationLabel(report.validationStatus)}
                                  </span>
                                </div>
                                <p className="mt-1 text-xs font-semibold text-slate-500">
                                  {report.department} · {formatDateTime(report.createdAt)} · OCR {formatStatus(report.scanStatus)}
                                </p>
                                {report.summary ? (
                                  <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">{report.summary}</p>
                                ) : report.extractedText ? (
                                  <p className="mt-2 line-clamp-3 text-sm leading-6 text-slate-600">{report.extractedText}</p>
                                ) : (
                                  <p className="mt-2 text-sm text-slate-500">No text was extracted from this report.</p>
                                )}
                              </article>
                            ))}
                            <p className="text-[11px] leading-5 text-slate-400">
                              Summaries are AI-generated and advisory only. Verify against the original report.
                            </p>
                          </div>
                        ) : (
                          <p className="text-sm text-slate-500">The patient has not uploaded any reports.</p>
                        )}
                      </div>

                      <div>
                        <p className="mb-2 flex items-center gap-2 text-xs font-black uppercase tracking-wider text-slate-500">
                          <Pill className="h-3.5 w-3.5" /> Medicines ({patientMedicines.length})
                        </p>
                        {patientMedicines.length > 0 ? (
                          <div className="space-y-2">
                            {patientMedicines.map((medicine) => (
                              <div
                                key={medicine.id}
                                className="flex flex-wrap items-center justify-between gap-2 rounded-2xl border border-[#DCE8F5] bg-[#F8FBFF] px-4 py-3"
                              >
                                <p className="text-sm font-black text-slate-950">
                                  {medicine.name}
                                  {medicine.dosage ? <span className="font-semibold text-slate-500"> · {medicine.dosage}</span> : null}
                                </p>
                                <span className="text-xs font-bold capitalize text-slate-500">{formatStatus(medicine.status)}</span>
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
                </DashboardCard>
              </section>

              <DashboardCard id="emergency">
                <SectionHeading eyebrow="Urgent" title="Emergency visits" />
                {overview.emergencyBookings.length > 0 ? (
                  <div className="grid gap-3 lg:grid-cols-2">
                    {overview.emergencyBookings.map((booking) => (
                      <article key={booking.id} className="rounded-2xl border border-[#DCE8F5] bg-[#F8FBFF] p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="text-sm font-black text-slate-950">{booking.patientName}</p>
                          <div className="flex items-center gap-2">
                            <span className="rounded-full bg-white px-3 py-1 text-xs font-bold capitalize text-slate-600">
                              {formatStatus(booking.status)}
                            </span>
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
              </DashboardCard>
            </>
          ) : null}
        </section>
      </div>
    </main>
  );
}
