"use client";

import Link from "next/link";
import { FormEvent, useCallback, useEffect, useMemo, useState } from "react";

type DoctorOverview = {
  doctor: {
    id: number;
    name: string;
    email: string;
    role: string;
  };
  stats: {
    appointments: number;
    patients: number;
    emergencyBookings: number;
    medicalRecords: number;
    medications: number;
  };
  appointments: Array<{
    id: number;
    userId: number;
    patientName: string;
    patientEmail: string;
    hasDashboardAccess: boolean;
    accessExpiresAt: string | null;
    date: string;
  }>;
  emergencyBookings: Array<{
    id: number;
    patientName: string;
    phone: string;
    address: string;
    symptoms: string;
    status: string;
    estimatedMinutes: number;
    hasDashboardAccess: boolean;
    accessExpiresAt: string | null;
    createdAt: string;
  }>;
  patients: Array<{
    id: number;
    name: string;
    email: string;
    recordCount: number;
    appointmentCount: number;
    latestVitals: {
      bloodPressure: string;
      sugarLevel: string;
      createdAt: string;
    } | null;
    accessExpiresAt: string | null;
  }>;
  medicalRecords: Array<{
    id: number;
    userId: number;
    patientName: string;
    title: string;
    fileName: string;
    scanStatus: string;
    extractedText: string | null;
    createdAt: string;
  }>;
  medications: Array<{
    id: number;
    patientName: string;
    name: string;
    dosage: string;
    status: string;
    createdAt: string;
  }>;
};

