"use client";

import { useEffect, useState } from "react";

/** The current time as a number, refreshed every `everyMs` while `active` (for a countdown). */
export function useNow(active: boolean, everyMs = 1000) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (!active) return;
    const timer = window.setInterval(() => setNow(Date.now()), everyMs);
    return () => window.clearInterval(timer);
  }, [active, everyMs]);
  return now;
}
