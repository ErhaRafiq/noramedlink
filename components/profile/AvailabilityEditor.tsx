"use client";

import { useEffect, useState } from "react";
import { CalendarPlus, Copy, Trash2 } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Card, CardHeader } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { api } from "@/lib/api";
import type { Availability } from "@/lib/types";
import { Notice, type NoticeState } from "./Notice";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
type Row = { key: number; weekday: number; start: string; end: string; slot: number };

const hhmm = (value: string) => value.slice(0, 5);
const minutes = (value: string) => Number(value.slice(0, 2)) * 60 + Number(value.slice(3, 5));

/** Why these rows cannot be saved, or null. The server checks the same rules. */
function problem(rows: Row[]): string | null {
  for (const row of rows) {
    if (!row.start || !row.end) return `Set a start and end time for ${DAYS[row.weekday]}.`;
    if (minutes(row.end) <= minutes(row.start)) return `${DAYS[row.weekday]}: a window must end after it starts.`;
    if (minutes(row.end) - minutes(row.start) < row.slot) return `${DAYS[row.weekday]}: a window must fit at least one appointment.`;
  }
  for (let day = 0; day < 7; day++) {
    const ordered = rows.filter((r) => r.weekday === day).sort((a, b) => minutes(a.start) - minutes(b.start));
    for (let i = 1; i < ordered.length; i++) {
      if (minutes(ordered[i].start) < minutes(ordered[i - 1].end)) return `${DAYS[day]}: windows must not overlap.`;
    }
    if (ordered.length > 4) return `${DAYS[day]}: at most 4 windows a day.`;
  }
  return null;
}

