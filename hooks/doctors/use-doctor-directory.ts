"use client";

import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { AppointmentDoctor } from "@/lib/types";
import { useDebouncedValue } from "@/hooks/use-debounced-value";

export const ALL_SPECIALTIES = "all";

/**
 * Verified doctors (the backend lists only admin-approved, active doctors), filtered in
 * the browser by a debounced search, a specialty and "available today".
 */
export function useDoctorDirectory() {
  const [doctors, setDoctors] = useState<AppointmentDoctor[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  const [search, setSearch] = useState("");
  const [specialty, setSpecialty] = useState(ALL_SPECIALTIES);
  const [availableToday, setAvailableToday] = useState(false);
  const debouncedSearch = useDebouncedValue(search, 200);

  useEffect(() => {
    let active = true;
    api
      .appointmentDoctors()
      .then((data) => {
        if (!active) return;
        setDoctors(data);
        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (!active) return;
        setError(err instanceof Error ? err.message : "Unable to load doctors.");
        setStatus("error");
      });
    return () => {
      active = false;
    };
  }, [attempt]);

  const specialties = useMemo(() => Array.from(new Set(doctors.map((d) => d.specialty))).sort(), [doctors]);

  const filtered = useMemo(() => {
    const query = debouncedSearch.trim().toLowerCase();
    return doctors.filter(
      (doctor) =>
        (!query || [doctor.name, doctor.specialty, doctor.location].some((text) => text.toLowerCase().includes(query))) &&
        (specialty === ALL_SPECIALTIES || doctor.specialty === specialty) &&
        (!availableToday || doctor.available_today === true),
    );
  }, [availableToday, debouncedSearch, doctors, specialty]);

  return {
    doctors: filtered,
    total: doctors.length,
    specialties,
    status,
    error,
    retry: () => {
      setStatus("loading");
      setAttempt((n) => n + 1);
    },
    filters: { search, setSearch, specialty, setSpecialty, availableToday, setAvailableToday },
  };
}
