"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Appointment } from "@/lib/types";

const PAGE_SIZE = 20;

/** The signed-in patient's appointments (soonest first) with move, cancel and rate. */
export function useMyAppointments(signedIn: boolean) {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!signedIn) return;
    setStatus("loading");
    try {
      const page = await api.appointments({ limit: PAGE_SIZE });
      setAppointments([...page.items].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()));
      setStatus("ready");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load your appointments.");
      setStatus("error");
    }
  }, [signedIn]);

  useEffect(() => {
    if (!signedIn) return;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load, signedIn]);

  /** Runs one change for one appointment, then reloads. Returns an error message or null. */
  const change = useCallback(
    async (appointmentId: number, action: () => Promise<unknown>, fallback: string) => {
      if (!signedIn || busyId !== null) return null;
      setBusyId(appointmentId);
      try {
        await action();
        await load();
        return null;
      } catch (err) {
        return err instanceof Error ? err.message : fallback;
      } finally {
        setBusyId(null);
      }
    },
    [busyId, load, signedIn],
  );

  return {
    appointments,
    status,
    error,
    busyId,
    reload: load,
    cancel: (id: number) => change(id, () => api.updateAppointment(id, { status: "CANCELLED" }), "Unable to cancel the appointment."),
    reschedule: (id: number, isoDate: string) =>
      change(id, () => api.updateAppointment(id, { date: isoDate }), "Unable to move the appointment."),
    review: (id: number, rating: number, comment: string) =>
      change(id, () => api.reviewAppointment(id, { rating, comment }), "Unable to save your rating."),
  };
}
