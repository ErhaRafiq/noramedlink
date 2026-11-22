"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type {
  BodyMeasurement,
  BodyMeasurementChanges,
  BodyMeasurementInput,
  BodySummary,
  DoctorBodySummary,
  PregnancyState,
  PregnancyStatus,
} from "@/lib/types";
import type { RecordScope } from "./use-health-record";

const PAGE_SIZE = 20;

const fail = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback);

/**
 * The weight and height history of one patient, the latest values with the BMI, and the pregnancy status.
 * Scope: the signed-in patient's own, or a patient a doctor holds an active access grant for (403 otherwise).
 * Every change returns an error message (or null on success) so the form can show it beside the field.
 */
export function useBodyMeasurements(scope: RecordScope) {
  const patientId = scope.role === "doctor" ? scope.patientId : null;
  const [rows, setRows] = useState<BodyMeasurement[]>([]);
  const [total, setTotal] = useState(0);
  const [summary, setSummary] = useState<BodySummary | DoctorBodySummary | null>(null);
  const [pregnancy, setPregnancy] = useState<PregnancyState | null>(null);
  const [gender, setGender] = useState<string | null>(null);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | "new" | "pregnancy" | "more" | null>(null);
  const [attempt, setAttempt] = useState(0);

  // Fetches the first page and the summary (and, for the patient, the profile's pregnancy status and gender).
  const fetchAll = useCallback(async () => {
    const [page, found] = await Promise.all([
      patientId === null ? api.bodyHistory({ limit: PAGE_SIZE }) : api.patientBodyHistory(patientId, { limit: PAGE_SIZE }),
      patientId === null ? api.bodySummary() : api.patientBodySummary(patientId),
    ]);
    if (patientId !== null) return { page, found, pregnancy: (found as DoctorBodySummary).pregnancy, gender: null };
    const profile = await api.profile();
    return { page, found, pregnancy: profile.patient?.pregnancy ?? null, gender: profile.patient?.gender ?? null };
  }, [patientId]);

  const apply = useCallback((data: Awaited<ReturnType<typeof fetchAll>>) => {
    setRows(data.page.items);
    setTotal(data.page.total);
    setSummary(data.found);
    setPregnancy(data.pregnancy);
    setGender(data.gender);
  }, []);

  // Used after every change so the numbers never go stale.
  const load = useCallback(async () => apply(await fetchAll()), [apply, fetchAll]);

  useEffect(() => {
    let live = true;
    fetchAll()
      .then((data) => {
        if (!live) return;
        apply(data);
        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (!live) return;
        setError(fail(err, "The weight and height record could not be loaded."));
        setStatus("error");
      });
    return () => {
      live = false;
    };
  }, [fetchAll, apply, attempt]);

  const retry = useCallback(() => {
    setStatus("loading");
    setError("");
    setAttempt((n) => n + 1);
  }, []);

  const loadMore = useCallback(async (): Promise<string | null> => {
    setBusyId("more");
    try {
      const page = await (patientId === null
        ? api.bodyHistory({ limit: PAGE_SIZE, offset: rows.length })
        : api.patientBodyHistory(patientId, { limit: PAGE_SIZE, offset: rows.length }));
      setRows((list) => [...list, ...page.items]);
      setTotal(page.total);
      return null;
    } catch (err) {
      return fail(err, "More readings could not be loaded.");
    } finally {
      setBusyId(null);
    }
  }, [patientId, rows.length]);

  const run = useCallback(
    async (key: number | "new" | "pregnancy", action: () => Promise<unknown>, fallback: string): Promise<string | null> => {
      setBusyId(key);
      try {
        await action();
        await load();
        return null;
      } catch (err) {
        return fail(err, fallback);
      } finally {
        setBusyId(null);
      }
    },
    [load],
  );

  const add = useCallback(
    (input: BodyMeasurementInput) =>
      run("new", () => (patientId === null ? api.addBodyMeasurement(input) : api.addPatientBodyMeasurement(patientId, input)), "The reading could not be saved."),
    [patientId, run],
  );

  const change = useCallback(
    (id: number, changes: BodyMeasurementChanges) =>
      run(
        id,
        () => (patientId === null ? api.changeBodyMeasurement(id, changes) : api.changePatientBodyMeasurement(patientId, id, changes)),
        "The reading could not be changed.",
      ),
    [patientId, run],
  );

  const remove = useCallback(
    (id: number) =>
      run(id, () => (patientId === null ? api.removeBodyMeasurement(id) : api.removePatientBodyMeasurement(patientId, id)), "The reading could not be removed."),
    [patientId, run],
  );

  const setPregnancyStatus = useCallback(
    (next: PregnancyStatus) =>
      run(
        "pregnancy",
        () => (patientId === null ? api.setPregnancyStatus(next) : api.setPatientPregnancyStatus(patientId, next)),
        "The pregnancy status could not be saved.",
      ),
    [patientId, run],
  );

  return { rows, total, summary, pregnancy, gender, status, error, busyId, retry, loadMore, add, change, remove, setPregnancyStatus };
}
