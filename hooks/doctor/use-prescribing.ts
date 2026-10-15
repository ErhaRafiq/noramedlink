"use client";

import { useCallback, useEffect, useMemo, useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { MedicationCheck, MedicineOption, Prescription, PrescriptionItemInput } from "@/lib/types";
import { useDebouncedValue } from "@/hooks/use-debounced-value";

export type DraftItem = PrescriptionItemInput & { key: string };

const CHECK_DELAY_MS = 400;

function message(error: unknown, fallback: string) {
  return error instanceof ApiError || error instanceof Error ? error.message : fallback;
}

/**
 * The prescription being written for one patient: the items, the live safety check (re-run as the
 * items change, older answers dropped), confirming with justifications, and the history.
 * The card is keyed by patient, so this starts fresh for each one.
 */
export function usePrescribing(patientId: number) {
  const [items, setItems] = useState<DraftItem[]>([]);
  const [checked, setChecked] = useState<{ key: string; result: MedicationCheck | null; error: string | null }>({
    key: "",
    result: null,
    error: null,
  });
  const [history, setHistory] = useState<{ items: Prescription[]; error: string | null; loaded: boolean }>({
    items: [],
    error: null,
    loaded: false,
  });
  const [historyVersion, setHistoryVersion] = useState(0);
  const [confirming, setConfirming] = useState(false);
  const [confirmError, setConfirmError] = useState<string | null>(null);
  const [cancellingId, setCancellingId] = useState<number | null>(null);

  const payload = useMemo(
    () =>
      items
        .filter((item) => item.medicine.trim().length >= 2)
        .map((item) => ({
          medicine: item.medicine,
          dose: item.dose || undefined,
          frequency: item.frequency || undefined,
          duration: item.duration || undefined,
          instructions: item.instructions || undefined,
          replaced_medicine: item.replaced_medicine || undefined,
        })),
    [items],
  );
  const key = JSON.stringify(payload);
  const debouncedKey = useDebouncedValue(key, CHECK_DELAY_MS);

  useEffect(() => {
    if (debouncedKey === "[]") return;
    const controller = new AbortController();
    api
      .medicationCheck(patientId, JSON.parse(debouncedKey) as PrescriptionItemInput[], { signal: controller.signal })
      .then((result) => setChecked({ key: debouncedKey, result, error: null }))
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        setChecked({ key: debouncedKey, result: null, error: message(error, "The safety check could not run.") });
      });
    return () => controller.abort();
  }, [patientId, debouncedKey]);

  useEffect(() => {
    let active = true;
    api
      .prescriptions(patientId)
      .then((page) => active && setHistory({ items: page.items, error: null, loaded: true }))
      .catch((error: unknown) => active && setHistory({ items: [], error: message(error, "Earlier prescriptions could not be loaded."), loaded: true }));
    return () => {
      active = false;
    };
  }, [patientId, historyVersion]);

  const add = useCallback((option: MedicineOption) => {
    setItems((current) => [...current, { key: `${Date.now()}-${option.name}`, medicine: option.brand ?? option.generic, frequency: "OD" }]);
  }, []);
  const update = useCallback((itemKey: string, patch: Partial<PrescriptionItemInput>) => {
    setItems((current) => current.map((item) => (item.key === itemKey ? { ...item, ...patch } : item)));
  }, []);
  const remove = useCallback((itemKey: string) => setItems((current) => current.filter((item) => item.key !== itemKey)), []);
  /** The doctor chose a suggested alternative instead (the original is recorded as replaced). */
  const replace = useCallback((index: number, medicine: string) => {
    setItems((current) =>
      current.map((item, i) => (i === index ? { ...item, medicine, dose: "", replaced_medicine: item.replaced_medicine ?? item.medicine } : item)),
    );
  }, []);

  const confirm = useCallback(
    async (justifications: Record<string, string>, notes: string) => {
      setConfirming(true);
      setConfirmError(null);
      try {
        await api.createPrescription(patientId, {
          items: payload,
          overrides: Object.entries(justifications).map(([alert_id, justification]) => ({ alert_id, justification })),
          notes: notes.trim() || undefined,
        });
        setItems([]);
        setHistoryVersion((v) => v + 1);
        return true;
      } catch (error) {
        setConfirmError(message(error, "The prescription could not be saved."));
        return false;
      } finally {
        setConfirming(false);
      }
    },
    [patientId, payload],
  );

  const cancel = useCallback(
    async (prescriptionId: number) => {
      setCancellingId(prescriptionId);
      try {
        await api.cancelPrescription(patientId, prescriptionId);
        setHistoryVersion((v) => v + 1);
      } catch (error) {
        setHistory((current) => ({ ...current, error: message(error, "The prescription could not be cancelled.") }));
      } finally {
        setCancellingId(null);
      }
    },
    [patientId],
  );

  const current = payload.length > 0 && checked.key === key;
  return {
    items,
    add,
    update,
    remove,
    replace,
    check: current ? checked.result : null,
    checkError: current ? checked.error : null,
    checking: payload.length > 0 && checked.key !== key,
    confirm,
    confirming,
    confirmError,
    history,
    cancel,
    cancellingId,
  };
}
