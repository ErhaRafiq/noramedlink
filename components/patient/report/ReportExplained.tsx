"use client";

import { useRef } from "react";
import { AlertOctagon, BookOpen, MessageCircleQuestion, Sparkles } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Badge, type BadgeTone } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/spinner";
import { useReportExplanation } from "@/hooks/patient/use-report-explanation";
import type { ExplainPosition, ExplainResult } from "@/lib/types";
import { ReportAsk } from "./ReportAsk";
import { ReportCard } from "./ReportSections";
import { ResultGauge } from "./ResultGauge";

const POSITION: Record<ExplainPosition, { label: string; tone: BadgeTone }> = {
  above: { label: "Higher than the usual range", tone: "warning" },
  below: { label: "Lower than the usual range", tone: "warning" },
  within: { label: "Inside the usual range", tone: "success" },
  unknown: { label: "No usual range to compare", tone: "neutral" },
  unreadable: { label: "Could not be read", tone: "neutral" },
};

function ResultRow({ item, onMore, busy }: { item: ExplainResult; onMore: (item: ExplainResult) => void; busy: boolean }) {
  const position = POSITION[item.position];
  return (
    <li className="rounded-control border border-line p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <h4 className="break-words text-sm font-semibold text-ink">{item.name}</h4>
          {item.name.toLowerCase() !== item.medical_name.toLowerCase() ? (
            <p className="break-words text-xs text-ink-muted">Written on your report as &ldquo;{item.medical_name}&rdquo;</p>
          ) : null}
        </div>
        <div className="flex flex-col items-start gap-1 sm:items-end">
          {item.printed ? <p className="text-sm font-semibold text-ink">{item.printed}</p> : null}
          <Badge tone={item.urgent ? "danger" : position.tone}>{position.label}</Badge>
        </div>
      </div>
      {item.gauge ? <ResultGauge gauge={item.gauge} position={item.position} label={`${item.name}: ${item.where}`} /> : null}
      <p className="mt-2 text-sm leading-6 text-slate-700">{item.where}</p>
      {item.what_it_is ? <p className="mt-2 text-sm leading-6 text-slate-600">{item.what_it_is}</p> : null}
      {item.meaning ? <p className="mt-2 text-sm leading-6 text-slate-700">{item.meaning}</p> : null}
      {item.note ? <p className="mt-2 text-xs leading-5 text-ink-muted">{item.note}</p> : null}
      {item.urgent && item.urgent_note ? (
        <p role="alert" className="mt-2 rounded-control bg-rose-50 p-3 text-sm font-medium text-rose-900">
          {item.urgent_note}
        </p>
      ) : null}
      <Button variant="ghost" size="sm" className="mt-2 !whitespace-normal text-left" disabled={busy} onClick={() => onMore(item)}>
        <MessageCircleQuestion className="h-4 w-4 flex-shrink-0" aria-hidden />
        Explain {item.name.toLowerCase()} more
      </Button>
    </li>
  );
}

function ExplainSkeleton() {
  return (
    <div role="status" aria-label="Explaining your report" className="space-y-3">
      <Skeleton className="h-16" />
      <Skeleton className="h-28" />
      <Skeleton className="h-28" />
    </div>
  );
}

/** The report in everyday words: where every result sits, what it is, what a higher or lower one can be linked to,
 * and a box to ask for more. Written by fixed rules from the report; never a diagnosis. */
