"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useCallback, useEffect, useMemo, useState } from "react";
import {
  Bell,
  CalendarDays,
  CheckCircle2,
  CreditCard,
  FileText,
  LayoutDashboard,
  Loader2,
  Settings,
  ShieldCheck,
  Stethoscope,
  Users,
  UserRound,
  XCircle,
} from "lucide-react";

import { DashboardCard, Sidebar, StatCard } from "@/components/ui/saas-shell";
import { api } from "@/lib/api";
import { clearSession, dashboardPathForRole, getSession } from "@/lib/auth";
import type { AdminActivity, AdminDashboardStats, AdminDoctor, AdminUser } from "@/lib/types";

const adminSidebarItems = [
  { href: "/admin", label: "Dashboard", icon: LayoutDashboard, active: true },
  { href: "/admin#users", label: "Users", icon: Users },
  { href: "/admin#doctors", label: "Doctors", icon: Stethoscope },
  { href: "/admin#patients", label: "Patients", icon: UserRound },
  { href: "/admin#reports", label: "Reports", icon: FileText },
  { href: "/admin#appointments", label: "Appointments", icon: CalendarDays },
  { href: "/admin#payments", label: "Payments", icon: CreditCard },
  { href: "/admin#notifications", label: "Notifications", icon: Bell },
  { href: "/admin#settings", label: "System Settings", icon: Settings },
];

