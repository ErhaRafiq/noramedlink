"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Activity, CalendarDays, FileText, LayoutDashboard, Stethoscope, UserRound, Users } from "lucide-react";

import { DashboardShell, type DashboardNavItem } from "@/components/layout/DashboardShell";
import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { SkeletonCard } from "@/components/ui/skeleton";
import { ErrorState, PageLoader } from "@/components/ui/spinner";
import { StatCard, StatCardSkeleton } from "@/components/ui/stat-card";
import { signOut as endSession } from "@/lib/auth";
import type { AdminDoctor } from "@/lib/types";
import { useAdminDashboard } from "@/hooks/admin/use-admin-dashboard";
import { useAuthGuard } from "@/hooks/use-auth-guard";
import { AccountOverview, DoctorReviewQueue, RecentAccounts, RecentActivity } from "./AdminSections";

const NAV: DashboardNavItem[] = [
  { id: "summary", label: "Summary", icon: LayoutDashboard },
  { id: "doctors", label: "Doctor review", icon: Stethoscope },
  { id: "users", label: "New sign-ups", icon: Users },
  { id: "overview", label: "Accounts", icon: UserRound },
  { id: "activity", label: "Activity", icon: Activity },
];

type Notice = { ok: boolean; message: string } | null;

export function AdminView() {
  const router = useRouter();
  const auth = useAuthGuard("admin");
  const dashboard = useAdminDashboard(auth.status === "ready");
  const [notice, setNotice] = useState<Notice>(null);
  const [rejecting, setRejecting] = useState<AdminDoctor | null>(null);

  async function decide(doctor: AdminDoctor, decision: "approve" | "reject") {
    setNotice(null);
    const result = await dashboard.decide(doctor, decision);
    if (result) setNotice(result);
    setRejecting(null);
  }

  function signOut() {
    void endSession();
    router.replace("/login");
  }

  if (auth.status === "error") return <ErrorState message={auth.message} onRetry={() => window.location.reload()} />;
  if (auth.status !== "ready") return <PageLoader message="Checking your session..." />;

  const { stats } = dashboard;

  return (
    <DashboardShell nav={NAV} userName={auth.user.full_name || "Administrator"} userMeta="Administrator" onSignOut={signOut}>
      <header id="summary" className="scroll-mt-24">
        <p className="section-eyebrow">Administration</p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-ink">Admin dashboard</h1>
        <p className="mt-1 text-sm text-ink-muted">Doctor verification, new accounts and platform activity.</p>
      </header>

      {notice ? <Alert tone={notice.ok ? "success" : "error"}>{notice.message}</Alert> : null}

      {dashboard.status === "error" ? (
        <Alert tone="error" title="The dashboard could not be loaded">
          {dashboard.error}{" "}
          <Button variant="ghost" size="sm" className="px-2" onClick={() => void dashboard.retry()}>
            Try again
          </Button>
        </Alert>
      ) : dashboard.status === "loading" || !stats ? (
        <div role="status" aria-label="Loading the admin dashboard" className="space-y-6">
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            {Array.from({ length: 4 }, (_, i) => (
              <StatCardSkeleton key={i} />
            ))}
          </div>
          <div className="grid gap-6 xl:grid-cols-2">
            <SkeletonCard lines={5} />
            <SkeletonCard lines={5} />
          </div>
        </div>
      ) : (
        <>
          <section aria-label="Platform summary" className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard label="Users" value={stats.totalUsers} detail="all accounts" icon={Users} />
            <StatCard label="Verified doctors" value={stats.activeDoctors} detail="approved and bookable" icon={Stethoscope} tint="bg-teal-50 text-teal-700" />
            <StatCard label="Reports" value={stats.reportsUploaded} detail="uploaded by patients" icon={FileText} tint="bg-violet-50 text-violet-700" />
            <StatCard label="Appointments today" value={stats.appointmentsToday} detail="scheduled for today" icon={CalendarDays} tint="bg-amber-50 text-amber-700" />
          </section>

          <div className="grid gap-6 xl:grid-cols-[1.1fr_0.9fr]">
            <DoctorReviewQueue
              doctors={dashboard.pendingDoctors}
              deciding={dashboard.deciding}
              onApprove={(doctor) => void decide(doctor, "approve")}
              onReject={setRejecting}
            />
            <RecentAccounts users={dashboard.users} />
          </div>

          <div className="grid items-start gap-6 xl:grid-cols-[0.9fr_1.1fr]">
            <AccountOverview stats={stats} pendingDoctors={dashboard.pendingDoctors.length} />
            <RecentActivity activity={dashboard.activity} />
          </div>
        </>
      )}

      <ConfirmDialog
        open={rejecting !== null}
        title="Reject this doctor?"
        description={
          <>
            <strong className="font-semibold text-ink">{rejecting?.fullName}</strong> will not be listed for patients and cannot be
            booked. Do this only if the registration could not be verified.
          </>
        }
        confirmLabel="Reject doctor"
        pendingLabel="Rejecting..."
        pending={dashboard.deciding?.decision === "reject"}
        onConfirm={() => rejecting && void decide(rejecting, "reject")}
        onCancel={() => setRejecting(null)}
      />
    </DashboardShell>
  );
}