export function ReportExplained({ reportId, signedIn, reloadKey }: { reportId: number; signedIn: boolean; reloadKey?: unknown }) {
  const chat = useReportExplanation(signedIn, reportId, reloadKey);
  const askRef = useRef<HTMLDivElement>(null);
  const { explanation } = chat;

  function more(item: ExplainResult) {
    askRef.current?.scrollIntoView({ block: "nearest" });
    void chat.ask(`Explain my ${item.name} result in more detail`, item.key);
  }

  return (
    <ReportCard icon={Sparkles} title="Your report in simple words" description="Explained without medical terms">
      {chat.status === "loading" ? (
        <ExplainSkeleton />
      ) : chat.status === "error" || !explanation ? (
        <ErrorState message={chat.error} onRetry={chat.retry} />
      ) : (
        <div className="space-y-5">
          <Alert tone="info" title="Written by a computer program, not a doctor">
            {explanation.disclaimer}
          </Alert>
          <p className="whitespace-pre-line text-sm leading-7 text-ink">{explanation.headline}</p>
          {explanation.attention.length > 0 ? (
            <ul className="space-y-2" aria-label="Worth noticing">
              {explanation.attention.map((a) => (
                <li
                  key={a.text}
                  className={`flex gap-2 rounded-control p-3 text-sm ${a.urgent ? "bg-rose-50 text-rose-900" : "bg-amber-50 text-amber-900"}`}
                >
                  {a.urgent ? <AlertOctagon className="mt-0.5 h-4 w-4 flex-shrink-0" aria-hidden /> : null}
                  <span className="min-w-0 break-words">{a.text}</span>
                </li>
              ))}
            </ul>
          ) : null}
          {explanation.results.length > 0 ? (
            <section aria-label="Each result">
              <h3 className="mb-2 text-sm font-semibold text-ink">Your results, one by one</h3>
              <ul className="space-y-3">
                {explanation.results.map((item) => (
                  <ResultRow key={item.key} item={item} onMore={more} busy={chat.asking} />
                ))}
              </ul>
            </section>
          ) : null}
          {explanation.insights.map((i) => (
            <section key={i.title} className="rounded-control border border-teal-100 bg-teal-50 p-4">
              <h3 className="text-sm font-semibold text-teal-900">{i.title}</h3>
              <p className="mt-1 text-sm leading-6 text-teal-950">{i.text}</p>
            </section>
          ))}
          {explanation.conditions.length > 0 || explanation.medicines.length > 0 ? (
            <section aria-label="Mentioned in the report" className="space-y-2">
              <h3 className="text-sm font-semibold text-ink">Also mentioned in the report</h3>
              {explanation.conditions.map((c) => (
                <p key={c.medical_name} className="text-sm leading-6 text-slate-700">
                  <strong className="font-semibold text-ink">{c.name}</strong>
                  {c.explain ? `: ${c.explain}` : null}
                </p>
              ))}
              {explanation.medicines.map((m) => (
                <p key={m.name} className="text-sm leading-6 text-slate-700">
                  <strong className="font-semibold text-ink">{m.name}</strong>
                  {m.details ? ` (${m.details})` : ""}
                  {m.stopped ? " - the report says this was stopped." : " - listed in the report."}
                </p>
              ))}
            </section>
          ) : null}
          {explanation.glossary.length > 0 ? (
            <details className="rounded-control border border-line">
              <summary className="flex cursor-pointer items-center gap-2 px-4 py-2.5 text-sm font-medium text-slate-700">
                <BookOpen className="h-4 w-4" aria-hidden />
                Words used in the report
              </summary>
              <dl className="space-y-2 border-t border-line p-4 text-sm">
                {explanation.glossary.map((g) => (
                  <div key={g.term}>
                    <dt className="font-semibold text-ink">
                      {g.term} <span className="font-normal text-ink-muted">- {g.plain}</span>
                    </dt>
                    <dd className="text-slate-600">{g.explain}</dd>
                  </div>
                ))}
              </dl>
            </details>
          ) : null}
          {explanation.questions.length > 0 ? (
            <section aria-label="Questions for your doctor">
              <h3 className="text-sm font-semibold text-ink">Questions you could ask your doctor</h3>
              <ul className="mt-1 list-disc space-y-1 pl-5 text-sm leading-6 text-slate-700">
                {explanation.questions.map((q) => (
                  <li key={q}>{q}</li>
                ))}
              </ul>
            </section>
          ) : null}
          {explanation.readable ? (
            <div ref={askRef}>
              <ReportAsk chat={chat} suggestions={explanation.suggestions} disclaimer={explanation.disclaimer} />
            </div>
          ) : null}
        </div>
      )}
    </ReportCard>
  );
}
