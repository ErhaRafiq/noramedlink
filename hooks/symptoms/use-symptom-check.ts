"use client";

import { useCallback, useRef, useState } from "react";

import { api } from "@/lib/api";
import type { SymptomCheck } from "@/lib/types";

/** Runs the symptom checker. A newer check replaces an older one that is still waiting. */
export function useSymptomCheck() {
  const [result, setResult] = useState<SymptomCheck | null>(null);
  const [checking, setChecking] = useState(false);
  const [error, setError] = useState("");
  const latest = useRef(0);

  const check = useCallback(async (text: string) => {
    const mine = ++latest.current;
    setChecking(true);
    setError("");
    try {
      const found = await api.checkSymptoms(text);
      if (mine === latest.current) setResult(found);
    } catch (err) {
      if (mine === latest.current) setError(err instanceof Error ? err.message : "The symptom check could not be completed.");
    } finally {
      if (mine === latest.current) setChecking(false);
    }
  }, []);

  const reset = useCallback(() => {
    latest.current += 1;
    setResult(null);
    setError("");
    setChecking(false);
  }, []);

  return { result, checking, error, check, reset };
}
