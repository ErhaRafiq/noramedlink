"use client";

import { useCallback, useEffect, useState } from "react";

import { api } from "@/lib/api";
import { getSession, updateStoredUser } from "@/lib/auth";
import type { DoctorProfileInput, PatientProfileInput, Profile } from "@/lib/types";

type Saving = "account" | "patient" | "doctor" | null;
export type SaveResult = { ok: true } | { ok: false; message: string };

/** The signed-in user's own profile, with one save action per form. */
export function useProfile() {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [error, setError] = useState("");
  const [saving, setSaving] = useState<Saving>(null);
  const [loadCount, setLoadCount] = useState(0);

  useEffect(() => {
    let current = true;
    api
      .profile()
      .then((data) => {
        if (!current) return;
        setProfile(data);
        setError("");
      })
      .catch((err: unknown) => {
        if (current) setError(err instanceof Error ? err.message : "Unable to load your profile.");
      });
    return () => {
      current = false;
    };
  }, [loadCount]);

  const save = useCallback(async (kind: Exclude<Saving, null>, request: () => Promise<Profile>): Promise<SaveResult> => {
    setSaving(kind);
    try {
      const next = await request();
      setProfile(next);
      // The header and dashboards show the name; keep the stored profile in step.
      const stored = getSession()?.user;
      if (stored) updateStoredUser({ ...stored, full_name: next.account.full_name, phone: next.account.phone, is_email_verified: next.account.email_verified });
      return { ok: true };
    } catch (err) {
      return { ok: false, message: err instanceof Error ? err.message : "The profile could not be saved." };
    } finally {
      setSaving(null);
    }
  }, []);

  return {
    profile,
    error,
    saving,
    retry: () => setLoadCount((count) => count + 1),
    saveAccount: (values: { full_name: string; phone: string; email_reminders?: boolean }) => save("account", () => api.updateAccount(values)),
    savePatient: (values: PatientProfileInput) => save("patient", () => api.updatePatientProfile(values)),
    saveDoctor: (values: DoctorProfileInput) => save("doctor", () => api.updateDoctorProfile(values)),
  };
}
