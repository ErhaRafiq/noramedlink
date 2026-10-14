"use client";

import { useState } from "react";
import Link from "next/link";
import { AlertOctagon, AlertTriangle, ArrowRight, HeartPulse, Shield } from "lucide-react";

import { cn } from "@/lib/cn";
import type { HealthFlags } from "@/lib/types";
import { RISKS_PREVIEW, formatDate } from "./helpers";
import { DashCard } from "./ui";

/** What the app's fixed rules found in the patient's own reports, in everyday words: red for
 * prompt attention, amber for points to discuss, and the conditions their reports mention. */
export function HealthFlagsCard({ flags, onRetry }: { flags: HealthFlags | null; onRetry: () => void }) {
  const [showAll, setShowAll] = useState(false);

  return (
    <DashCard id="insights">
      <div className="mb-4 flex items-center justify-between gap-3">
        <h2 className="text-base font-semibold text-ink">Health flags</h2>
        {flags && !showAll && flags.reports.length > RISKS_PREVIEW && (
          <button type="button" onClick={() => setShowAll(true)} className="flex items-center gap-1 text-xs font-semibold text-brand-blue transition hover:underline">
            View all ({flags.reports.length}) <ArrowRight className="h-3 w-3" aria-hidden />
          </button>
        )}
      </div>

      {flags === null ? (
        <div role="status" className="rounded-control border border-line bg-surface-soft p-3 text-sm text-ink-muted">
          Health flags could not be loaded.{" "}
          <button type="button" onClick={onRetry} className="font-semibold text-brand-blue hover:underline">
            Try again
          </button>
        </div>
      ) : (
        <>
          {flags.reports.length === 0 ? (
            <p className="rounded-control border border-line bg-surface-soft p-3 text-sm text-ink-muted">
              The app&apos;s checks have not marked anything in your reports. That does not mean everything is normal.
            </p>
          ) : (
            <ul className="space-y-3">
              {(showAll ? flags.reports : flags.reports.slice(0, RISKS_PREVIEW)).map((report) => {
                const urgent = report.severity === "HIGH_RISK";
                const Icon = urgent ? AlertOctagon : AlertTriangle;
                return (
                  <li
                    key={report.report_id}
                    className={cn(
                      "min-w-0 rounded-control border p-3.5",
                      urgent ? "border-rose-300 bg-rose-50 text-rose-900" : "border-amber-200 bg-amber-50 text-amber-900",
                    )}
                  >
                    <div className="flex items-start gap-2">
                      <Icon className={cn("mt-0.5 h-4 w-4 flex-shrink-0", urgent ? "text-rose-600" : "text-amber-600")} aria-hidden />
                      <div className="min-w-0 flex-1">
                        <p className="text-xs font-semibold uppercase tracking-wide">
                          {urgent ? "Needs prompt attention" : "To go over with your doctor"}
                        </p>
                        <Link href={`/dashboard/patient/reports/${report.report_id}`} className="mt-0.5 block break-words text-sm font-semibold hover:underline">
                          {report.report_title}
                        </Link>
                        <p className="text-xs opacity-80">Uploaded {formatDate(report.upload_date)}</p>
                        <ul className="mt-1.5 space-y-1 text-sm leading-6">
                          {report.messages.slice(0, 3).map((message, index) => (
                            <li key={index} className="break-words">
                              {message}
                            </li>
                          ))}
                          {report.messages.length > 3 && <li className="text-xs opacity-80">and {report.messages.length - 3} more on the report page</li>}
                        </ul>
                      </div>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}

          {flags.conditions_mentioned.length > 0 && (
            <div className="mt-4 rounded-control border border-blue-200 bg-blue-50 p-3.5 text-blue-950">
              <p className="flex items-center gap-2 text-sm font-semibold">
                <HeartPulse className="h-4 w-4 text-brand-blue" aria-hidden />
                Conditions mentioned in your reports
              </p>
              <ul className="mt-2 flex flex-wrap gap-2">
                {flags.conditions_mentioned.map((condition) => (
                  <li
                    key={condition.name}
                    className={cn(
                      "min-w-0 break-words rounded-full border bg-white px-3 py-1 text-xs font-semibold",
                      condition.chronic ? "border-amber-300 text-amber-900" : "border-blue-200 text-blue-900",
                    )}
                  >
                    {condition.plain.charAt(0).toUpperCase() + condition.plain.slice(1)}
                    {condition.chronic && <span className="ml-1 font-normal">· long-term</span>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </>
      )}

      <div className="mt-4 flex items-start gap-2.5 rounded-control border border-emerald-100 bg-emerald-50 p-3.5">
        <Shield className="mt-0.5 h-4 w-4 flex-shrink-0 text-emerald-600" aria-hidden />
        <p className="text-xs font-medium leading-5 text-emerald-700">
          From the app&apos;s fixed checks on your reports. Not a diagnosis: please go over these with your doctor.
        </p>
      </div>
    </DashCard>
  );
}
