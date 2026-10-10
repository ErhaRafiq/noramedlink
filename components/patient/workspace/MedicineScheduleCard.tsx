"use client";

import { ArrowRight, BellOff, BellRing, Check, Minus } from "lucide-react";

import { cn } from "@/lib/cn";
import type { MedicineReminder } from "@/lib/types";
import type { NotificationPermissionState } from "@/hooks/use-browser-notifications";
import { formatTime, getReminderDisplay } from "./helpers";
import { DashCard } from "./ui";

const SCHEDULE_PREVIEW = 6;

export function MedicineScheduleCard({
  reminders,
  permission,
  onEnablePopups,
  onMark,
  onSeeAll,
}: {
  reminders: MedicineReminder[];
  permission: NotificationPermissionState;
  onEnablePopups: () => void;
  onMark: (reminderId: number, action: "taken" | "skip") => void;
  onSeeAll: () => void;
}) {
  return (
    <section id="medications">
      <DashCard>
        <div className="flex items-center justify-between mb-1">
          <div>
            <h2 className="text-sm font-black text-slate-900">Today&apos;s Medicine Schedule</h2>
            <ReminderPopupStatus permission={permission} onEnable={onEnablePopups} />
          </div>
          <button type="button" onClick={onSeeAll} className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1 transition">
            See all <ArrowRight className="h-3 w-3" />
          </button>
        </div>
        <div className="mt-4 space-y-2.5">
          {reminders.length === 0 ? (
            <p className="p-3 text-sm text-slate-500">No medicine reminders scheduled for today.</p>
          ) : (
            reminders.slice(0, SCHEDULE_PREVIEW).map((r) => {
              const display = getReminderDisplay(r);
              const name = r.medication?.medicine_name ?? "Medication";
              return (
                <div key={r.id} className="flex items-center gap-4 p-3 rounded-2xl bg-slate-50 border border-slate-100 hover:border-blue-100 transition">
                  <p className="text-[11px] font-black text-slate-500 w-14 flex-shrink-0 text-center">{formatTime(r.reminder_time)}</p>
                  <div className="h-7 w-px bg-slate-200 flex-shrink-0" />
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-bold text-slate-900 truncate">{name}</p>
                    <p className="text-xs text-slate-400">{r.frequency}</p>
                  </div>
                  <span className={cn("text-[11px] font-black px-3 py-1 rounded-full flex-shrink-0", display.tone)}>{display.label}</span>
                  <div className="flex gap-1.5">
                    <button
                      type="button"
                      onClick={() => onMark(r.id, "taken")}
                      aria-label={`Mark ${name} as taken`}
                      className="h-7 w-7 rounded-lg bg-white border border-slate-200 flex items-center justify-center text-emerald-600 hover:bg-emerald-50 hover:border-emerald-200 transition"
                    >
                      <Check className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      onClick={() => onMark(r.id, "skip")}
                      aria-label={`Skip ${name}`}
                      className="h-7 w-7 rounded-lg bg-white border border-slate-200 flex items-center justify-center text-slate-400 hover:bg-slate-50 transition"
                    >
                      <Minus className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>
              );
            })
          )}
        </div>
        <button
          type="button"
          onClick={onSeeAll}
          className="mt-4 w-full py-2.5 rounded-xl border border-blue-100 bg-blue-50/50 text-sm font-semibold text-blue-600 hover:bg-blue-50 transition"
        >
          View full schedule
        </button>
      </DashCard>
    </section>
  );
}

function ReminderPopupStatus({ permission, onEnable }: { permission: NotificationPermissionState; onEnable: () => void }) {
  if (permission === "unsupported") return null;
  if (permission === "granted") {
    return (
      <p className="text-[11px] text-slate-400 mt-0.5 flex items-center gap-1.5">
        <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 inline-block" />
        Browser pop-ups are on while this page is open
      </p>
    );
  }
  if (permission === "denied") {
    return (
      <p className="text-[11px] text-slate-400 mt-0.5 flex items-center gap-1.5">
        <BellOff className="h-3 w-3" />
        Pop-ups are blocked in your browser settings
      </p>
    );
  }
  return (
    <button type="button" onClick={onEnable} className="text-[11px] font-semibold text-blue-600 hover:text-blue-700 mt-0.5 flex items-center gap-1.5 transition">
      <BellRing className="h-3 w-3" />
      Turn on browser pop-ups
    </button>
  );
}
