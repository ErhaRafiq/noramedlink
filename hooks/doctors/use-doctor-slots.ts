"use client";

import { useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { DaySlots } from "@/lib/types";

const DAYS = 14;

/** A doctor's bookable times for the next two weeks (clinic time); loads when `doctorId` is set. */
export function useDoctorSlots(doctorId: number | null) {
  const [state, setState] = useState<{ doctorId: number | null; days: DaySlots[]; error: string }>({ doctorId: null, days: [], error: "" });
  const [reloads, setReloads] = useState(0);

  useEffect(() => {
    if (doctorId === null) return;
    const controller = new AbortController();
    api
      .doctorSlots(doctorId, DAYS, { signal: controller.signal })
      .then((data) => setState({ doctorId, days: data.days, error: "" }))
      .catch((err: unknown) => {
        if (!controller.signal.aborted) setState({ doctorId, days: [], error: err instanceof Error ? err.message : "Unable to load times." });
      });
    return () => controller.abort();
  }, [doctorId, reloads]);

  const loading = doctorId !== null && state.doctorId !== doctorId;
  return {
    days: loading ? [] : state.days,
    error: loading ? "" : state.error,
    loading,
    reload: () => setReloads((n) => n + 1),
  };
}
