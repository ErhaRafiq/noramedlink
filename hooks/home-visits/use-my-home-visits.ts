"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { HomeVisitStatus, LegacyHomeVisitRequest, PatientHomeVisit } from "@/lib/types";

const POLL_MS = 8_000;
const PAGE_SIZE = 20;
/** A visit in one of these states is still going: the patient sees the tracker, and the page keeps refreshing. */
export const LIVE_STATES: HomeVisitStatus[] = ["offered", "accepted", "en_route", "arrived", "completed"];

const fail = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback);

/**
 * The patient's home visits (newest first), the older requests from before the service, and the one live visit
 * if there is one. While a visit is live the list is refreshed every few seconds (a visit is never tracked on a
 * map: only its status changes).
 */
export function useMyHomeVisits() {
  const [items, setItems] = useState<PatientHomeVisit[]>([]);
  const [legacy, setLegacy] = useState<LegacyHomeVisitRequest[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState("");

  const fetchAll = useCallback(async () => {
    const [page, old] = await Promise.all([api.myHomeVisits({ limit: PAGE_SIZE }), api.legacyHomeVisits()]);
    return { visits: page.items, old };
  }, []);

  useEffect(() => {
    let live = true;
    fetchAll()
      .then((data) => {
        if (!live) return;
        setItems(data.visits);
        setLegacy(data.old);
        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (!live) return;
        setError(fail(err, "Your home visits could not be loaded."));
        setStatus("error");
      });
    return () => {
      live = false;
    };
  }, [fetchAll, attempt]);

  const active = items.find((visit) => LIVE_STATES.includes(visit.status)) ?? null;
  const activeId = active?.id ?? null;

  // Quietly refresh while a visit is live; a failed refresh keeps what is on screen.
  useEffect(() => {
    if (activeId === null) return;
    let live = true;
    const timer = window.setInterval(() => {
      api
        .myHomeVisits({ limit: PAGE_SIZE })
        .then((page) => live && setItems(page.items))
        .catch(() => undefined);
    }, POLL_MS);
    return () => {
      live = false;
      window.clearInterval(timer);
    };
  }, [activeId]);

  const retry = useCallback(() => {
    setStatus("loading");
    setError("");
    setAttempt((n) => n + 1);
  }, []);

  const refresh = useCallback(async () => {
    try {
      setItems((await api.myHomeVisits({ limit: PAGE_SIZE })).items);
    } catch {
      // the next refresh will try again
    }
  }, []);

  const cancel = useCallback(
    async (id: number) => {
      setBusy(true);
      setActionError("");
      try {
        await api.cancelHomeVisit(id);
        await refresh();
      } catch (err) {
        setActionError(fail(err, "The visit could not be cancelled."));
      } finally {
        setBusy(false);
      }
    },
    [refresh],
  );

  return { items, legacy, status, error, retry, active, refresh, cancel, busy, actionError };
}