/** A doctor's weekly hours. Patients can book only the appointment slots cut from these windows. */
export function AvailabilityEditor() {
  const [loaded, setLoaded] = useState<Availability | null>(null);
  const [rows, setRows] = useState<Row[]>([]);
  const [loadError, setLoadError] = useState("");
  const [saving, setSaving] = useState(false);
  const [notice, setNotice] = useState<NoticeState>(null);
  const [nextKey, setNextKey] = useState(1);

  useEffect(() => {
    let current = true;
    api
      .availability()
      .then((data) => {
        if (!current) return;
        setLoaded(data);
        setRows(data.windows.map((w, i) => ({ key: i, weekday: w.weekday, start: hhmm(w.start_time), end: hhmm(w.end_time), slot: w.slot_minutes })));
        setNextKey(data.windows.length);
      })
      .catch((err: unknown) => current && setLoadError(err instanceof Error ? err.message : "Unable to load your hours."));
    return () => {
      current = false;
    };
  }, []);

  if (loadError) return <Alert tone="error">{loadError}</Alert>;
  if (!loaded) {
    return (
      <Card>
        <div role="status" aria-label="Loading your hours" className="space-y-3">
          <Skeleton className="h-6 w-1/3" />
          <Skeleton className="h-32 w-full" />
        </div>
      </Card>
    );
  }
  const availability = loaded;

  function add(weekday: number) {
    setRows((current) => [...current, { key: nextKey, weekday, start: "09:00", end: "13:00", slot: 30 }]);
    setNextKey((n) => n + 1);
    setNotice(null);
  }
  function update(key: number, patch: Partial<Row>) {
    setRows((current) => current.map((r) => (r.key === key ? { ...r, ...patch } : r)));
    setNotice(null);
  }
  function remove(key: number) {
    setRows((current) => current.filter((r) => r.key !== key));
    setNotice(null);
  }
  function copyMondayToWeekdays() {
    const monday = rows.filter((r) => r.weekday === 0);
    if (!monday.length) return;
    const others = rows.filter((r) => r.weekday > 4 || r.weekday === 0);
    const copies = [1, 2, 3, 4].flatMap((weekday, d) => monday.map((r, i) => ({ ...r, weekday, key: nextKey + d * 10 + i })));
    setRows([...others, ...copies]);
    setNextKey(nextKey + 100);
    setNotice(null);
  }

  async function save() {
    const message = problem(rows);
    if (message) {
      setNotice({ tone: "error", text: message });
      return;
    }
    setSaving(true);
    try {
      const saved = await api.setAvailability(
        rows.map((r) => ({ weekday: r.weekday, start_time: r.start, end_time: r.end, slot_minutes: r.slot })),
      );
      setLoaded(saved);
      setNotice({
        tone: "success",
        text: rows.length ? "Your weekly hours were saved. Patients can book the open times now." : "Your hours were cleared. Patients cannot book you until you add some.",
      });
    } catch (err) {
      setNotice({ tone: "error", text: err instanceof Error ? err.message : "The hours could not be saved." });
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card id="hours" className="scroll-mt-24" aria-labelledby="hours-title">
      <CardHeader
        title={<span id="hours-title">Weekly hours</span>}
        description="Patients book one of the appointment times cut from these windows. Times are in Pakistan time (PKT). Appointments already booked stay as they are."
        action={
          <Button variant="ghost" size="sm" icon={<Copy className="h-4 w-4" />} onClick={copyMondayToWeekdays} disabled={!rows.some((r) => r.weekday === 0)}>
            Monday to Fri
          </Button>
        }
      />
      {rows.length === 0 ? (
        <Alert tone="warning" className="mb-4">
          No hours yet: patients cannot book you. Add a window below.
        </Alert>
      ) : null}
      <div className="space-y-3">
        {DAYS.map((name, weekday) => {
          const dayRows = rows.filter((r) => r.weekday === weekday);
          return (
            <div key={name} className="grid gap-2 rounded-control border border-line p-3 sm:grid-cols-[110px_1fr] sm:items-start">
              <p className="pt-2 text-sm font-semibold text-ink">{name}</p>
              <div className="space-y-2">
                {dayRows.length === 0 ? <p className="pt-2 text-sm text-ink-muted">Not available</p> : null}
                {dayRows.map((row) => (
                  <div key={row.key} role="group" aria-label={`${name} window`} className="flex flex-wrap items-center gap-2">
                    <label className="sr-only" htmlFor={`start-${row.key}`}>{`${name} starts`}</label>
                    <input id={`start-${row.key}`} type="time" step={900} value={row.start} onChange={(e) => update(row.key, { start: e.target.value })} className="form-field w-[7.5rem] py-2" />
                    <span className="text-ink-muted" aria-hidden>
                      to
                    </span>
                    <label className="sr-only" htmlFor={`end-${row.key}`}>{`${name} ends`}</label>
                    <input id={`end-${row.key}`} type="time" step={900} value={row.end} onChange={(e) => update(row.key, { end: e.target.value })} className="form-field w-[7.5rem] py-2" />
                    <label className="sr-only" htmlFor={`len-${row.key}`}>{`${name} appointment length`}</label>
                    <select id={`len-${row.key}`} value={row.slot} onChange={(e) => update(row.key, { slot: Number(e.target.value) })} className="form-field w-auto py-2">
                      {availability.slot_choices.map((m) => (
                        <option key={m} value={m}>
                          {m} min each
                        </option>
                      ))}
                    </select>
                    <Button variant="ghost" size="sm" onClick={() => remove(row.key)} aria-label={`Remove ${name} window`} icon={<Trash2 className="h-4 w-4" />} />
                  </div>
                ))}
                <Button variant="ghost" size="sm" onClick={() => add(weekday)} icon={<CalendarPlus className="h-4 w-4" />}>
                  Add a window
                </Button>
              </div>
            </div>
          );
        })}
      </div>
      <div className="mt-4">
        <Notice state={notice} />
        <div className="mt-3 flex justify-end">
          <Button onClick={() => void save()} loading={saving}>
            {saving ? "Saving..." : "Save weekly hours"}
          </Button>
        </div>
      </div>
    </Card>
  );
}
