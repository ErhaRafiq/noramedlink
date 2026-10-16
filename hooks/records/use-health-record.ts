"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { HealthEntry, HealthEntryChanges, HealthEntryInput, HealthOptions } from "@/lib/types";

/** Whose list: the signed-in patient's own, or a patient a doctor holds an active access grant for. */
export type RecordScope = { role: "patient" } | { role: "doctor"; patientId: number };

const fail = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback);

/**
 * The structured allergies, diagnoses and conditions of one patient. Every change returns an error
 * message (or null on success) so the form can show it next to the field that caused it.
 */
export function useHealthRecord(scope: RecordScope, enabled = true) {
  const [entries, setEntries] = useState<HealthEntry[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [busyId, setBusyId] = useState<number | "new" | null>(null);
  const [attempt, setAttempt] = useState(0);
  const patientId = scope.role === "doctor" ? scope.patientId : null;

  useEffect(() => {
    if (!enabled) return;
    let live = true;
    const request = patientId === null ? api.healthRecord() : api.patientHealthRecord(patientId);
    request
      .then((list) => {
        if (!live) return;
        setEntries(list);
        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (!live) return;
        setError(fail(err, "The health record could not be loaded."));
        setStatus("error");
      });
    return () => {
      live = false;
    };
  }, [enabled, patientId, attempt]);

  const retry = useCallback(() => {
    setStatus("loading");
    setError("");
    setAttempt((n) => n + 1);
  }, []);

  const add = useCallback(
    async (entry: HealthEntryInput): Promise<string | null> => {
      setBusyId("new");
      try {
        const saved = patientId === null ? await api.addHealthEntry(entry) : await api.addPatientHealthEntry(patientId, entry);
        setEntries((list) => [...list, saved]);
        return null;
      } catch (err) {
        return fail(err, "The entry could not be saved.");
      } finally {
        setBusyId(null);
      }
    },
    [patientId],
  );

  const change = useCallback(
    async (id: number, changes: HealthEntryChanges): Promise<string | null> => {
      setBusyId(id);
      try {
        const saved = patientId === null ? await api.changeHealthEntry(id, changes) : await api.changePatientHealthEntry(patientId, id, changes);
        setEntries((list) => list.map((e) => (e.id === id ? saved : e)));
        return null;
      } catch (err) {
        return fail(err, "The entry could not be changed.");
      } finally {
        setBusyId(null);
      }
    },
    [patientId],
  );

  /** Patients only: hides the entry from the list. */
  const remove = useCallback(async (id: number): Promise<string | null> => {
    setBusyId(id);
    try {
      await api.removeHealthEntry(id);
      setEntries((list) => list.filter((e) => e.id !== id));
      return null;
    } catch (err) {
      return fail(err, "The entry could not be removed.");
    } finally {
      setBusyId(null);
    }
  }, []);

  return { entries, status, error, busyId, retry, add, change, remove };
}

/** Suggested names (allergies, conditions) the medication check understands; loaded once. */
export function useHealthOptions(enabled = true) {
  const [options, setOptions] = useState<HealthOptions>({ allergies: [], conditions: [] });
  useEffect(() => {
    if (!enabled) return;
    let live = true;
    api
      .healthOptions()
      .then((found) => live && setOptions(found))
      .catch(() => undefined); // suggestions are a convenience: typing a name still works without them
    return () => {
      live = false;
    };
  }, [enabled]);
  return options;
}
