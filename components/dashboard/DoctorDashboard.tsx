"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import {
  Activity,
  CalendarDays,
  ClipboardPlus,
  FileSearch,
  LayoutDashboard,
  LogOut,
  Sparkles,
  Stethoscope,
  Users,
} from "lucide-react";

import { DashboardCard, Sidebar, StatCard } from "@/components/ui/saas-shell";
import { api } from "@/lib/api";
import { clearSession, getSession, updateStoredUser } from "@/lib/auth";
import type { DoctorDashboard as DoctorDashboardType } from "@/lib/types";

const sidebarItems = [
  { href: "/dashboard/doctor", label: "Dashboard", icon: LayoutDashboard, active: true },
  { href: "/doctor-dashboard", label: "Patients", icon: Users },
  { href: "/doctor-dashboard", label: "Review Reports", icon: FileSearch },
  { href: "/doctor-dashboard", label: "Appointments", icon: CalendarDays },
];

export function DoctorDashboard() {
  const router = useRouter();
  const [dashboard, setDashboard] = useState<DoctorDashboardType | null>(null);
  const [statusMessage, setStatusMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);

  useEffect(() => {
    const session = getSession();
    if (!session) {
      router.replace("/login");
      return;
    }

    void Promise.all([api.me(session.token), api.doctorDashboard(session.token)])
      .then(([user, doctorDashboard]) => {
        if (user.role !== "doctor") {
          router.replace("/dashboard/patient");
          return;
        }
        updateStoredUser(user);
        setDashboard(doctorDashboard);
      })
      .catch((error) => {
        setStatusMessage(error instanceof Error ? error.message : "Unable to load doctor dashboard.");
        clearSession();
        router.replace("/login");
      })
      .finally(() => setIsLoading(false));
  }, [router]);

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

  const doctorName = dashboard?.doctor.full_name.replace(/^dr\.?\s*/i, "") || "Doctor";
  const stats = dashboard?.stats;

  return (
    <main className="app-shell min-h-screen">
      <div className="mx-auto grid max-w-[1520px] gap-6 px-4 py-5 lg:grid-cols-[286px_1fr] lg:px-6">
        <Sidebar
          items={sidebarItems}
          userName={`Dr. ${doctorName}`}
          userMeta={dashboard?.doctor.email}
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
                  Welcome back, Dr. {doctorName}
                </h1>
                <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
                  Patient queue, report review, appointments, and AI summary readiness.
                </p>
              </div>
              <div className="flex flex-wrap gap-3">
                <Link href="/doctor-dashboard" className="gradient-button gap-2 px-4 py-3">
                  <Users className="h-4 w-4" />
                  View Patients
                </Link>
                <Link href="/doctors" className="secondary-button gap-2 px-4 py-3">
                  <Stethoscope className="h-4 w-4" />
                  Doctor Directory
                </Link>
              </div>
            </div>
          </header>

          {statusMessage ? (
            <p className="rounded-2xl border border-red-100 bg-red-50 px-5 py-4 text-sm font-semibold text-red-700">
              {statusMessage}
            </p>
          ) : null}

          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Today's Appointments" value={stats?.pending_consults ?? 0} detail="pending consults" icon={CalendarDays} />
            <StatCard label="Patients Reviewed" value={stats?.records_reviewed ?? 0} detail="records reviewed" icon={Users} />
            <StatCard label="Pending Reports" value={stats?.assigned_patients ?? 0} detail="assigned patients" icon={FileSearch} />
            <StatCard label="AI Summaries" value={stats?.future_modules ?? 0} detail="ready modules" icon={Sparkles} />
          </section>

          <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
            <DashboardCard>
              <div className="mb-5 flex items-center justify-between gap-4">
                <div>
                  <p className="section-eyebrow">Patient queue</p>
                  <h2 className="mt-2 text-2xl font-black text-slate-950">Review priorities</h2>
                </div>
                <span className="soft-badge">{stats?.assigned_patients ?? 0} active</span>
              </div>
              <div className="space-y-3">
                {(dashboard?.modules ?? []).slice(0, 3).map((module, index) => (
                  <article key={module.title} className="rounded-2xl border border-[#DCE8F5] bg-[#F8FBFF] p-4">
                    <div className="flex items-start gap-3">
                      <span className="grid h-10 w-10 shrink-0 place-items-center rounded-xl bg-blue-50 text-blue-700">
                        {index === 0 ? <Users className="h-4 w-4" /> : index === 1 ? <FileSearch className="h-4 w-4" /> : <Activity className="h-4 w-4" />}
                      </span>
                      <div>
                        <p className="text-sm font-black text-slate-950">{module.title}</p>
                        <p className="mt-1 text-sm leading-6 text-slate-600">{module.description}</p>
                      </div>
                    </div>
                  </article>
                ))}
              </div>
            </DashboardCard>

            <DashboardCard>
              <div className="mb-5">
                <p className="section-eyebrow">Recent reports needing review</p>
                <h2 className="mt-2 text-2xl font-black text-slate-950">Report triage</h2>
              </div>
              <div className="grid gap-3">
                {["Patient OCR summary", "Lab result validation", "Appointment preparation"].map((item) => (
                  <div key={item} className="flex items-center justify-between rounded-2xl border border-[#DCE8F5] bg-[#F8FBFF] p-4">
                    <div className="flex items-center gap-3">
                      <FileSearch className="h-5 w-5 text-blue-700" />
                      <p className="text-sm font-black text-slate-950">{item}</p>
                    </div>
                    <span className="rounded-full bg-amber-50 px-3 py-1 text-xs font-black text-amber-700">
                      Pending
                    </span>
                  </div>
                ))}
              </div>
            </DashboardCard>
          </section>

          <section className="grid gap-6 lg:grid-cols-2">
            <DashboardCard>
              <p className="section-eyebrow">Appointment schedule</p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">Today</h2>
              <div className="mt-5 space-y-3">
                {["Morning clinic", "Patient review block", "Evening follow-up"].map((slot) => (
                  <div key={slot} className="rounded-2xl border border-[#DCE8F5] bg-[#F8FBFF] p-4">
                    <p className="text-sm font-black text-slate-950">{slot}</p>
                    <p className="mt-1 text-xs font-bold text-slate-500">Managed from appointment modules.</p>
                  </div>
                ))}
              </div>
            </DashboardCard>

            <DashboardCard>
              <p className="section-eyebrow">Quick actions</p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">Doctor tools</h2>
              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <Link href="/doctor-dashboard" className="secondary-button gap-2 px-4 py-3">
                  <Users className="h-4 w-4" />
                  View Patients
                </Link>
                <Link href="/doctor-dashboard" className="secondary-button gap-2 px-4 py-3">
                  <ClipboardPlus className="h-4 w-4" />
                  Review Reports
                </Link>
                <Link href="/doctor-dashboard" className="secondary-button gap-2 px-4 py-3">
                  <CalendarDays className="h-4 w-4" />
                  Manage Appointments
                </Link>
              </div>
            </DashboardCard>
          </section>
        </section>
      </div>
    </main>
  );
}
