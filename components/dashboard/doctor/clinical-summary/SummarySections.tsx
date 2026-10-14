"use client";

import { useState } from "react";
import { AlertOctagon, AlertTriangle, Info } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/cn";
import type { ClinicalFlag, ClinicalSource, ClinicalSummaryContent } from "@/lib/types";

const TONE: Record<ClinicalFlag["severity"], { box: string; icon: typeof Info; iconClass: string; label: string }> = {
  HIGH_RISK: { box: "border-rose-300 bg-rose-50 text-rose-950", icon: AlertOctagon, iconClass: "text-rose-600", label: "High risk" },
  CAUTION: { box: "border-amber-200 bg-amber-50 text-amber-950", icon: AlertTriangle, iconClass: "text-amber-600", label: "Caution" },
  INFO: { box: "border-line bg-surface-soft text-ink", icon: Info, iconClass: "text-brand-blue", label: "Info" },
};

/** "Lab report · 2026-03-01 (printed in report)" for each source of a finding. */
export function SourceLine({ sources }: { sources: ClinicalSource[] }) {
  if (!sources.length) return null;
  const labels = sources.map((s) => {
    const name = s.kind === "vitals" ? "Vitals entered in the app" : s.title || `Report ${s.report_id}`;
    const when = s.date ? ` · ${s.date}${s.date_source ? ` (${s.date_source})` : ""}` : " · no printed date";
    const value = s.printed ? ` · ${s.printed}` : "";
    return `${name}${when}${value}`;
  });
  return <p className="mt-1 break-words text-xs opacity-75">Source: {labels.join("; ")}</p>;
}

function ShowMore({ total, limit, shown, onToggle }: { total: number; limit: number; shown: boolean; onToggle: () => void }) {
  if (total <= limit) return null;
  return (
    <button type="button" onClick={onToggle} className="mt-2 text-xs font-semibold text-brand-blue hover:underline">
      {shown ? "Show fewer" : `Show all ${total}`}
    </button>
  );
}

export function FlagList({ flags, limit, empty }: { flags: ClinicalFlag[]; limit: number; empty: string }) {
  const [all, setAll] = useState(false);
  if (!flags.length) return <p className="text-sm text-ink-muted">{empty}</p>;
  return (
    <>
      <ul className="space-y-2">
        {(all ? flags : flags.slice(0, limit)).map((flag, index) => {
          const tone = TONE[flag.severity] ?? TONE.INFO;
          const Icon = tone.icon;
          return (
            <li key={`${flag.code}-${flag.subject}-${index}`} className={cn("min-w-0 rounded-control border p-3", tone.box)}>
              <div className="flex items-start gap-2">
                <Icon className={cn("mt-0.5 h-4 w-4 flex-shrink-0", tone.iconClass)} aria-hidden />
                <div className="min-w-0 flex-1">
                  <p className="break-words text-sm font-medium leading-6">
                    <span className="sr-only">{tone.label}: </span>
                    {flag.message}
                  </p>
                  <p className="mt-0.5 break-words text-xs opacity-80">Why: {flag.reason}</p>
                  {flag.rule ? <p className="break-words text-xs opacity-70">Rule: {flag.rule}</p> : null}
                  <SourceLine sources={flag.sources} />
                </div>
              </div>
            </li>
          );
        })}
      </ul>
      <ShowMore total={flags.length} limit={limit} shown={all} onToggle={() => setAll((v) => !v)} />
    </>
  );
}

export function Section({ title, children, count }: { title: string; children: React.ReactNode; count?: number }) {
  return (
    <section aria-label={title} className="min-w-0">
      <h3 className="mb-2 flex items-center gap-2 text-sm font-semibold text-ink">
        {title}
        {typeof count === "number" && count > 0 ? <Badge>{count}</Badge> : null}
      </h3>
      {children}
    </section>
  );
}