function getStoredDoctorId() {
  if (typeof window === "undefined") {
    return "";
  }

  return localStorage.getItem("userId") ?? "";
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

function formatStatus(value: string) {
  return value.replaceAll("_", " ").toLowerCase();
}

function statusClass(value: string) {
  if (["COMPLETED", "TAKEN"].includes(value)) {
    return "border-emerald-200 bg-emerald-50 text-emerald-700";
  }

  if (["CANCELLED", "FAILED"].includes(value)) {
    return "border-rose-200 bg-rose-50 text-rose-700";
  }

  if (["DOCTOR_ASSIGNED", "ON_THE_WAY"].includes(value)) {
    return "border-blue-200 bg-blue-50 text-blue-700";
  }

  return "border-amber-200 bg-amber-50 text-amber-700";
}

function DoctorHeroIcon() {
  return (
    <div className="relative h-28 w-28 shrink-0">
      <div className="absolute inset-3 rounded-[2rem] bg-gradient-to-br from-[#2563EB] to-[#00BFA6] shadow-2xl shadow-blue-200" />
      <div className="absolute inset-0 -rotate-6 rounded-[2rem] border border-[#DCE8F5] bg-white/70 backdrop-blur" />
      <svg viewBox="0 0 120 120" className="absolute inset-0 h-full w-full drop-shadow-xl">
        <circle cx="60" cy="37" r="18" fill="#0f766e" />
        <path d="M28 101c3-24 17-38 32-38s29 14 32 38H28Z" fill="#14b8a6" />
        <path d="M44 30h32v11H44z" fill="#fff" />
        <path d="M55 20h10v31H55z" fill="#fff" />
        <path d="M41 70c4 11 10 17 19 17s15-6 19-17" fill="none" stroke="#fff" strokeLinecap="round" strokeWidth="6" />
        <circle cx="38" cy="86" r="8" fill="#60a5fa" />
        <circle cx="82" cy="86" r="8" fill="#c084fc" />
      </svg>
    </div>
  );
}

function EmptyState({ title, text }: { title: string; text: string }) {
  return (
    <div className="rounded-3xl border border-dashed border-slate-200 bg-white/70 p-6 text-center">
      <p className="font-black text-slate-950">{title}</p>
      <p className="mt-2 text-sm text-slate-500">{text}</p>
    </div>
  );
}

export default function DoctorDashboardPage() {
  const [doctorId] = useState(getStoredDoctorId);
  const [overview, setOverview] = useState<DoctorOverview | null>(null);
  const [statusMessage, setStatusMessage] = useState(() =>
    getStoredDoctorId() ? "" : "Login to open the doctor dashboard.",
  );
  const [patientAccessOtp, setPatientAccessOtp] = useState("");
  const [isLoading, setIsLoading] = useState(() => Boolean(getStoredDoctorId()));
  const [isUnlocking, setIsUnlocking] = useState(false);
  const [activePatientId, setActivePatientId] = useState<number | null>(null);

  const loadOverview = useCallback(async (activeDoctorId: string) => {
    setIsLoading(true);
    setStatusMessage("");

    try {
      const response = await fetch(`/api/doctor/overview?userId=${activeDoctorId}`);
      const data = (await response.json()) as DoctorOverview & { message?: string };

      if (!response.ok) {
        setOverview(null);
        setStatusMessage(data.message ?? "Doctor dashboard could not be loaded.");
        return;
      }

      setOverview(data);
      setActivePatientId((currentPatientId) => currentPatientId ?? data.patients[0]?.id ?? null);
    } catch {
      setOverview(null);
      setStatusMessage("Unable to load doctor dashboard.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    if (!doctorId) {
      return;
    }

    const timeoutId = window.setTimeout(() => {
      void loadOverview(doctorId);
    }, 0);

    return () => window.clearTimeout(timeoutId);
  }, [doctorId, loadOverview]);

  const activePatient = useMemo(
    () => overview?.patients.find((patient) => patient.id === activePatientId) ?? null,
    [activePatientId, overview],
  );

  const activePatientRecords = useMemo(
    () =>
      overview?.medicalRecords.filter(
        (record) => record.userId === activePatient?.id,
      ) ?? [],
    [activePatient, overview],
  );

  const unlockPatientDashboard = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setStatusMessage("");

    if (!patientAccessOtp.trim()) {
      setStatusMessage("Enter the one-time patient OTP.");
      return;
    }

    setIsUnlocking(true);

    try {
      const response = await fetch("/api/doctor/access/unlock", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          doctorId,
          patientAccessOtp,
        }),
      });
      const data = (await response.json()) as {
        message?: string;
        patient?: { id: number };
      };

      if (!response.ok) {
        setStatusMessage(data.message ?? "Unable to unlock patient dashboard.");
        return;
      }

      setStatusMessage(data.message ?? "Patient dashboard unlocked.");
      setPatientAccessOtp("");
      await loadOverview(doctorId);

      if (data.patient?.id) {
        setActivePatientId(data.patient.id);
      }
    } catch {
      setStatusMessage("Unable to unlock patient dashboard.");
    } finally {
      setIsUnlocking(false);
    }
  };

  const endConsultationSession = async (patientId: number) => {
    setStatusMessage("");

    try {
      const response = await fetch("/api/doctor/access/end", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doctorId, patientId }),
      });
      const data = (await response.json()) as { message?: string };

      if (!response.ok) {
        setStatusMessage(data.message ?? "Unable to end consultation session.");
        return;
      }

      setStatusMessage(data.message ?? "Consultation session ended.");
      setActivePatientId(null);
      await loadOverview(doctorId);
    } catch {
      setStatusMessage("Unable to end consultation session.");
    }
  };

  const statCards = overview
    ? [
        {
          label: "Appointments",
          value: overview.stats.appointments,
          detail: "linked to your profile",
          color: "from-blue-400 to-cyan-400",
        },
        {
          label: "Patients",
          value: overview.stats.patients,
          detail: "with care context",
          color: "from-emerald-400 to-teal-500",
        },
        {
          label: "Emergency",
          value: overview.stats.emergencyBookings,
          detail: "home visit requests",
          color: "from-rose-400 to-orange-400",
        },
        {
          label: "Records",
          value: overview.stats.medicalRecords,
          detail: "uploaded reports",
          color: "from-blue-500 to-teal-400",
        },
      ]
    : [];

  return (
    <main className="app-shell min-h-screen px-4 py-8 sm:px-6 lg:px-8">
      <section className="mx-auto max-w-7xl space-y-6">
        <div className="dashboard-topbar overflow-hidden">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
              <DoctorHeroIcon />
              <div>
                <p className="section-eyebrow">Nora MedLink Doctor</p>
                <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">
                  Doctor Workspace
                </h1>
                <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
                  Appointments, patient context, and urgent visits.
                </p>
              </div>
            </div>

            <div className="flex flex-wrap gap-3">
              <Link href="/doctors" className="secondary-button px-4 py-2">
                Doctor Directory
              </Link>
              <Link href="/dashboard" className="gradient-button px-4 py-2">
                Patient View
              </Link>
            </div>
          </div>
        </div>

        {statusMessage ? (
          <p className="rounded-3xl border border-blue-100 bg-blue-50 px-5 py-4 text-sm font-semibold text-blue-800">
            {statusMessage}
          </p>
        ) : null}

        {isLoading ? (
          <div className="glass-card p-8 text-center text-sm font-semibold text-slate-500">
            Loading doctor dashboard...
          </div>
        ) : overview ? (
          <>
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
              {statCards.map((card) => (
                <article key={card.label} className="metric-card">
                  <div className={`mb-4 h-2 w-20 rounded-full bg-gradient-to-r ${card.color}`} />
                  <p className="text-sm font-semibold text-slate-500">{card.label}</p>
                  <p className="mt-2 text-3xl font-black text-slate-950">{card.value}</p>
                  <p className="mt-1 text-xs font-semibold text-slate-400">{card.detail}</p>
                </article>
              ))}
            </div>

            <section className="premium-card dashboard-panel focus-band">
              <form
                className="relative grid gap-4 lg:grid-cols-[1fr_320px_auto] lg:items-end"
                onSubmit={unlockPatientDashboard}
              >
                <div>
                  <p className="section-eyebrow">Patient Consent</p>
                  <h2 className="mt-2 text-2xl font-black text-slate-950">
                    Unlock patient file
                  </h2>
                  <p className="mt-2 text-sm leading-6 text-slate-500">
                    Use the one-time OTP shared by the patient.
                  </p>
                </div>
                <div>
                  <label htmlFor="dashboard-access-otp" className="text-sm font-bold text-slate-700">
                    One-time OTP
                  </label>
                  <input
                    id="dashboard-access-otp"
                    type="text"
                    value={patientAccessOtp}
                    onChange={(event) => setPatientAccessOtp(event.target.value)}
                    placeholder="6-digit OTP"
                    className="form-input bg-slate-50 text-sm font-black tracking-[0.12em]"
                  />
                </div>
                <button type="submit" disabled={isUnlocking} className="gradient-button h-[50px] px-5">
                  {isUnlocking ? "Unlocking..." : "Unlock"}
                </button>
              </form>
            </section>

            <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
              <div className="dashboard-panel">
                <div className="mb-5 flex items-center justify-between gap-3">
                  <div>
                    <p className="section-eyebrow">Today</p>
                    <h2 className="section-title mt-2 text-2xl">Appointments</h2>
                  </div>
                  <span className="rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700">
                    Dr. {overview.doctor.name.replace(/^Dr\.?\s*/i, "")}
                  </span>
                </div>

                <div className="space-y-3">
                  {overview.appointments.length > 0 ? (
                    overview.appointments.map((appointment) => (
                      <button
                        key={appointment.id}
                        type="button"
                        onClick={() => setActivePatientId(appointment.userId)}
                        className={`w-full rounded-3xl border p-4 text-left shadow-sm transition hover:-translate-y-0.5 hover:shadow-lg ${
                          activePatientId === appointment.userId
                            ? "border-teal-300 bg-teal-50"
                            : "border-slate-100 bg-white"
                        }`}
                      >
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <p className="font-black text-slate-950">{appointment.patientName}</p>
                          <span className="rounded-full bg-white px-3 py-1 text-xs font-bold text-slate-600">
                            #{appointment.id}
                          </span>
                          <span
                            className={`rounded-full px-3 py-1 text-xs font-bold ${
                              appointment.hasDashboardAccess
                                ? "bg-emerald-100 text-emerald-700"
                                : "bg-amber-100 text-amber-700"
                            }`}
                          >
                            {appointment.hasDashboardAccess ? "Session active" : "Needs OTP"}
                          </span>
                        </div>
                        <p className="mt-2 text-sm font-semibold text-slate-600">
                          {formatDate(appointment.date)}
                        </p>
                        <p className="mt-1 text-xs text-slate-500">{appointment.patientEmail}</p>
                        {appointment.accessExpiresAt ? (
                          <p className="mt-1 text-xs font-semibold text-emerald-700">
                            Access expires {formatDate(appointment.accessExpiresAt)}
                          </p>
                        ) : null}
                      </button>
                    ))
                  ) : (
                    <EmptyState title="No appointments yet" text="Appointments booked with your doctor name will appear here." />
                  )}
                </div>
              </div>

              <div className="dashboard-panel">
                <div className="mb-5">
                  <p className="section-eyebrow">Patient File</p>
                  <h2 className="section-title mt-2 text-2xl">
                    {activePatient ? activePatient.name : "Select a patient"}
                  </h2>
                  {activePatient?.accessExpiresAt ? (
                    <div className="mt-3 flex flex-wrap items-center gap-3">
                      <span className="rounded-full bg-emerald-50 px-3 py-1 text-xs font-bold text-emerald-700">
                        Access expires {formatDate(activePatient.accessExpiresAt)}
                      </span>
                      <button
                        type="button"
                        onClick={() => void endConsultationSession(activePatient.id)}
                        className="rounded-full border border-rose-100 bg-rose-50 px-3 py-1 text-xs font-bold text-rose-700 transition hover:bg-rose-100"
                      >
                        End Consultation
                      </button>
                    </div>
                  ) : null}
                </div>

                {activePatient ? (
                  <div className="space-y-4">
                    <div className="grid gap-3 sm:grid-cols-3">
                      <div className="rounded-3xl bg-white p-4">
                        <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400">BP</p>
                        <p className="mt-2 text-xl font-black text-slate-950">
                          {activePatient.latestVitals?.bloodPressure ?? "No data"}
                        </p>
                      </div>
                      <div className="rounded-3xl bg-white p-4">
                        <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400">Sugar</p>
                        <p className="mt-2 text-xl font-black text-slate-950">
                          {activePatient.latestVitals?.sugarLevel ?? "No data"}
                        </p>
                      </div>
                      <div className="rounded-3xl bg-white p-4">
                        <p className="text-xs font-bold uppercase tracking-[0.18em] text-slate-400">Reports</p>
                        <p className="mt-2 text-xl font-black text-slate-950">{activePatient.recordCount}</p>
                      </div>
                    </div>

                    <div className="rounded-3xl border border-slate-100 bg-white p-4">
                      <p className="font-black text-slate-950">Recent Scanned Reports</p>
                      <div className="mt-3 space-y-3">
                        {activePatientRecords.length > 0 ? (
                          activePatientRecords.slice(0, 4).map((record) => (
                            <div key={record.id} className="rounded-2xl bg-slate-50 p-3">
                              <div className="flex flex-wrap items-center justify-between gap-2">
                                <p className="text-sm font-bold text-slate-900">{record.title}</p>
                                <span className="rounded-full bg-white px-2.5 py-1 text-xs font-bold text-slate-500">
                                  {record.scanStatus.toLowerCase()}
                                </span>
                              </div>
                              <p className="mt-1 text-xs text-slate-500">{record.fileName}</p>
                              {record.extractedText ? (
                                <p className="mt-2 line-clamp-2 text-xs leading-5 text-slate-600">
                                  {record.extractedText}
                                </p>
                              ) : null}
                            </div>
                          ))
                        ) : (
                          <p className="text-sm text-slate-500">No scanned reports found for this patient.</p>
                        )}
                      </div>
                    </div>
                  </div>
                ) : (
                    <EmptyState title="No patient selected" text="Enter a one-time patient OTP to unlock vitals, reports, and medicines for this consultation." />
                )}
              </div>
            </section>

            <section className="grid gap-6 lg:grid-cols-2">
              <div className="dashboard-panel">
                <p className="section-eyebrow">Emergency</p>
                <h2 className="section-title mt-2 text-2xl">Emergency Visits</h2>
                <div className="mt-5 space-y-3">
                  {overview.emergencyBookings.length > 0 ? (
                    overview.emergencyBookings.map((booking) => (
                      <article key={booking.id} className="rounded-3xl border border-slate-100 bg-white p-4">
                        <div className="flex flex-wrap items-center gap-2">
                          <p className="font-black text-slate-950">{booking.patientName}</p>
                          <span className={`rounded-full border px-3 py-1 text-xs font-bold capitalize ${statusClass(booking.status)}`}>
                            {formatStatus(booking.status)}
                          </span>
                          <span
                            className={`rounded-full px-3 py-1 text-xs font-bold ${
                              booking.hasDashboardAccess
                                ? "bg-emerald-100 text-emerald-700"
                                : "bg-amber-100 text-amber-700"
                            }`}
                          >
                            {booking.hasDashboardAccess ? "Session active" : "Needs OTP"}
                          </span>
                        </div>
                        <p className="mt-2 text-sm font-semibold text-slate-700">{booking.symptoms}</p>
                        <p className="mt-1 text-xs leading-5 text-slate-500">
                          {booking.phone} | {booking.address} | ETA {booking.estimatedMinutes} min
                        </p>
                      </article>
                    ))
                  ) : (
                    <EmptyState title="No emergency visits" text="Assigned emergency bookings will appear here." />
                  )}
                </div>
              </div>

              <div className="dashboard-panel">
                <p className="section-eyebrow">Medication</p>
                <h2 className="section-title mt-2 text-2xl">Medicines</h2>
                <div className="mt-5 space-y-3">
                  {overview.medications.length > 0 ? (
                    overview.medications.map((medicine) => (
                      <article key={medicine.id} className="rounded-3xl border border-slate-100 bg-white p-4">
                        <div className="flex flex-wrap items-center justify-between gap-2">
                          <div>
                            <p className="font-black text-slate-950">{medicine.name}</p>
                            <p className="mt-1 text-sm text-slate-500">
                              {medicine.patientName} | {medicine.dosage}
                            </p>
                          </div>
                          <span className={`rounded-full border px-3 py-1 text-xs font-bold capitalize ${statusClass(medicine.status)}`}>
                            {formatStatus(medicine.status)}
                          </span>
                        </div>
                      </article>
                    ))
                  ) : (
                    <EmptyState title="No medicines logged" text="Patient medicine reminders will appear here once added." />
                  )}
                </div>
              </div>
            </section>
          </>
        ) : (
          <div className="glass-card p-8 text-center">
            <h2 className="text-2xl font-black text-slate-950">Doctor access needed</h2>
            <p className="mt-2 text-sm text-slate-500">
              Login with a doctor account. If you are using an older account, create a new one with Join as Doctor.
            </p>
            <div className="mt-5 flex flex-wrap justify-center gap-3">
              <Link href="/login" className="gradient-button inline-flex">
                Go to Login
              </Link>
              <Link href="/signup?role=doctor" className="secondary-button inline-flex">
                Create Doctor Account
              </Link>
            </div>
          </div>
        )}
      </section>
    </main>
  );
}
