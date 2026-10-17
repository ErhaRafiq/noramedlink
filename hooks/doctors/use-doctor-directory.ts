"use client";

import { useEffect, useMemo, useState } from "react";

import { api } from "@/lib/api";
import type { AppointmentDoctor, ConsultationMode, DoctorSearch, DoctorSort } from "@/lib/types";
import { useDebouncedValue } from "@/hooks/use-debounced-value";

export const ALL_SPECIALTIES = "all";

/**
 * Verified doctors (the backend lists only admin-approved, active doctors). Search, specialty, city,
 * consultation type, price, rating, availability and sorting are applied by the server, so the
 * ratings, fees and next open times shown are always real.
 */
export function useDoctorDirectory() {
  const [doctors, setDoctors] = useState<AppointmentDoctor[]>([]);
  const [specialties, setSpecialties] = useState<string[]>([]);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);
  const [everLoaded, setEverLoaded] = useState(0);

  const [search, setSearch] = useState("");
  const [specialty, setSpecialty] = useState(ALL_SPECIALTIES);
  const [city, setCity] = useState("");
  const [mode, setMode] = useState<ConsultationMode | "">("");
  const [availableToday, setAvailableToday] = useState(false);
  const [pmdcVerified, setPmdcVerified] = useState(false);
  const [maxFee, setMaxFee] = useState("");
  const [minRating, setMinRating] = useState("");
  const [sort, setSort] = useState<DoctorSort>("soonest");
  const debouncedSearch = useDebouncedValue(search, 250);
  const debouncedCity = useDebouncedValue(city, 250);
  const debouncedFee = useDebouncedValue(maxFee, 400);

  const request = useMemo<DoctorSearch>(
    () => ({
      query: debouncedSearch,
      specialty: specialty === ALL_SPECIALTIES ? undefined : specialty,
      city: debouncedCity,
      mode: mode || undefined,
      availableToday,
      maxFee: debouncedFee && Number(debouncedFee) > 0 ? Number(debouncedFee) : undefined,
      minRating: minRating ? Number(minRating) : undefined,
      sort,
      pmdcVerified,
    }),
    [availableToday, debouncedCity, debouncedFee, debouncedSearch, minRating, mode, pmdcVerified, sort, specialty],
  );
  const filtered = useMemo(
    () => Boolean(request.query || request.specialty || request.city || request.mode || request.availableToday || request.maxFee || request.minRating || request.pmdcVerified),
    [request],
  );

  useEffect(() => {
    const controller = new AbortController();
    api
      .appointmentDoctors(request, { signal: controller.signal })
      .then((data) => {
        setDoctors(data);
        setSpecialties((known) => Array.from(new Set([...known, ...data.map((d) => d.specialty)])).sort());
        setEverLoaded((n) => n + 1);
        setError("");
        setStatus("ready");
      })
      .catch((err: unknown) => {
        if (controller.signal.aborted) return;
        setError(err instanceof Error ? err.message : "Unable to load doctors.");
        setStatus("error");
      });
    return () => controller.abort();
  }, [request, attempt]);

  return {
    doctors,
    specialties,
    status,
    error,
    filtered,
    hasLoaded: everLoaded > 0,
    retry: () => {
      setStatus("loading");
      setAttempt((n) => n + 1);
    },
    reset: () => {
      setSearch("");
      setSpecialty(ALL_SPECIALTIES);
      setCity("");
      setMode("");
      setAvailableToday(false);
      setPmdcVerified(false);
      setMaxFee("");
      setMinRating("");
    },
    filters: {
      search, setSearch, specialty, setSpecialty, city, setCity, mode, setMode,
      availableToday, setAvailableToday, pmdcVerified, setPmdcVerified, maxFee, setMaxFee, minRating, setMinRating, sort, setSort,
    },
  };
}
