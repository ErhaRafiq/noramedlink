"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { AdminActivity, AdminDashboardStats, AdminDoctor, AdminUser, SymptomStats } from "@/lib/types";

// The "New accounts" card lists the latest sign-ups; counts come from dashboard-stats.
const RECENT_USERS = 6;

export type DoctorDecision = "approve" | "reject";

/** Admin overview data plus approving or rejecting doctors in the review queue. */
export function useAdminDashboard(signedIn: boolean) {
  const [stats, setStats] = useState<AdminDashboardStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [pendingDoctors, setPendingDoctors] = useState<AdminDoctor[]>([]);
  const [activity, setActivity] = useState<AdminActivity[]>([]);
  const [symptoms, setSymptoms] = useState<SymptomStats | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [deciding, setDeciding] = useState<{ doctorId: number; decision: DoctorDecision } | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const load = useCallback(async () => {
    if (!signedIn) return;
    try {
      const [statsData, userPage, doctors, activityData, symptomData] = await Promise.all([
        api.adminDashboardStats(),
        api.adminUsers({ limit: RECENT_USERS }),
        api.adminPendingDoctors(),
        api.adminRecentActivity(),
        api.adminSymptomStats().catch(() => null), // a side card: the dashboard still loads without it
      ]);
      if (!mountedRef.current) return;
      setStats(statsData);
      setUsers(userPage.items);
      setPendingDoctors(doctors);
      setActivity(activityData);
      setSymptoms(symptomData);
      setStatus("ready");
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err.message : "The admin dashboard could not be loaded.");
      setStatus("error");
    }
  }, [signedIn]);

  useEffect(() => {
    if (!signedIn) return;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load, signedIn]);

  /** Approves or rejects a pending doctor. Returns a message for the page to show. */
  const decide = useCallback(
    async (doctor: AdminDoctor, decision: DoctorDecision) => {
      if (!signedIn || deciding) return null;
      setDeciding({ doctorId: doctor.id, decision });
      try {
        if (decision === "approve") await api.approveAdminDoctor(doctor.id);
        else await api.rejectAdminDoctor(doctor.id);
        await load();
        return {
          ok: true,
          message: decision === "approve" ? `${doctor.fullName} is approved and can now be booked.` : `${doctor.fullName}'s registration was rejected.`,
        };
      } catch (err) {
        return { ok: false, message: err instanceof Error ? err.message : "The decision could not be saved." };
      } finally {
        if (mountedRef.current) setDeciding(null);
      }
    },
    [deciding, load, signedIn],
  );

  return { stats, users, pendingDoctors, activity, symptoms, status, error, deciding, decide, retry: load };
}
