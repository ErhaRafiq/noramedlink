"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import type { HomeVisitSettings, HomeVisitSettingsInput } from "@/lib/types";

const fail = (error: unknown, fallback: string) => (error instanceof Error ? error.message : fallback);

/** The doctor's home-visit switch, service radius and base location. */
export function useHomeVisitSettings() {
  const [settings, setSettings] = useState<HomeVisitSettings | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    let live = true;
    api
      .homeVisitSettings()
      .then((data) => live && setSettings(data))
      .catch((err: unknown) => live && setError(fail(err, "Your home-visit settings could not be loaded.")));
    return () => {
      live = false;
    };
  }, [attempt]);

  const retry = useCallback(() => {
    setError("");
    setAttempt((n) => n + 1);
  }, []);

  /** Returns an error message, or null when saved. */
  const save = useCallback(async (input: HomeVisitSettingsInput): Promise<string | null> => {
    setSaving(true);
    try {
      setSettings(await api.saveHomeVisitSettings(input));
      return null;
    } catch (err) {
      return fail(err, "The settings could not be saved.");
    } finally {
      setSaving(false);
    }
  }, []);

  return { settings, error, retry, saving, save };
}
