"use client";

import { Badge } from "@/components/ui/badge";
import type { ClinicalBody } from "@/lib/types";

const PREGNANCY = { pregnant: "Pregnant", not_pregnant: "Not pregnant", not_recorded: "Not recorded" } as const;

function Line({ label, value, detail }: { label: string; value: string | null; detail?: string }) {
  return (
    <li className="min-w-0 break-words">
      <span className="text-ink-muted">{label}: </span>
      {value ? <span className="font-medium text-ink">{value}</span> : <span className="font-medium text-amber-800">Not recorded</span>}
      {detail ? <span className="text-xs text-ink-muted"> · {detail}</span> : null}
    </li>
  );
}

/** Body measurements of the clinical summary: every value with its date and who entered it; nothing is assumed. */
export function BodySection({ body }: { body: ClinicalBody }) {
  const { weight, height, bmi, pregnancy } = body;
  return (
    <div className="space-y-2">
      <ul className="space-y-1.5 text-sm">
        <Line label="Weight" value={weight ? `${weight.value} kg` : null} detail={weight ? `${weight.date}, entered by ${weight.entered_by}` : undefined} />
        <Line label="Height" value={height ? `${height.value} cm` : null} detail={height ? `${height.date}, entered by ${height.entered_by}` : undefined} />
        <Line
          label="BMI"
          value={bmi ? `${bmi.value} kg/m²` : null}
          detail={bmi ? (bmi.band ?? bmi.band_note ?? undefined) : weight && !height ? "needs a height" : undefined}
        />
      </ul>
      {weight && body.weight_current === false ? (
        <p className="text-xs font-medium text-amber-800">
          <Badge tone="warning" className="mr-1.5">
            Out of date
          </Badge>
          Older than {body.weight_max_age_days} days ({body.app_rule}); re-measure before weight-based dose checks.
        </p>
      ) : null}
      {bmi?.asian_note ? <p className="text-xs leading-5 text-ink-muted">{bmi.asian_note}</p> : null}
      {body.weight_history.length > 1 ? (
        <p className="break-words text-xs text-ink-muted">
          Weight history: {body.weight_history.map((h) => `${h.value} kg (${h.date})`).join(", ")}.
        </p>
      ) : null}
      {body.weight_change_flags.length === 0 && body.change_since_previous ? (
        <p className="text-xs text-ink-muted">
          Change since the previous reading: {body.change_since_previous.percent > 0 ? "+" : ""}
          {body.change_since_previous.percent}% ({body.change_since_previous.from_date} to {body.change_since_previous.to_date}).
        </p>
      ) : null}
      <p className="text-sm">
        <span className="text-ink-muted">Pregnancy status: </span>
        <span className="font-medium text-ink">{PREGNANCY[pregnancy.status]}</span>
        {pregnancy.set_on ? <span className="text-xs text-ink-muted"> · set {pregnancy.set_on} by the {pregnancy.set_by_role}</span> : null}
        {pregnancy.expired ? <span className="text-xs text-amber-800"> · the &ldquo;pregnant&rdquo; status is older than {pregnancy.max_months} months ({body.app_rule}) and counts as not recorded</span> : null}
      </p>
      <p className="text-xs text-ink-muted">Weight-change flags appear under Flags. Rule-based, for physician review.</p>
    </div>
  );
}
