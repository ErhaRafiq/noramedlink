"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { HomeVisitChecklist, HomeVisitChoice, HomeVisitCheck, HomeVisitCreate, PatientHomeVisit } from "@/lib/types";

const fail = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback);

/** What the page shows instead of the form after the server answers. Nothing is saved for the first two. */
export type RequestStop =
  | { kind: "emergency"; message: string; flags: string[] }
  | { kind: "clinic"; message: string; specialty: string | null };

/** The safety checklist questions, loaded once. */
export function useChecklist() {
  const [checklist, setChecklist] = useState<HomeVisitChecklist | null>(null);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    api
      .homeVisitChecklist()
      .then((data) => live && setChecklist(data))
      .catch((err: unknown) => live && setError(fail(err, "The safety questions could not be loaded.")));
    return () => {
      live = false;
    };
  }, [attempt]);

  const retry = useCallback(() => {
    setError("");
    setAttempt((n) => n + 1);
  }, []);

  return { checklist, error, retry };
}

/**
 * Sending a request, or searching for doctors to choose from. The server runs the emergency gate first; an
 * emergency or a clinic-only answer comes back as `stop` and nothing is saved.
 */
export function useHomeVisitRequest(onCreated: (visit: PatientHomeVisit) => void) {
  const [pending, setPending] = useState<"search" | "send" | null>(null);
  const [error, setError] = useState("");
  const [stop, setStop] = useState<RequestStop | null>(null);
  const [choices, setChoices] = useState<HomeVisitChoice[] | null>(null);

  const search = useCallback(async (check: HomeVisitCheck) => {
    setPending("search");
    setError("");
    try {
      const result = await api.searchHomeVisitDoctors(check);
      if (result.outcome === "emergency") setStop({ kind: "emergency", message: result.message, flags: result.red_flags });
      else if (result.outcome === "not_suitable") setStop({ kind: "clinic", message: result.message, specialty: result.specialty });
      else setChoices(result.doctors);
    } catch (err) {
      setError(fail(err, "Doctors could not be searched. Please try again."));
    } finally {
      setPending(null);
    }
  }, []);

  const send = useCallback(
    async (payload: HomeVisitCreate) => {
      setPending("send");
      setError("");
      try {
        const result = await api.requestHomeVisit(payload);
        if (result.outcome === "emergency") setStop({ kind: "emergency", message: result.message, flags: result.red_flags });
        else if (result.outcome === "not_suitable") setStop({ kind: "clinic", message: result.message, specialty: result.specialty });
        else if (result.visit) onCreated(result.visit);
      } catch (err) {
        setError(fail(err, "The request could not be sent. Please try again."));
      } finally {
        setPending(null);
      }
    },
    [onCreated],
  );

  return {
    pending,
    error,
    stop,
    choices,
    search,
    send,
    clearChoices: () => setChoices(null),
    startOver: () => {
      setStop(null);
      setChoices(null);
      setError("");
    },
  };
}
