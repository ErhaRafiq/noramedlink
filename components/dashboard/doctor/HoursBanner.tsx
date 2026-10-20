"use client";

import { useEffect, useState } from "react";
import { CalendarClock } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { ButtonLink } from "@/components/ui/button";
import { api } from "@/lib/api";

/** Shown to an approved doctor who has no weekly hours: patients can see them but cannot book until they set some. */
export function HoursBanner({ approved }: { approved: boolean }) {
  const [missing, setMissing] = useState(false);

  useEffect(() => {
    if (!approved) return;
    let current = true;
    api
      .availability()
      .then((data) => current && setMissing(data.windows.length === 0))
      .catch(() => undefined); // no banner is better than a wrong one
    return () => {
      current = false;
    };
  }, [approved]);

  if (!approved || !missing) return null;
  return (
    <Alert tone="warning" title="Patients cannot book you yet">
      <p>You are approved, but you have not set your weekly hours. Patients can only book the appointment times cut from them.</p>
      <ButtonLink href="/profile#hours" size="sm" className="mt-3" icon={<CalendarClock className="h-4 w-4" />}>
        Set my weekly hours
      </ButtonLink>
    </Alert>
  );
}
