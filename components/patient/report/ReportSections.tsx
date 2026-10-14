import type { ReactNode } from "react";
import { FileText, ShieldCheck, Sparkles, type LucideIcon } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty-state";
import { Skeleton, SkeletonCard } from "@/components/ui/skeleton";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/datetime";
import { buildMedicalDisclaimer, summaryOrigin, validationLabel } from "@/lib/patient-dashboard";
import type { MedicalDocument, UncertainValue } from "@/lib/types";

/** A titled card used by every section of the report page. */
export function ReportCard({ icon: Icon, title, description, children }: { icon?: LucideIcon; title: string; description?: string; children: ReactNode }) {
  return (
    <section className="rounded-card border border-line bg-white p-5 shadow-card sm:p-6">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-ink">{title}</h2>
          {description ? <p className="mt-0.5 text-sm text-ink-muted">{description}</p> : null}
        </div>
        {Icon ? <Icon className="h-5 w-5 flex-shrink-0 text-brand-blue" aria-hidden /> : null}
      </div>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-control border border-line bg-surface-soft px-4 py-3">
      <dt className="text-xs font-medium text-ink-muted">{label}</dt>
      <dd className="mt-1 break-words text-sm font-semibold capitalize text-ink">{value}</dd>
    </div>
  );
}

export function ReportStats({ report }: { report: MedicalDocument }) {
  return (
    <dl className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <Stat label="Text reading" value={report.ocr_status.replaceAll("_", " ").toLowerCase()} />
      <Stat label="Reading confidence" value={typeof report.ocr_confidence === "number" ? `${Math.round(report.ocr_confidence * 100)}%` : "Not available"} />
      <Stat label="File type" value={report.file_type.toUpperCase()} />
      <Stat label="Validation" value={validationLabel(report.validation_status)} />
    </dl>
  );
}

export function ReportFilePreview({ report, fileUrl }: { report: MedicalDocument; fileUrl: string }) {
  const isPdf = report.file_type.toLowerCase().includes("pdf");
  return (
    <ReportCard icon={FileText} title="Original file" description={report.original_filename}>
      {fileUrl ? (
        <div className="overflow-hidden rounded-control border border-line bg-surface-soft">
          {isPdf ? (
            <iframe src={fileUrl} title={report.title} className="h-[560px] w-full bg-white" />
          ) : (
            // Signed, short-lived link to a private file: next/image cannot optimise it.
            // eslint-disable-next-line @next/next/no-img-element
            <img src={fileUrl} alt={`Uploaded file: ${report.title}`} className="max-h-[560px] w-full object-contain" />
          )}
        </div>
      ) : (
        <EmptyState title="File not available" description="The original file could not be found for this report." />
      )}
    </ReportCard>
  );
}

function structuredFields(report: MedicalDocument) {
  const fields = report.structured_data_json?.fields ?? report.structured_sections ?? {};
  return Object.entries(fields).filter(([, value]) => String(value ?? "").trim().length > 0);
}

