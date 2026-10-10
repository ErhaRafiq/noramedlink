import { HeartPulse } from "lucide-react";

import type { DoctorSummary } from "@/lib/types";
import { DISCLAIMER, formatDate } from "./helpers";
import { DashCard } from "./ui";

export function AiSummaryCard({ summary }: { summary: DoctorSummary | undefined }) {
  return (
    <DashCard className="relative overflow-hidden">
      <div className="absolute top-0 right-0 w-52 h-52 rounded-full bg-gradient-to-br from-blue-300/20 to-violet-300/20 blur-3xl pointer-events-none" />
      <div className="relative">
        <div className="flex items-center justify-between mb-5">
          <h2 className="text-sm font-black text-slate-900">AI Health Summary</h2>
          {summary ? (
            <span className="text-[11px] bg-violet-50 text-violet-600 font-bold px-2.5 py-1 rounded-full border border-violet-100">
              Generated {formatDate(summary.generated_at)}
            </span>
          ) : null}
        </div>
        <div className="flex gap-5 items-start">
          <div className="flex-shrink-0 flex items-center justify-center">
            <div className="relative h-28 w-28" aria-hidden>
              <div className="absolute inset-0 rounded-full bg-gradient-to-br from-blue-400/25 to-violet-400/25 animate-pulse" />
              <div className="absolute inset-3 rounded-full bg-gradient-to-br from-blue-400/15 to-violet-400/15" />
              <div className="absolute inset-6 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 shadow-[0_0_28px_rgba(99,102,241,0.45)] flex items-center justify-center">
                <HeartPulse className="h-8 w-8 text-white" />
              </div>
              <svg className="absolute inset-0 w-full h-full opacity-50" viewBox="0 0 112 112">
                <path
                  d="M14,56 Q22,38 30,56 Q38,74 46,56 Q54,38 62,56 Q70,74 78,56 Q86,38 94,56 Q102,74 110,56"
                  fill="none"
                  stroke="rgba(99,102,241,0.5)"
                  strokeWidth="1.5"
                />
              </svg>
            </div>
          </div>
          <div className="flex-1 min-w-0">
            <p className="text-sm leading-6 text-slate-600">{summary?.summary_text || "No AI summary yet. Upload a report to generate one."}</p>
          </div>
        </div>
        <p className="mt-4 text-[11px] text-slate-400 leading-5">{DISCLAIMER}</p>
      </div>
    </DashCard>
  );
}