/** Every section of one summary version, each item tied to its source. */
export function SummarySections({ content }: { content: ClinicalSummaryContent }) {
  const limit = content.section_limit ?? 5;
  const medicines = content.medications;
  const allergies = content.allergies;
  const ai = content.key_findings.source !== "rule_based";

  return (
    <div className="space-y-6">
      <Section title="Key findings">
        <div className="rounded-control border border-blue-200 bg-blue-50 p-4 text-blue-950">
          <p className="text-sm leading-7">{content.key_findings.text}</p>
          <p className="mt-2 text-xs opacity-75">
            {ai
              ? "AI-generated wording of the rule-built findings below. Advisory; verify with a clinician."
              : "Built by fixed rules from the patient's records."}
          </p>
        </div>
      </Section>

      <Section title="Abnormal results" count={content.abnormal_results.length}>
        <FlagList flags={content.abnormal_results} limit={limit} empty="No rule alerts on the latest results." />
      </Section>

      <Section title="Flags: conditions and treatment" count={content.flags.length}>
        <FlagList flags={content.flags} limit={limit} empty="No long-term conditions or ongoing treatment found." />
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Conditions mentioned in reports" count={content.conditions.length}>
          {content.conditions.length ? (
            <ul className="space-y-1.5 text-sm">
              {content.conditions.map((c) => (
                <li key={c.name} className="min-w-0">
                  <span className="font-medium text-ink">{c.name}</span>
                  {c.chronic ? <Badge tone="warning" className="ml-2">long-term</Badge> : null}
                  {c.icd10 ? <span className="ml-2 text-xs text-ink-muted">ICD-10 {c.icd10}</span> : null}
                  <SourceLine sources={c.sources} />
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-muted">None mentioned.</p>
          )}
          {content.family_history.length ? (
            <p className="mt-2 text-xs text-ink-muted">
              Family history (not the patient&apos;s): {content.family_history.map((f) => f.name + (f.relatives?.length ? ` (${f.relatives.join(", ")})` : "")).join(", ")}
            </p>
          ) : null}
        </Section>

        <Section title="Medicines">
          {medicines.from_reports.length || medicines.from_app.length ? (
            <ul className="space-y-1.5 text-sm">
              {medicines.from_reports.map((m, i) => (
                <li key={`r-${m.medicine}-${i}`} className="break-words">
                  <span className="font-medium text-ink">{m.medicine}</span> {[m.dose, m.frequency].filter(Boolean).join(", ")}
                  <span className="text-xs text-ink-muted"> · latest report list</span>
                </li>
              ))}
              {medicines.from_app.map((m, i) => (
                <li key={`a-${m.name}-${i}`} className="break-words">
                  <span className="font-medium text-ink">{m.name}</span> {m.dosage}
                  <span className="text-xs text-ink-muted"> · entered in the app ({m.list})</span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="text-sm text-ink-muted">None recorded.</p>
          )}
          {medicines.stopped_in_reports.length ? (
            <p className="mt-2 text-xs text-ink-muted">Marked stopped in reports: {medicines.stopped_in_reports.join(", ")}</p>
          ) : null}
        </Section>
      </div>

      <Section title="Allergies">
        {allergies.status === "not_recorded" ? (
          <p className="text-sm font-medium text-amber-800">Not recorded in any report.</p>
        ) : (
          <ul className="space-y-1.5 text-sm">
            {allergies.items.map((a) => (
              <li key={a.name}>
                <span className="font-medium text-rose-800">{a.name}</span> <span className="text-xs text-ink-muted">mentioned in report</span>
                <SourceLine sources={a.sources} />
              </li>
            ))}
            {allergies.no_known_allergies_in.length ? (
              <li className="text-ink-muted">
                &ldquo;No known allergies&rdquo; in {allergies.no_known_allergies_in.length} report(s)
                {allergies.items.length ? " (reports disagree: check with the patient)" : ""}
              </li>
            ) : null}
          </ul>
        )}
      </Section>

      {content.check_original.length ? (
        <Section title="Check against the original report" count={content.check_original.length}>
          <FlagList flags={content.check_original} limit={limit} empty="" />
        </Section>
      ) : null}

      <Section title="Missing data">
        {content.missing_data.length ? (
          <ul className="list-disc space-y-1 pl-5 text-sm text-ink-muted">
            {content.missing_data.map((m) => (
              <li key={m}>{m}</li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-ink-muted">Nothing missing that the rules check for.</p>
        )}
      </Section>
    </div>
  );
}
