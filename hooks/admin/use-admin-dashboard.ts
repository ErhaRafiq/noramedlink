"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { AdminActivity, AdminDashboardStats, AdminDoctor, AdminUser } from "@/lib/types";

// The "New accounts" card lists the latest sign-ups; counts come from dashboard-stats.
const RECENT_USERS = 6;

export type DoctorDecision = "approve" | "reject";

/** Admin overview data plus approving or rejecting doctors in the review queue. */
export function useAdminDashboard(token: string | null) {
  const [stats, setStats] = useState<AdminDashboardStats | null>(null);
  const [users, setUsers] = useState<AdminUser[]>([]);
  const [pendingDoctors, setPendingDoctors] = useState<AdminDoctor[]>([]);
  const [activity, setActivity] = useState<AdminActivity[]>([]);
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
    if (!token) return;
    try {
      const [statsData, userPage, doctors, activityData] = await Promise.all([
        api.adminDashboardStats(token),
        api.adminUsers(token, { limit: RECENT_USERS }),
        api.adminPendingDoctors(token),
        api.adminRecentActivity(token),
      ]);
      if (!mountedRef.current) return;
      setStats(statsData);
      setUsers(userPage.items);
      setPendingDoctors(doctors);
      setActivity(activityData);
      setStatus("ready");
    } catch (err) {
      if (!mountedRef.current) return;
      setError(err instanceof Error ? err.message : "The admin dashboard could not be loaded.");
      setStatus("error");
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load, token]);

  /** Approves or rejects a pending doctor. Returns a message for the page to show. */
  const decide = useCallback(
    async (doctor: AdminDoctor, decision: DoctorDecision) => {
      if (!token || deciding) return null;
      setDeciding({ doctorId: doctor.id, decision });
      try {
        if (decision === "approve") await api.approveAdminDoctor(token, doctor.id);
        else await api.rejectAdminDoctor(token, doctor.id);
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
    [deciding, load, token],
  );

  return { stats, users, pendingDoctors, activity, status, error, deciding, decide, retry: load };
}