function label(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

const WARNING_TONES: Record<string, string> = {
  HIGH_RISK: "border-rose-100 bg-rose-50 text-rose-900",
  CAUTION: "border-amber-100 bg-amber-50 text-amber-900",
};

/** What was extracted from the report: fields, medical terms and rule warnings. */
export function ReportExtraction({ report }: { report: MedicalDocument }) {
  const fields = structuredFields(report);
  const entities = report.extracted_entities ?? report.structured_data_json?.bio_bert_entities ?? [];
  const warnings = report.rule_warnings ?? report.structured_data_json?.rule_warnings ?? [];
  const uncertain = report.structured_data_json?.uncertain_values ?? [];

  return (
    <>
      {uncertain.length > 0 ? <UncertainValues values={uncertain} /> : null}
      <ReportCard title="Extracted values" description="Fields read from the report text.">
        {fields.length > 0 ? (
          <div className="overflow-hidden rounded-control border border-line">
            <table className="w-full text-left text-sm">
              <tbody>
                {fields.map(([key, value]) => (
                  <tr key={key} className="border-b border-line last:border-0">
                    <th scope="row" className="w-44 bg-surface-soft px-4 py-2.5 font-medium text-slate-700">
                      {label(key)}
                    </th>
                    <td className="px-4 py-2.5 text-slate-600">{String(value)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <EmptyState title="No values found" description="The text is saved, but no labelled values were recognised." />
        )}
      </ReportCard>

      <ReportCard icon={Sparkles} title="Medical terms" description="Diseases, medicines, symptoms and lab values the model recognised.">
        {entities.length > 0 ? (
          <ul className="flex flex-wrap gap-2">
            {entities.slice(0, 24).map((entity, index) => (
              <li key={`${entity.text}-${entity.label}-${index}`} className="rounded-full border border-blue-100 bg-blue-50 px-3 py-1 text-xs text-blue-900">
                <span className="font-semibold">{entity.text}</span> · {entity.label}
                {typeof entity.confidence === "number" ? ` · ${Math.round(entity.confidence * 100)}%` : ""}
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState title="No terms recognised" />
        )}
      </ReportCard>

      <ReportCard icon={ShieldCheck} title="Rule checks" description="Values outside common reference ranges, checked by fixed rules.">
        {warnings.length > 0 ? (
          <ul className="space-y-2">
            {warnings.map((warning, index) => (
              <li
                key={`${warning.code}-${index}`}
                className={cn("rounded-control border p-3 text-sm", WARNING_TONES[warning.severity ?? ""] ?? "border-teal-100 bg-teal-50 text-teal-900")}
              >
                <p className="font-semibold">{warning.patient_message ?? warning.message}</p>
                {warning.patient_message && warning.patient_message !== warning.message ? (
                  <p className="mt-1 text-xs opacity-80">For your doctor: {warning.message}</p>
                ) : null}
                {warning.evidence ? <p className="mt-1 text-xs opacity-80">From the report: {warning.evidence}</p> : null}
              </li>
            ))}
          </ul>
        ) : (
          <EmptyState title="No rule warnings" description="No value in this report triggered a rule." />
        )}
      </ReportCard>
    </>
  );
}

/** Numbers OCR was unsure of. They are shown exactly as read; the rules do not rely on them. */
function UncertainValues({ values }: { values: UncertainValue[] }) {
  return (
    <Alert tone="warning" title="Check these numbers against the original report">
      <p>The scan was hard to read here, so these numbers may be wrong. They are shown exactly as read. If one is wrong, correct it in the report text.</p>
      <ul className="mt-2 space-y-1">
        {values.slice(0, 12).map((value, index) => (
          <li key={`${value.line}-${value.text}-${index}`} className="break-words">
            <span className="font-semibold">{value.text}</span>
            <span className="opacity-80"> in &ldquo;{value.line}&rdquo;{value.page ? ` (page ${value.page})` : ""}</span>
          </li>
        ))}
      </ul>
      {values.length > 12 ? <p className="mt-1 opacity-80">and {values.length - 12} more</p> : null}
    </Alert>
  );
}

function SummaryList({ title, values }: { title: string; values: string[] }) {
  return (
    <div className="rounded-control border border-line bg-surface-soft p-4">
      <h3 className="text-xs font-semibold uppercase tracking-wide text-ink-muted">{title}</h3>
      {values.length > 0 ? (
        <ul className="mt-2 space-y-1.5 text-sm leading-6 text-slate-700">
          {values.slice(0, 4).map((value) => (
            <li key={value}>{value}</li>
          ))}
        </ul>
      ) : (
        <p className="mt-2 text-sm text-ink-muted">None found.</p>
      )}
    </div>
  );
}

/** The text could not be read, so there is nothing to summarise yet: say why and what to do. */
function UnreadReport({ report }: { report: MedicalDocument }) {
  const reason = report.structured_data_json?.error;
  return (
    <ReportCard icon={Sparkles} title="Summary" description={`Uploaded ${formatDateTime(report.upload_date)}`}>
      <EmptyState
        icon={FileText}
        title="The text of this file could not be read"
        description={`${reason ? `${reason} ` : ""}Try "Read file again", or type the report text under "Correct the report" and save: the summary and rule checks are then built from your text.`}
      />
    </ReportCard>
  );
}

/** The readable text and the summaries, with the note that matches where the summary came from. */
export function ReportSummary({ report }: { report: MedicalDocument }) {
  const clinical = report.clinical_summary_json ?? report.structured_data_json?.ai_summary ?? {};
  const summaryText = clinical.summary || report.summary || report.ai_summary;
  const textRead = report.ocr_status !== "FAILED" || Boolean((report.extracted_text ?? "").trim());
  if (!textRead) return <UnreadReport report={report} />;
  const aiWritten = Boolean(report.summary_source) && report.summary_source !== "rule_based";
  // Older reports did not record who wrote the plain-language summary: fall back to the clinical one's source.
  const plain = summaryOrigin(report.patient_summary_source ?? report.summary_source);
  return (
    <ReportCard icon={Sparkles} title="Summary" description={`Uploaded ${formatDateTime(report.upload_date)}`}>
      {report.patient_summary ? (
        <div className="rounded-control border border-emerald-100 bg-emerald-50 p-4">
          <h3 className="text-xs font-semibold uppercase tracking-wide text-emerald-800">In plain language</h3>
          <p className="mt-0.5 text-xs text-emerald-800/80">{plain.label}</p>
          <p className="mt-2 whitespace-pre-line text-sm leading-7 text-emerald-950">{report.patient_summary}</p>
          <p className="mt-3 text-xs leading-5 text-emerald-900/70">{plain.note}</p>
        </div>
      ) : null}
      {/* The clinical wording is for the doctor; the patient reads the plain-language summary above. */}
      <details className="mt-3 rounded-control border border-teal-100 bg-teal-50" open={!report.patient_summary}>
        <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-teal-900">Details for your doctor (medical wording)</summary>
        <div className="border-t border-teal-100 p-4">
          <p className="whitespace-pre-line text-sm leading-7 text-teal-950">{summaryText || "No summary is available for this report yet."}</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            <SummaryList title="Key findings" values={clinical.key_findings ?? []} />
            <SummaryList title="Conditions mentioned" values={clinical.detected_diseases ?? []} />
            <SummaryList title="Medicines mentioned" values={clinical.medicines ?? []} />
            <SummaryList title="Doctor notes" values={clinical.doctor_notes ?? []} />
          </div>
        </div>
      </details>
      <p className="mt-4 text-xs leading-5 text-ink-muted">
        {aiWritten
          ? buildMedicalDisclaimer()
          : "Built by fixed rules from the report text, not by AI. Advisory only; this is not a diagnosis. Verify with a clinician."}
      </p>

      <details className="mt-4 rounded-control border border-line">
        <summary className="cursor-pointer px-4 py-2.5 text-sm font-medium text-slate-700">Show the text read from the file</summary>
        <pre className="max-h-[420px] overflow-auto whitespace-pre-wrap border-t border-line bg-surface-soft p-4 text-sm leading-7 text-slate-700">
          {report.formatted_text || report.ocr_cleaned_text || "No readable text is available yet."}
        </pre>
      </details>
    </ReportCard>
  );
}

export function ReportDetailSkeleton() {
  return (
    <div role="status" aria-label="Loading the report" className="space-y-6">
      <div className="space-y-3">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-8 w-2/3" />
        <Skeleton className="h-3 w-48" />
      </div>
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        {Array.from({ length: 4 }, (_, i) => (
          <Skeleton key={i} className="h-16" />
        ))}
      </div>
      <div className="grid gap-6 xl:grid-cols-2">
        <SkeletonCard lines={8} />
        <SkeletonCard lines={8} />
      </div>
    </div>
  );
}
