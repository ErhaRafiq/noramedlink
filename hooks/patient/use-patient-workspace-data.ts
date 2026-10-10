"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type {
  Appointment,
  DailyVital,
  DoctorOption,
  DoctorSummary,
  HealthRiskPrediction,
  MedicalDocument,
  MedicationSchedule,
  MedicineReminder,
  PatientVitals,
} from "@/lib/types";

export type PatientWorkspaceData = {
  reports: MedicalDocument[];
  vitalsToday: DailyVital | null;
  basicVitals: PatientVitals[];
  doctors: DoctorOption[];
  appointments: Appointment[];
  medications: MedicationSchedule[];
  reminders: MedicineReminder[];
  riskPredictions: HealthRiskPrediction[];
  doctorSummaries: DoctorSummary[];
};

// The dashboard loads the newest reports and appointments; paging controls come in U4.
const REPORTS_LOADED = 100;
const APPOINTMENTS_LOADED = 20;

const EMPTY: PatientWorkspaceData = {
  reports: [],
  vitalsToday: null,
  basicVitals: [],
  doctors: [],
  appointments: [],
  medications: [],
  reminders: [],
  riskPredictions: [],
  doctorSummaries: [],
};

/**
 * Everything the patient dashboard shows, loaded in parallel. A section that fails to
 * load shows its empty state instead of breaking the page. `refresh()` reloads it all;
 * results that arrive after the page is gone are dropped.
 */
export function usePatientWorkspaceData(token: string | null) {
  const [data, setData] = useState<PatientWorkspaceData>(EMPTY);
  const [isLoading, setIsLoading] = useState(true);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;
    return () => {
      mountedRef.current = false;
    };
  }, []);

  const refresh = useCallback(async () => {
    if (!token) return;
    const [vitalsToday, reports, doctors, appointments, medications, reminders, riskPredictions, doctorSummaries, basicVitals] =
      await Promise.all([
        api.patientVitalsToday(token).catch(() => null),
        api.reports(token, { limit: REPORTS_LOADED }).then((page) => page.items).catch(() => []),
        api.doctors(token).catch(() => []),
        api.appointmentsV2(token, { limit: APPOINTMENTS_LOADED }).then((page) => page.items).catch(() => []),
        api.medicines(token).catch(() => []),
        api.remindersToday(token).catch(() => []),
        api.riskPredictions(token).catch(() => []),
        api.doctorSummaries(token).catch(() => []),
        api.basicVitalsHistory(token).catch(() => []),
      ]);
    if (!mountedRef.current) return;
    setData({ vitalsToday, reports, doctors, appointments, medications, reminders, riskPredictions, doctorSummaries, basicVitals });
  }, [token]);

  useEffect(() => {
    if (!token) return;
    void refresh().finally(() => {
      if (mountedRef.current) setIsLoading(false);
    });
  }, [token, refresh]);

  /** Puts a just-uploaded report at the top without waiting for a full reload. */
  const addReport = useCallback((report: MedicalDocument) => {
    setData((current) => ({ ...current, reports: [report, ...current.reports.filter((r) => r.id !== report.id)] }));
  }, []);

  return { data, isLoading, refresh, addReport };
}
