"use client";

import { useState } from "react";
import { AlertOctagon, AlertTriangle, Info } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";
import { cn } from "@/lib/cn";
import type { LabelEvidence, MedicationCheck, RankedAlternative, SafetyAlert } from "@/lib/types";

const LEVEL = {
  HIGH_RISK: { box: "border-rose-300 bg-rose-50 text-rose-950", icon: AlertOctagon, iconClass: "text-rose-600" },
  CAUTION: { box: "border-amber-200 bg-amber-50 text-amber-950", icon: AlertTriangle, iconClass: "text-amber-600" },
  INFO: { box: "border-line bg-surface-soft text-ink", icon: Info, iconClass: "text-brand-blue" },
} as const;

const SEVERITY_LABEL: Record<string, string> = {
  contraindicated: "Contraindicated",
  major: "Major",
  moderate: "Moderate",
  minor: "Minor",
  info: "Info",
};

/** One alert: what, why (the rule and the record), what to do, and the source. */
export function AlertItem({ alert }: { alert: SafetyAlert }) {
  const tone = LEVEL[alert.level] ?? LEVEL.INFO;
  const Icon = tone.icon;
  return (
    <li className={cn("min-w-0 rounded-control border p-3", tone.box)}>
      <div className="flex items-start gap-2">
        <Icon className={cn("mt-0.5 h-4 w-4 flex-shrink-0", tone.iconClass)} aria-hidden />
        <div className="min-w-0 flex-1 text-sm">
          <p className="break-words font-semibold">
            <span className="mr-2 text-xs font-semibold uppercase tracking-wide opacity-80">{SEVERITY_LABEL[alert.severity]}</span>
            {alert.title}
          </p>
          <p className="mt-0.5 break-words leading-6">{alert.effect}</p>
          <p className="break-words text-xs">
            <span className="font-semibold">What to do:</span> {alert.management}
          </p>
          {alert.evidence.length ? <p className="mt-0.5 break-words text-xs opacity-80">Why: {alert.evidence.join("; ")}</p> : null}
          {alert.sources.length ? (
            <p className="mt-0.5 break-words text-xs opacity-70">
              Source:{" "}
              {alert.sources.map((s, i) => (
                <span key={s.label} title={s.reference}>
                  {i ? "; " : ""}
                  {s.label}
                </span>
              ))}
            </p>
          ) : null}
        </div>
      </div>
    </li>
  );
}

function AlternativeItem({ alternative, onUse }: { alternative: RankedAlternative; onUse: () => void }) {
  const worst = alternative.alerts.find((a) => a.level !== "INFO");
  return (
    <li className="min-w-0 rounded-control border border-line bg-white p-3">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-sm font-semibold text-ink">
            {alternative.rank}. {alternative.medicine}
            <span className="ml-2 text-xs font-normal text-ink-muted">for {alternative.use}</span>
          </p>
          <p className="break-words text-xs text-ink-muted">{alternative.reason}</p>
        </div>
        <Button variant="secondary" size="sm" onClick={onUse}>
          Use instead
        </Button>
      </div>
      <div className="mt-2 flex items-center gap-2" aria-label={`Score ${Math.round(alternative.score * 100)} out of 100`}>
        <div className="h-2 flex-1 overflow-hidden rounded-full bg-slate-100">
          <div className="h-full rounded-full bg-brand-teal" style={{ width: `${Math.round(alternative.score * 100)}%` }} />
        </div>
        <span className="text-xs font-semibold text-ink">{Math.round(alternative.score * 100)}</span>
      </div>
      {worst ? <p className="mt-1 text-xs text-amber-800">Still flags: {worst.title}</p> : <p className="mt-1 text-xs text-teal-800">No rule alert for this patient.</p>}
      <details className="mt-1 text-xs">
        <summary className="cursor-pointer font-medium text-brand-blue">Why this rank</summary>
        <ul className="mt-1 space-y-0.5 text-ink-muted">
          {alternative.breakdown.map((b) => (
            <li key={b.factor}>
              {b.factor.replace("_", " ")}: {b.value} × weight {b.weight} = {b.contribution} ({b.reason})
            </li>
          ))}
        </ul>
      </details>
    </li>
  );
}

