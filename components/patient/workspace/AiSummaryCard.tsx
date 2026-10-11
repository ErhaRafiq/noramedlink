import { Sparkles } from "lucide-react";

import type { DoctorSummary } from "@/lib/types";
import { DISCLAIMER, formatDate } from "./helpers";
import { DashCard } from "./ui";

export function AiSummaryCard({ summary }: { summary: DoctorSummary | undefined }) {
  return (
    <DashCard className="flex flex-col">
      <div className="flex items-start justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="grid h-9 w-9 place-items-center rounded-control bg-teal-50 text-teal-700">
            <Sparkles className="h-4 w-4" aria-hidden />
          </span>
          <h2 className="text-base font-semibold text-ink">Health summary</h2>
        </div>
        {summary ? <span className="soft-badge">Generated {formatDate(summary.generated_at)}</span> : null}
      </div>
      <p className="mt-4 flex-1 text-sm leading-7 text-slate-700">
        {summary?.summary_text || "No summary yet. Upload a report and a summary of your records will appear here."}
      </p>
      <p className="mt-4 border-t border-line pt-3 text-xs leading-5 text-ink-muted">{DISCLAIMER}</p>
    </DashCard>
  );
}
