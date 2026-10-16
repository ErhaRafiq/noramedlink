"use client";

import { useMemo, useState } from "react";
import { CalendarX2 } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useDoctorSlots } from "@/hooks/doctors/use-doctor-slots";
import { cn } from "@/lib/cn";
import { clinicDay, clinicTime } from "@/lib/datetime";

/**
 * The doctor's open times for the next two weeks: pick a day, then a time. Days with nothing open are
 * left out; taken times stay visible but cannot be chosen, so the patient sees why a time is missing.
 */
export function SlotPicker({
  doctorId,
  selected,
  onSelect,
  busy = [],
}: {
  doctorId: number;
  selected: string | null;
  onSelect: (start: string) => void;
  /** The patient's own live visits (with any doctor): overlapping times are closed, as the server refuses them. */
  busy?: { start: string; end: string }[];
}) {
  const { days: rawDays, loading, error, reload } = useDoctorSlots(doctorId);
  const days = useMemo(() => {
    const spans = busy.map((b) => [new Date(b.start).getTime(), new Date(b.end).getTime()] as const);
    return rawDays.map((d) => ({
      ...d,
      slots: d.slots.map((s) => {
        const from = new Date(s.start).getTime();
        const to = new Date(s.end).getTime();
        return spans.some(([a, b]) => from < b && to > a) ? { ...s, available: false } : s;
      }),
    }));
  }, [rawDays, busy]);
  const bookable = useMemo(() => days.filter((d) => d.slots.some((s) => s.available)), [days]);
  const [chosenDay, setChosenDay] = useState<string | null>(null);
  const day = bookable.find((d) => d.day === chosenDay) ?? bookable.find((d) => d.slots.some((s) => s.start === selected)) ?? bookable[0];

  if (loading) {
    return (
      <div role="status" aria-label="Loading times" className="space-y-3">
        <Skeleton className="h-10 w-full" />
        <Skeleton className="h-24 w-full" />
      </div>
    );
  }
  if (error) {
    return (
      <Alert tone="error">
        {error}{" "}
        <Button variant="ghost" size="sm" onClick={reload} className="ml-1 px-2">
          Try again
        </Button>
      </Alert>
    );
  }
  if (!day) {
    return (
      <div className="rounded-control border border-dashed border-line p-5 text-center">
        <CalendarX2 className="mx-auto h-6 w-6 text-slate-400" aria-hidden />
        <p className="mt-2 text-sm font-medium text-ink">No open times in the next two weeks</p>
        <p className="mt-0.5 text-xs text-ink-muted">The doctor has not published availability yet, or every time is taken. Check again later.</p>
      </div>
    );
  }

  return (
    <div>
      <div role="tablist" aria-label="Day" className="-mx-1 flex gap-2 overflow-x-auto px-1 pb-2">
        {bookable.map((d) => {
          const open = d.slots.filter((s) => s.available).length;
          const active = d.day === day.day;
          return (
            <button
              key={d.day}
              type="button"
              role="tab"
              aria-selected={active}
              onClick={() => setChosenDay(d.day)}
              className={cn(
                "flex-shrink-0 rounded-control border px-3 py-2 text-left transition-colors",
                active ? "border-brand-blue bg-blue-50 text-brand-blue" : "border-line bg-white text-slate-700 hover:border-line-strong",
              )}
            >
              <span className="block text-sm font-semibold">{clinicDay(d.slots[0].start)}</span>
              <span className="block text-xs opacity-80">{open} open</span>
            </button>
          );
        })}
      </div>
      <div role="group" aria-label={`Times on ${clinicDay(day.slots[0].start)}`} className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-4">
        {day.slots.map((slot) => {
          const isSelected = slot.start === selected;
          return (
            <button
              key={slot.start}
              type="button"
              disabled={!slot.available}
              aria-pressed={isSelected}
              onClick={() => onSelect(slot.start)}
              className={cn(
                "min-h-[40px] rounded-control border px-2 py-2 text-sm font-medium transition-colors focus-visible:ring-2 focus-visible:ring-brand-blue",
                isSelected && "border-brand-blue bg-brand-blue text-white",
                !isSelected && slot.available && "border-line bg-white text-ink hover:border-brand-blue hover:text-brand-blue",
                !slot.available && "cursor-not-allowed border-transparent bg-surface-soft text-slate-400 line-through",
              )}
            >
              {clinicTime(slot.start)}
            </button>
          );
        })}
      </div>
      <p className="mt-2 text-xs text-ink-muted">Times are in Pakistan time (PKT). Crossed-out times are taken, too soon, or clash with one of your own visits.</p>
    </div>
  );
}