function formatDate(value: string) {
  return new Intl.DateTimeFormat("en", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(new Date(value));
}

export default function AdminPage() {
  const router = useRouter();
  const [stats, setStats] = useState<AdminDashboardStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [pendingDoctors, setPendingDoctors] = useState<AdminDoctor[]>([]);
  const [activity, setActivity] = useState<AdminActivity[]>([]);
  const [statusMessage, setStatusMessage] = useState("");
  const [isLoading, setIsLoading] = useState(true);
  const [updatingDoctorId, setUpdatingDoctorId] = useState<number | null>(null);

  const loadDashboard = useCallback(async (activeToken: string) => {
    setIsLoading(true);
    setStatusMessage("");

    try {
      const [statsData, userData, pendingDoctorData, activityData] = await Promise.all([
        api.adminDashboardStats(activeToken),
        api.adminUsers(activeToken),
        api.adminPendingDoctors(activeToken),
        api.adminRecentActivity(activeToken),
      ]);

      setStats(statsData);
      setUsers(userData);
      setPendingDoctors(pendingDoctorData);
      setActivity(activityData);
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Admin dashboard could not be loaded.");
    } finally {
      setIsLoading(false);
    }
  }, []);

  useEffect(() => {
    const session = getSession();
    if (!session) {
      router.replace("/login");
      return;
    }

    if (session.user.role !== "admin") {
      router.replace(dashboardPathForRole(session.user.role));
      return;
    }

    const loadTimer = window.setTimeout(() => {
      void loadDashboard(session.token);
    }, 0);

    return () => window.clearTimeout(loadTimer);
  }, [loadDashboard, router]);

  const recentUsers = useMemo(() => users.slice(0, 6), [users]);
  const patientCount = users.filter((user) => user.role === "patient").length;

  async function updateDoctor(doctorId: number, action: "approve" | "reject") {
    const session = getSession();
    if (!session) {
      router.replace("/login");
      return;
    }

    if (session.user.role !== "admin") {
      router.replace(dashboardPathForRole(session.user.role));
      return;
    }

    setUpdatingDoctorId(doctorId);
    setStatusMessage("");
    try {
      if (action === "approve") {
        await api.approveAdminDoctor(session.token, doctorId);
      } else {
        await api.rejectAdminDoctor(session.token, doctorId);
      }
      await loadDashboard(session.token);
      setStatusMessage(action === "approve" ? "Doctor verification approved." : "Doctor verification rejected.");
    } catch (error) {
      setStatusMessage(error instanceof Error ? error.message : "Doctor verification update failed.");
    } finally {
      setUpdatingDoctorId(null);
    }
  }

  function logout() {
    clearSession();
    router.replace("/login");
  }

  return (
    <main className="app-shell min-h-screen">
      <div className="mx-auto grid max-w-[1520px] gap-6 px-4 py-5 lg:grid-cols-[286px_1fr] lg:px-6">
        <Sidebar
          items={adminSidebarItems}
          userName="Nora MedLink Admin"
          userMeta="System operations"
          action={
            <button
              type="button"
              onClick={logout}
              className="flex w-full items-center gap-3 rounded-[16px] px-4 py-3 text-left text-sm font-bold text-red-100 transition hover:bg-red-400/10"
            >
              <XCircle className="h-4 w-4" />
              Logout
            </button>
          }
        />

        <section className="flex flex-col gap-6">
          <header className="dashboard-topbar overflow-hidden">
            <div className="flex flex-col gap-5 md:flex-row md:items-center md:justify-between">
              <div className="flex items-center gap-5">
                <span className="grid h-14 w-14 shrink-0 place-items-center rounded-2xl bg-gradient-to-br from-[#2563EB] to-[#00BFA6] text-white shadow-lg shadow-teal-500/20">
                  <ShieldCheck className="h-7 w-7" />
                </span>
                <div>
                  <p className="section-eyebrow">Nora MedLink Admin</p>
                  <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950 sm:text-4xl">
                    Admin Dashboard
                  </h1>
                  <p className="mt-2 max-w-xl text-sm leading-6 text-slate-500">
                    Users, doctors, reports, appointments, payments, notifications, and system records.
                  </p>
                </div>
              </div>
              <div className="flex flex-wrap gap-3">
                <Link href="/dashboard/patient" className="secondary-button px-4 py-2">
                  Patient View
                </Link>
                <Link href="/dashboard/doctor" className="gradient-button px-4 py-2">
                  Doctor View
                </Link>
              </div>
            </div>
          </header>

          {statusMessage ? (
            <p className="rounded-2xl border border-blue-100 bg-blue-50 px-5 py-4 text-sm font-semibold text-blue-800">
              {statusMessage}
            </p>
          ) : null}

          {isLoading ? (
            <div className="glass-card p-8 text-center text-sm font-semibold text-slate-500">
              <Loader2 className="mx-auto mb-3 h-6 w-6 animate-spin text-teal-600" />
              Loading admin dashboard...
            </div>
          ) : stats ? (
            <>
              <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
                <StatCard label="Total Users" value={stats.totalUsers} detail="all accounts" icon={Users} />
                <StatCard label="Active Doctors" value={stats.activeDoctors} detail="approved doctors" icon={Stethoscope} />
                <StatCard label="Reports Uploaded" value={stats.reportsUploaded} detail="patient report records" icon={FileText} />
                <StatCard label="Appointments Today" value={stats.appointmentsToday} detail="scheduled today" icon={CalendarDays} />
              </section>

              <section className="grid gap-6 xl:grid-cols-[0.95fr_1.05fr]">
                <DashboardCard id="doctors">
                  <div className="mb-5 flex items-center justify-between gap-3">
                    <div>
                      <p className="section-eyebrow">Pending Doctor Verifications</p>
                      <h2 className="section-title mt-2 text-2xl">Doctor Review Queue</h2>
                    </div>
                    <span className="soft-badge">{stats.pendingDoctors} pending</span>
                  </div>

                  {pendingDoctors.length > 0 ? (
                    <div className="space-y-3">
                      {pendingDoctors.map((doctor) => (
                        <article key={doctor.id} className="rounded-2xl border border-[#DCE8F5] bg-[#F8FBFF] p-4">
                          <div className="flex flex-col gap-4 xl:flex-row xl:items-start xl:justify-between">
                            <div>
                              <p className="font-black text-slate-950">{doctor.fullName}</p>
                              <p className="mt-1 text-sm text-slate-500">{doctor.email}</p>
                              <p className="mt-2 text-sm font-semibold text-slate-700">
                                {doctor.specialization} | PMDC/PMC {doctor.pmdcNumber}
                              </p>
                              <p className="mt-1 text-xs text-slate-500">{doctor.hospitalName}</p>
                            </div>
                            <div className="flex flex-wrap gap-2">
                              <button
                                type="button"
                                disabled={updatingDoctorId === doctor.id}
                                onClick={() => void updateDoctor(doctor.id, "approve")}
                                className="gradient-button gap-2 px-4 py-2"
                              >
                                <CheckCircle2 className="h-4 w-4" />
                                Approve
                              </button>
                              <button
                                type="button"
                                disabled={updatingDoctorId === doctor.id}
                                onClick={() => void updateDoctor(doctor.id, "reject")}
                                className="secondary-button gap-2 px-4 py-2 text-red-700"
                              >
                                <XCircle className="h-4 w-4" />
                                Reject
                              </button>
                            </div>
                          </div>
                        </article>
                      ))}
                    </div>
                  ) : (
                    <p className="rounded-2xl border border-dashed border-[#DCE8F5] bg-[#F8FBFF] p-6 text-sm font-semibold text-slate-500">
                      No pending doctor verifications.
                    </p>
                  )}
                </DashboardCard>

                <DashboardCard id="users">
                  <div className="mb-5">
                    <p className="section-eyebrow">Recent Registrations</p>
                    <h2 className="section-title mt-2 text-2xl">New Accounts</h2>
                  </div>
                  <div className="space-y-3">
                    {recentUsers.map((user) => (
                      <article key={user.id} className="flex items-center justify-between gap-3 rounded-2xl border border-[#DCE8F5] bg-[#F8FBFF] p-4">
                        <div>
                          <p className="font-black text-slate-950">{user.fullName}</p>
                          <p className="mt-1 text-sm text-slate-500">{user.email}</p>
                        </div>
                        <span className="rounded-full bg-white px-3 py-1 text-xs font-bold capitalize text-slate-600 ring-1 ring-[#DCE8F5]">
                          {user.role}
                        </span>
                      </article>
                    ))}
                  </div>
                </DashboardCard>
              </section>

              <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
                <DashboardCard id="patients">
                  <p className="section-eyebrow">Users</p>
                  <h2 className="section-title mt-2 text-2xl">Account Overview</h2>
                  <div className="mt-5 grid gap-3 sm:grid-cols-3">
                    <SmallMetric label="Patients" value={patientCount} />
                    <SmallMetric label="Doctors Pending" value={pendingDoctors.length} />
                    <SmallMetric label="Active Users" value={users.filter((user) => user.isActive).length} />
                  </div>
                </DashboardCard>

                <DashboardCard>
                  <p className="section-eyebrow">System Activity</p>
                  <h2 className="section-title mt-2 text-2xl">Recent Activity</h2>
                  <div className="mt-5 space-y-3">
                    {activity.map((item) => (
                      <article key={item.id} className="rounded-2xl border border-[#DCE8F5] bg-[#F8FBFF] p-4">
                        <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
                          <div>
                            <p className="font-black text-slate-950">{item.title}</p>
                            <p className="mt-1 text-sm text-slate-500">{item.description}</p>
                          </div>
                          <span className="text-xs font-bold text-slate-400">{formatDate(item.createdAt)}</span>
                        </div>
                      </article>
                    ))}
                  </div>
                </DashboardCard>
              </section>
            </>
          ) : (
            <div className="glass-card p-8 text-center">
              <h2 className="text-2xl font-black text-slate-950">Admin data unavailable</h2>
              <p className="mt-2 text-sm text-slate-500">
                Login with an admin account and make sure the FastAPI backend is running on localhost:8000.
              </p>
              <Link href="/login" className="gradient-button mt-5 inline-flex">
                Go to Login
              </Link>
            </div>
          )}
        </section>
      </div>
    </main>
  );
}

function SmallMetric({ label, value }: { label: string; value: number }) {
  return (
    <div className="rounded-2xl border border-[#DCE8F5] bg-[#F8FBFF] p-4">
      <p className="text-xs font-black uppercase tracking-[0.14em] text-slate-400">{label}</p>
      <p className="mt-2 text-2xl font-black text-slate-950">{value}</p>
    </div>
  );
}
