"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { Appointment } from "@/lib/types";

const PAGE_SIZE = 20;

/** The signed-in patient's appointments (soonest first) with cancel and reschedule. */
export function useMyAppointments(token: string | null) {
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [status, setStatus] = useState<"idle" | "loading" | "ready" | "error">("idle");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);

  const load = useCallback(async () => {
    if (!token) return;
    setStatus("loading");
    try {
      const page = await api.appointments(token, { limit: PAGE_SIZE });
      setAppointments([...page.items].sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime()));
      setStatus("ready");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to load your appointments.");
      setStatus("error");
    }
  }, [token]);

  useEffect(() => {
    if (!token) return;
    const timer = window.setTimeout(() => void load(), 0);
    return () => window.clearTimeout(timer);
  }, [load, token]);

  /** Runs an update for one appointment, then reloads. Returns an error message or null. */
  const update = useCallback(
    async (appointmentId: number, payload: { date?: string; status?: string }) => {
      if (!token || busyId !== null) return null;
      setBusyId(appointmentId);
      try {
        await api.updateAppointment(token, appointmentId, payload);
        await load();
        return null;
      } catch (err) {
        return err instanceof Error ? err.message : "Unable to update the appointment.";
      } finally {
        setBusyId(null);
      }
    },
    [busyId, load, token],
  );

  return {
    appointments,
    status,
    error,
    busyId,
    reload: load,
    cancel: (id: number) => update(id, { status: "CANCELLED" }),
    reschedule: (id: number, isoDate: string) => update(id, { date: isoDate, status: "BOOKED" }),
  };
}