function LabelText({ generic }: { generic: string }) {
  const [label, setLabel] = useState<LabelEvidence | null>(null);
  const [loading, setLoading] = useState(false);
  return (
    <details
      className="text-xs"
      onToggle={(event) => {
        if ((event.target as HTMLDetailsElement).open && !label && !loading) {
          setLoading(true);
          api
            .medicineLabel(generic)
            .then(setLabel)
            .catch((error: unknown) => setLabel({ generic, available: false, reason: error instanceof Error ? error.message : "Unavailable." }))
            .finally(() => setLoading(false));
        }
      }}
    >
      <summary className="cursor-pointer font-medium text-brand-blue">FDA label text for {generic} (supporting evidence)</summary>
      <div className="mt-1 space-y-1 text-ink-muted">
        {loading ? <p role="status">Loading…</p> : null}
        {label && !label.available ? <p>Not available: {label.reason}</p> : null}
        {label?.available
          ? Object.entries(label.sections ?? {})
              .filter(([, text]) => text)
              .map(([section, text]) => (
                <p key={section} className="break-words">
                  <span className="font-semibold">{section.replaceAll("_", " ")}:</span> {text}
                </p>
              ))
          : null}
        {label?.available ? <p className="opacity-75">{label.source}. Shown for reference; it never changes an alert.</p> : null}
      </div>
    </details>
  );
}

/** The record the check used, so the physician can see what each alert is based on (FE-5). */
export function ContextSummary({ context }: { context: MedicationCheck["context"] }) {
  const parts = [
    `Current medicines: ${context.medicines.map((m) => m.name).join(", ") || "none recorded"}`,
    `Conditions: ${context.conditions.map((c) => c.name).join(", ") || "none mentioned"}`,
    `Allergies: ${context.allergies.map((a) => a.name).join(", ") || (context.allergy_status === "none_recorded" ? "no known allergies (report)" : "not recorded")}`,
    `Labs: ${context.labs.map((l) => `${l.test} ${l.value} ${l.unit}${l.date ? ` (${l.date})` : ""}`).join(", ") || "no eGFR, potassium or creatinine"}`,
  ];
  return (
    <details className="rounded-control border border-line bg-surface-soft p-3 text-xs text-ink-muted">
      <summary className="cursor-pointer text-sm font-medium text-ink">What the check used from this patient&apos;s record</summary>
      <ul className="mt-2 space-y-1">
        {parts.map((part) => (
          <li key={part} className="break-words">
            {part}
          </li>
        ))}
      </ul>
    </details>
  );
}

/** Alerts and ranked alternatives for each medicine in the prescription. */
export function CheckPanel({ check, onUseAlternative }: { check: MedicationCheck; onUseAlternative: (index: number, medicine: string) => void }) {
  return (
    <div className="space-y-4">
      {check.items.map((item, index) => (
        <section key={`${item.medicine}-${index}`} aria-label={`Safety check: ${item.medicine}`} className="min-w-0 space-y-2">
          <h4 className="flex flex-wrap items-center gap-2 text-sm font-semibold text-ink">
            {item.medicine}
            {item.resolved.known && item.resolved.name.toLowerCase() !== item.medicine.toLowerCase() ? (
              <span className="font-normal text-ink-muted">({item.resolved.generics.join(" + ")})</span>
            ) : null}
            {item.worst === null ? <Badge tone="success">No rule alerts</Badge> : null}
          </h4>
          {item.alerts.length ? (
            <ul className="space-y-2">
              {item.alerts.map((alert) => (
                <AlertItem key={alert.id} alert={alert} />
              ))}
            </ul>
          ) : (
            <p className="text-xs text-ink-muted">No allergy, interaction, duplicate, contraindication or dose rule matched. No rule alert does not mean safe.</p>
          )}
          {item.resolved.known ? <LabelText generic={item.resolved.generics[0]} /> : null}
          {item.alternatives.length ? (
            <div className="rounded-control border border-teal-100 bg-teal-50/60 p-3">
              <p className="mb-2 text-sm font-semibold text-teal-900">Safer alternatives for this patient, ranked</p>
              <ul className="space-y-2">
                {item.alternatives.map((alternative) => (
                  <AlternativeItem key={alternative.medicine} alternative={alternative} onUse={() => onUseAlternative(index, alternative.medicine)} />
                ))}
              </ul>
              <p className="mt-2 text-xs text-teal-900/80">Suggestions only: each one is re-checked for this patient. The choice is yours.</p>
            </div>
          ) : null}
        </section>
      ))}
    </div>
  );
}
