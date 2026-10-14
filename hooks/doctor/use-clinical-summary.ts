"use client";

import { useCallback, useEffect, useRef, useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { ClinicalSummaryStatus, ClinicalSummaryVersion, ClinicalSummaryVersionMeta } from "@/lib/types";

/** "current": up to date. "updating": out of date (or none yet), a new version is being built.
 * "update-failed": out of date and the update failed: the previous version is shown, labelled. */
export type SummaryPhase = "loading" | "error" | "current" | "updating" | "update-failed";

function message(error: unknown) {
  if (error instanceof ApiError) return error.message;
  return "The clinical summary could not be loaded. Check the connection and try again.";
}

/**
 * A patient's clinical summary for the doctor. When it is out of date (or there is none yet), the
 * previous version stays on screen, labelled, while a new one is built automatically; if that
 * fails, the previous one stays, labelled with its date, never silently. Switching patients drops
 * answers that arrive late.
 */
export function useClinicalSummary(token: string | null, patientId: number | null) {
  const [phase, setPhase] = useState<SummaryPhase>("loading");
  const [status, setStatus] = useState<ClinicalSummaryStatus | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [versions, setVersions] = useState<ClinicalSummaryVersionMeta[] | null>(null);
  const [viewing, setViewing] = useState<ClinicalSummaryVersion | null>(null);
  const [viewError, setViewError] = useState<string | null>(null);
  const controller = useRef<AbortController | null>(null);

  const regenerate = useCallback(
    async (signal?: AbortSignal) => {
      if (!token || patientId === null) return;
      setPhase("updating");
      setError(null);
      try {
        const result = await api.regenerateClinicalSummary(token, patientId, { signal });
        if (signal?.aborted) return;
        setStatus({ patient_id: patientId, summary: result.summary, out_of_date: false, pending_change: null });
        setPhase("current");
        setVersions(null); // the list changed: reloaded when opened
      } catch (caught) {
        if (signal?.aborted) return;
        setError(message(caught));
        setPhase("update-failed");
      }
    },
    [token, patientId],
  );

  // The card is keyed by patient, so this hook starts fresh ("loading") for each patient; state is
  // only set from the answers, which are dropped once the patient changes or the card closes.
  const [loadCount, setLoadCount] = useState(0);
  useEffect(() => {
    if (!token || patientId === null) return;
    const current = new AbortController();
    controller.current = current;
    api
      .clinicalSummary(token, patientId, { signal: current.signal })
      .then(async (loaded) => {
        if (current.signal.aborted) return;
        setStatus(loaded);
        if (loaded.out_of_date) await regenerate(current.signal);
        else setPhase("current");
      })
      .catch((caught: unknown) => {
        if (current.signal.aborted) return;
        setError(message(caught));
        setPhase("error");
      });
    return () => current.abort();
  }, [token, patientId, loadCount, regenerate]);

  const load = useCallback(() => {
    setPhase("loading");
    setError(null);
    setLoadCount((n) => n + 1);
  }, []);

  const loadVersions = useCallback(async () => {
    if (!token || patientId === null) return;
    try {
      const page = await api.clinicalSummaryVersions(token, patientId, { limit: 50 });
      setVersions(page.items);
    } catch (caught) {
      setViewError(message(caught));
    }
  }, [token, patientId]);

  const viewVersion = useCallback(
    async (version: number | null) => {
      setViewError(null);
      if (!token || patientId === null || version === null || version === status?.summary?.version) {
        setViewing(null);
        return;
      }
      try {
        setViewing(await api.clinicalSummaryVersion(token, patientId, version));
      } catch (caught) {
        setViewError(message(caught));
      }
    },
    [token, patientId, status],
  );

  return {
    phase,
    status,
    error,
    versions,
    viewing,
    viewError,
    reload: load,
    regenerate: () => void regenerate(controller.current?.signal),
    loadVersions,
    viewVersion,
  };
}
