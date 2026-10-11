import { Sparkles } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton } from "@/components/ui/skeleton";
import { buildMedicalDisclaimer } from "@/lib/patient-dashboard";

export type SummaryView = {
  summary: string;
  key_findings: string[];
  risk_indicators: string[];
  recommendations: string[];
  warning?: string | null;
};

function ResultList({ title, items }: { title: string; items: string[] }) {
  return (
    <section className="rounded-card border border-line bg-white p-5 shadow-card">
      <div className="flex items-center justify-between gap-3">
        <h3 className="text-sm font-semibold text-ink">{title}</h3>
        <span className="soft-badge">{items.length}</span>
      </div>
      {items.length > 0 ? (
        <ul className="mt-3 space-y-2">
          {items.map((item) => (
            <li key={item} className="rounded-control bg-surface-soft px-3 py-2 text-sm leading-6 text-slate-700">
              {item}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm text-ink-muted">None found.</p>
      )}
    </section>
  );
}

export function SummaryResult({ result, loading }: { result: SummaryView | null; loading: boolean }) {
  if (loading) {
    return (
      <div role="status" aria-label="Generating summary" className="space-y-4 rounded-card border border-line bg-white p-5 shadow-card">
        <Skeleton className="h-4 w-40" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-full" />
        <Skeleton className="h-3 w-2/3" />
      </div>
    );
  }
  if (!result) {
    return (
      <EmptyState
        icon={Sparkles}
        title="Your summary appears here"
        description="Paste report text or use your saved reports. Numbers are kept as written and nothing is diagnosed."
      />
    );
  }
  return (
    <div className="space-y-4">
      <section className="rounded-card border border-teal-100 bg-teal-50/60 p-5">
        <h2 className="text-sm font-semibold text-ink">Summary</h2>
        <p className="mt-2 text-sm leading-7 text-slate-700">{result.summary}</p>
        <p className="mt-3 text-xs text-ink-muted">{buildMedicalDisclaimer()}</p>
      </section>
      {result.warning ? <Alert tone="warning">{result.warning}</Alert> : null}
      <ResultList title="Key findings" items={result.key_findings} />
      <ResultList title="Values to discuss with your doctor" items={result.risk_indicators} />
      <ResultList title="Suggested next steps" items={result.recommendations} />
    </div>
  );
}
