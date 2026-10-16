"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { DoctorDashboard as DoctorProfileResponse, DoctorOverview } from "@/lib/types";

export type DoctorProfile = DoctorProfileResponse["doctor"];
export type DoctorNotice = { tone: "error" | "success"; text: string } | null;

/**
 * Data and actions for the doctor dashboard: the doctor's profile, the overview
 * (appointments, patients with access, emergency visits), the selected patient, and
 * unlocking or ending access with a one-time code.
 */
export function useDoctorDashboard(signedIn: boolean) {
  const [profile, setProfile] = useState<DoctorProfile | null>(null);
  const [overview, setOverview] = useState<DoctorOverview | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [notice, setNotice] = useState<DoctorNotice>(null);
  const [selectedPatientId, setSelectedPatientId] = useState<number | null>(null);
  const [isUnlocking, setIsUnlocking] = useState(false);
  const [endingPatientId, setEndingPatientId] = useState<number | null>(null);
  const [changingAppointmentId, setChangingAppointmentId] = useState<number | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const applyOverview = useCallback((data: DoctorOverview, preferPatientId?: number | null) => {
    setOverview(data);
    setSelectedPatientId((current) => {
      const wanted = preferPatientId === undefined ? current : preferPatientId;
      if (wanted !== null) return wanted;
      return data.patients[0]?.id ?? null;
    });
  }, []);

  useEffect(() => {
    if (!signedIn) return;
    Promise.all([api.doctorDashboard(), api.doctorOverview()])
      .then(([doctor, data]) => {
        if (!mountedRef.current) return;
        setProfile(doctor.doctor);
        applyOverview(data);
      })
      .catch((error: unknown) => {
        if (!mountedRef.current) return;
        setNotice({ tone: "error", text: error instanceof Error ? error.message : "Unable to load the doctor dashboard." });
      })
      .finally(() => {
        if (mountedRef.current) setIsLoading(false);
      });
  }, [applyOverview, signedIn]);

  const reload = useCallback(
    async (preferPatientId?: number | null) => {
      if (!signedIn) return;
      const data = await api.doctorOverview();
      if (mountedRef.current) applyOverview(data, preferPatientId);
    },
    [applyOverview, signedIn],
  );

  /** Unlocks a patient's file with the code they shared. Returns true on success. */
  const unlock = useCallback(
    async (code: string) => {
      if (!signedIn || isUnlocking) return false;
      const trimmed = code.trim();
      if (!trimmed) {
        setNotice({ tone: "error", text: "Enter the one-time code the patient shared with you." });
        return false;
      }
      setIsUnlocking(true);
      setNotice(null);
      try {
        const data = await api.unlockPatientDashboard(trimmed);
        setNotice({ tone: "success", text: data.message });
        await reload(data.patient.id);
        return true;
      } catch (error) {
        setNotice({ tone: "error", text: error instanceof Error ? error.message : "Unable to unlock the patient file." });
        return false;
      } finally {
        if (mountedRef.current) setIsUnlocking(false);
      }
    },
    [isUnlocking, reload, signedIn],
  );

  const endAccess = useCallback(
    async (patientId: number) => {
      if (!signedIn || endingPatientId !== null) return;
      setEndingPatientId(patientId);
      setNotice(null);
      try {
        const data = await api.endPatientDashboardAccess(patientId);
        setNotice({ tone: "success", text: data.message });
        setSelectedPatientId(null);
        await reload(null);
      } catch (error) {
        setNotice({ tone: "error", text: error instanceof Error ? error.message : "Unable to end the consultation." });
      } finally {
        if (mountedRef.current) setEndingPatientId(null);
      }
    },
    [endingPatientId, reload, signedIn],
  );

  /** Completes, marks as missed, or cancels one of the doctor's appointments. */
  const changeAppointment = useCallback(
    async (appointmentId: number, status: "COMPLETED" | "NO_SHOW" | "CANCELLED") => {
      if (!signedIn || changingAppointmentId !== null) return;
      setChangingAppointmentId(appointmentId);
      setNotice(null);
      try {
        await api.updateAppointment(appointmentId, { status });
        setNotice({
          tone: "success",
          text: status === "COMPLETED" ? "Visit marked as completed." : status === "NO_SHOW" ? "Marked as a missed visit." : "Appointment cancelled; the patient was told.",
        });
        await reload();
      } catch (error) {
        setNotice({ tone: "error", text: error instanceof Error ? error.message : "Unable to update the appointment." });
      } finally {
        if (mountedRef.current) setChangingAppointmentId(null);
      }
    },
    [changingAppointmentId, reload, signedIn],
  );

  return {
    changeAppointment,
    changingAppointmentId,
    profile,
    overview,
    isLoading,
    notice,
    selectedPatientId,
    selectPatient: setSelectedPatientId,
    unlock,
    isUnlocking,
    endAccess,
    endingPatientId,
  };
}
