"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api } from "@/lib/api";
import type {
  Appointment,
  DailyVital,
  DepartmentTile,
  DoctorOption,
  HealthFlags,
  MedicalDocument,
  MedicationSchedule,
  MedicineReminder,
  PatientVitals,
} from "@/lib/types";

export type PatientWorkspaceData = {
  /** Report count per department, across all of the patient's reports. */
  departmentTiles: DepartmentTile[];
  /** The newest high-risk reports (up to HIGH_RISK_SHOWN) and how many there are in all. */
  highRiskReports: MedicalDocument[];
  highRiskTotal: number;
  vitalsToday: DailyVital | null;
  basicVitals: PatientVitals[];
  doctors: DoctorOption[];
  appointments: Appointment[];
  medications: MedicationSchedule[];
  reminders: MedicineReminder[];
  /** null: the flags could not be loaded (shown as an error, never as "nothing flagged"). */
  healthFlags: HealthFlags | null;
};

// The report list itself is paged by useReportList; this hook loads the summaries.
const APPOINTMENTS_LOADED = 20;
const HIGH_RISK_SHOWN = 5;

const EMPTY: PatientWorkspaceData = {
  departmentTiles: [],
  highRiskReports: [],
  highRiskTotal: 0,
  vitalsToday: null,
  basicVitals: [],
  doctors: [],
  appointments: [],
  medications: [],
  reminders: [],
  healthFlags: null,
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
    const [vitalsToday, departmentTiles, highRisk, doctors, appointments, medications, reminders, healthFlags, basicVitals] =
      await Promise.all([
        api.patientVitalsToday(token).catch(() => null),
        api.patientDepartmentTiles(token).catch(() => []),
        api.reports(token, { limit: HIGH_RISK_SHOWN, validationStatus: "HIGH_RISK" }).catch(() => ({ items: [], total: 0 })),
        api.doctors(token).catch(() => []),
        api.appointments(token, { limit: APPOINTMENTS_LOADED }).then((page) => page.items).catch(() => []),
        api.medicines(token).catch(() => []),
        api.remindersToday(token).catch(() => []),
        api.healthFlags(token).catch(() => null),
        api.basicVitalsHistory(token).catch(() => []),
      ]);
    if (!mountedRef.current) return;
    setData({
      vitalsToday,
      departmentTiles,
      highRiskReports: highRisk.items,
      highRiskTotal: highRisk.total,
      doctors,
      appointments,
      medications,
      reminders,
      healthFlags,
      basicVitals,
    });
  }, [token]);

  useEffect(() => {
    if (!token) return;
    void refresh().finally(() => {
      if (mountedRef.current) setIsLoading(false);
    });
  }, [token, refresh]);

  return { data, isLoading, refresh };
}
