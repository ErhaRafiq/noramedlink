"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { DoctorHomeVisit, DoctorHomeVisitOffer, HomeVisitCancelReason, HomeVisitSummary } from "@/lib/types";

const POLL_MS = 5_000; // offers are short (2 minutes), so the doctor's list is refreshed often
const PAGE_SIZE = 20;
export const DOCTOR_LIVE_STATES = ["accepted", "en_route", "arrived", "completed"];

const fail = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback);

/**
 * The doctor's waiting requests and visits. While the page is open the lists refresh every few seconds. Each
 * action returns an error message (or null) and refreshes both lists.
 */
export function useDoctorHomeVisits(enabled: boolean) {
  const [offers, setOffers] = useState<DoctorHomeVisitOffer[]>([]);
  const [visits, setVisits] = useState<DoctorHomeVisit[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [busyId, setBusyId] = useState<number | null>(null);

  const fetchAll = useCallback(async () => {
    const [waiting, page] = await Promise.all([api.doctorHomeVisitOffers(), api.doctorHomeVisits({ limit: PAGE_SIZE })]);
    return { waiting, visits: page.items };
  }, []);

  useEffect(() => {
    if (!enabled) return;
    let live = true;
    fetchAll()
      .then((data) => {
        if (!live) return;
        setOffers(data.waiting);
        setVisits(data.visits);
        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (!live) return;
        setError(fail(err, "Your home visits could not be loaded."));
        setStatus("error");
      });
    const timer = window.setInterval(() => {
      fetchAll()
        .then((data) => {
          if (!live) return;
          setOffers(data.waiting);
          setVisits(data.visits);
        })
        .catch(() => undefined); // a failed refresh keeps what is on screen
    }, POLL_MS);
    return () => {
      live = false;
      window.clearInterval(timer);
    };
  }, [enabled, fetchAll, attempt]);

  const retry = useCallback(() => {
    setStatus("loading");
    setError("");
    setAttempt((n) => n + 1);
  }, []);

  const run = useCallback(
    async (id: number, action: () => Promise<unknown>, fallback: string): Promise<string | null> => {
      setBusyId(id);
      try {
        await action();
        const data = await fetchAll();
        setOffers(data.waiting);
        setVisits(data.visits);
        return null;
      } catch (err) {
        // The request may have just moved on (timeout, cancelled): show the fresh lists with the message.
        void fetchAll().then((data) => {
          setOffers(data.waiting);
          setVisits(data.visits);
        }).catch(() => undefined);
        return fail(err, fallback);
      } finally {
        setBusyId(null);
      }
    },
    [fetchAll],
  );

  return {
    offers,
    visits,
    status,
    error,
    retry,
    busyId,
    live: visits.filter((v) => DOCTOR_LIVE_STATES.includes(v.status)),
    past: visits.filter((v) => !DOCTOR_LIVE_STATES.includes(v.status)),
    accept: (id: number) => run(id, () => api.acceptHomeVisit(id), "The request could not be accepted."),
    decline: (id: number) => run(id, () => api.declineHomeVisit(id), "The request could not be declined."),
    enRoute: (id: number, eta: number | null) => run(id, () => api.homeVisitEnRoute(id, eta), "The step could not be saved."),
    arrived: (id: number) => run(id, () => api.homeVisitArrived(id), "The step could not be saved."),
    complete: (id: number) => run(id, () => api.homeVisitComplete(id), "The step could not be saved."),
    close: (id: number, summary: HomeVisitSummary) => run(id, () => api.closeHomeVisit(id, summary), "The summary could not be saved."),
    cancel: (id: number, reason: HomeVisitCancelReason) => run(id, () => api.doctorCancelHomeVisit(id, reason), "The visit could not be cancelled."),
    escalate: (id: number) => run(id, () => api.escalateHomeVisit(id), "The patient could not be referred."),
  };
}
