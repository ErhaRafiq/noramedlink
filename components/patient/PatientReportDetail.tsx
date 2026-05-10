"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  FileText,
  Loader2,
  RefreshCw,
  Save,
  ShieldCheck,
  Sparkles,
  Trash2,
} from "lucide-react";

import { NoraLogo } from "@/components/ui/NoraLogo";
import { api } from "@/lib/api";
import { clearSession, getSession } from "@/lib/auth";
import { REPORT_CATEGORIES, normalizeReportCategory } from "@/lib/patient-dashboard";
import type { MedicalDocument } from "@/lib/types";

const departments = REPORT_CATEGORIES.map((category) => ({
  id: category.id,
  name: category.label,
}));

type ToastState = {
  type: "success" | "error" | "info";
  message: string;
} | null;

function formatDate(value?: string | null) {
  if (!value) {
    return "Not available";
  }
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function toastTone(type: "success" | "error" | "info") {
  if (type === "error") {
    return "border-red-100 bg-red-50 text-red-800";
  }
  if (type === "success") {
    return "border-teal-100 bg-teal-50 text-teal-800";
  }
  return "border-blue-100 bg-blue-50 text-blue-800";
}

function getStructuredFields(report: MedicalDocument | null) {
  if (!report) {
    return [];
  }
  const fields = report.structured_data_json?.fields ?? report.structured_sections ?? {};
  return Object.entries(fields).filter(([, value]) => String(value ?? "").trim().length > 0);
}

function displayLabel(value: string) {
  return value.replaceAll("_", " ").replace(/\b\w/g, (letter) => letter.toUpperCase());
}

function clinicalSummary(report: MedicalDocument | null): NonNullable<MedicalDocument["clinical_summary_json"]> {
  return report?.clinical_summary_json ?? report?.structured_data_json?.ai_summary ?? {};
}

function detectedEntities(report: MedicalDocument | null) {
  return report?.extracted_entities ?? report?.structured_data_json?.bio_bert_entities ?? [];
}

function ruleWarnings(report: MedicalDocument | null) {
  return report?.rule_warnings ?? report?.structured_data_json?.rule_warnings ?? [];
}

function warningTone(severity?: string) {
  if (severity === "HIGH_RISK") {
    return "border-red-100 bg-red-50 text-red-800";
  }
  if (severity === "CAUTION") {
    return "border-amber-100 bg-amber-50 text-amber-800";
  }
  return "border-teal-100 bg-teal-50 text-teal-800";
}

export function PatientReportDetail({ reportId }: { reportId: number }) {
  const router = useRouter();
  const [token] = useState(() => getSession()?.token ?? "");
  const [report, setReport] = useState<MedicalDocument | null>(null);
  const [editableText, setEditableText] = useState("");
  const [department, setDepartment] = useState("general");
  const [toast, setToast] = useState<ToastState>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [isRegenerating, setIsRegenerating] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  const structuredFields = useMemo(() => getStructuredFields(report), [report]);
  const summary = clinicalSummary(report);
  const entities = detectedEntities(report);
  const warnings = ruleWarnings(report);
  const fileUrl = report ? api.uploadUrl(report.stored_file_path) : "";
  const isPdf = report?.file_type.toLowerCase().includes("pdf");

  function notify(type: "success" | "error" | "info", message: string) {
    setToast({ type, message });
    window.setTimeout(() => setToast(null), 4200);
  }

  useEffect(() => {
    const session = getSession();
    if (!session) {
      router.replace("/login");
      return;
    }
    void api
      .patientDocument(session.token, reportId)
      .then((data) => {
        setReport(data);
        setEditableText(data.extracted_text ?? data.ocr_cleaned_text ?? "");
        setDepartment(normalizeReportCategory(data.category ?? data.department_slug ?? "general"));
      })
      .catch((error) => {
        notify("error", error instanceof Error ? error.message : "Unable to load report.");
        if (error instanceof Error && error.message.toLowerCase().includes("token")) {
          clearSession();
          router.replace("/login");
        }
      })
      .finally(() => setIsLoading(false));
  }, [reportId, router]);

  async function saveReport(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !report) {
      return;
    }
    if (!editableText.trim()) {
      notify("error", "OCR text cannot be empty.");
      return;
    }

    setIsSaving(true);
    try {
      const updated = await api.updateDocument(token, report.id, {
        department,
        extracted_text: editableText,
      });
      setReport(updated);
      setEditableText(updated.extracted_text ?? updated.ocr_cleaned_text ?? "");
      setDepartment(normalizeReportCategory(updated.category ?? updated.department_slug ?? department));
      notify("success", "Report text and department were saved.");
    } catch (error) {
      notify("error", error instanceof Error ? error.message : "Unable to save report.");
    } finally {
      setIsSaving(false);
    }
  }

  async function regenerateOcr() {
    if (!token || !report) {
      return;
    }
    setIsRegenerating(true);
    try {
      const updated = await api.regenerateDocumentOcr(token, report.id);
      setReport(updated);
      setEditableText(updated.extracted_text ?? updated.ocr_cleaned_text ?? "");
      setDepartment(normalizeReportCategory(updated.category ?? updated.department_slug ?? "general"));
      notify(updated.ocr_status === "FAILED" ? "error" : "success", updated.ocr_status === "FAILED" ? "OCR regeneration failed. The report was kept." : "OCR was regenerated and saved.");
    } catch (error) {
      notify("error", error instanceof Error ? error.message : "Unable to regenerate OCR.");
    } finally {
      setIsRegenerating(false);
    }
  }

  async function deleteReport() {
    if (!token || !report) {
      return;
    }
    setIsDeleting(true);
    try {
      await api.deleteDocument(token, report.id);
      router.replace("/dashboard/patient/records");
    } catch (error) {
      notify("error", error instanceof Error ? error.message : "Unable to delete report.");
      setIsDeleting(false);
    }
  }

  if (isLoading) {
    return (
      <main className="app-shell grid min-h-screen place-items-center px-4">
        <div className="glass-card p-8 text-center">
          <Loader2 className="mx-auto h-7 w-7 animate-spin text-cyan-600" />
          <p className="mt-4 text-sm font-bold text-slate-600">Loading report...</p>
        </div>
      </main>
    );
  }

  if (!report) {
    return (
      <main className="app-shell grid min-h-screen place-items-center px-4">
        <div className="dashboard-panel max-w-xl text-center">
          <AlertTriangle className="mx-auto h-7 w-7 text-amber-500" />
          <h1 className="mt-4 text-2xl font-black text-slate-950">Report not found</h1>
          <Link href="/dashboard/patient/records" className="secondary-button mt-5 gap-2">
            <ArrowLeft className="h-4 w-4" />
            Back to reports
          </Link>
        </div>
      </main>
    );
  }

  return (
    <main className="app-shell min-h-screen">
      <div className="mx-auto max-w-[1440px] space-y-6 px-4 py-5 lg:px-6">
        <header className="dashboard-topbar">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-center lg:justify-between">
            <div>
              <NoraLogo />
              <Link href="/dashboard/patient/records" className="mt-5 inline-flex items-center gap-2 text-sm font-bold text-cyan-700">
                <ArrowLeft className="h-4 w-4" />
                Back to report list
              </Link>
              <p className="section-eyebrow mt-5">Report detail</p>
              <h1 className="mt-2 text-3xl font-black tracking-tight text-slate-950">{report.title}</h1>
              <p className="mt-2 text-sm font-semibold text-slate-500">
                {report.department_name ?? report.category} | Uploaded {formatDate(report.upload_date)}
              </p>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
              <SmallDetail label="OCR status" value={report.ocr_status.replaceAll("_", " ")} />
              <SmallDetail label="Confidence" value={typeof report.ocr_confidence === "number" ? `${Math.round(report.ocr_confidence * 100)}%` : "Not available"} />
              <SmallDetail label="File type" value={report.file_type.toUpperCase()} />
              <SmallDetail label="AI validation" value={report.validation_status?.replaceAll("_", " ") ?? "SAFE"} />
            </div>
          </div>
        </header>

        {toast ? (
          <div className={`rounded-2xl border px-5 py-4 text-sm font-semibold shadow-sm ${toastTone(toast.type)}`}>
            {toast.message}
          </div>
        ) : null}

        <section className="grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
          <div className="space-y-6">
            <div className="dashboard-panel">
              <div className="mb-4 flex items-center justify-between gap-4">
                <div>
                  <p className="section-eyebrow">Uploaded file</p>
                  <h2 className="mt-2 text-2xl font-black text-slate-950">Original report preview</h2>
                </div>
                <FileText className="h-6 w-6 text-cyan-600" />
              </div>
              <div className="overflow-hidden rounded-2xl border border-slate-200 bg-slate-50">
                {isPdf ? (
                  <iframe src={fileUrl} title={report.title} className="h-[560px] w-full bg-white" />
                ) : (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img src={fileUrl} alt={report.title} className="max-h-[560px] w-full object-contain" />
                )}
              </div>
            </div>

            <div className="dashboard-panel">
              <p className="section-eyebrow">Structured medical table</p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">Extracted fields</h2>
              {structuredFields.length > 0 ? (
                <div className="mt-5 overflow-hidden rounded-2xl border border-slate-200">
                  <table className="w-full text-left text-sm">
                    <tbody>
                      {structuredFields.map(([key, value]) => (
                        <tr key={key} className="border-b border-slate-100 last:border-b-0">
                          <th className="w-48 bg-slate-50 px-4 py-3 font-black text-slate-700">{displayLabel(key)}</th>
                          <td className="px-4 py-3 font-semibold text-slate-600">{String(value)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              ) : (
                <EmptyDetail title="No structured fields" text="The OCR text is saved, but no key-value medical fields were detected." />
              )}
            </div>

            <div className="dashboard-panel">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="section-eyebrow">BioBERT entities</p>
                  <h2 className="mt-2 text-2xl font-black text-slate-950">Detected medical terms</h2>
                </div>
                <Sparkles className="h-6 w-6 text-cyan-600" />
              </div>
              {entities.length > 0 ? (
                <div className="mt-5 flex flex-wrap gap-2">
                  {entities.slice(0, 24).map((entity, index) => (
                    <span key={`${entity.text}-${entity.label}-${index}`} className="rounded-full border border-cyan-100 bg-cyan-50 px-3 py-1.5 text-xs font-black text-cyan-800">
                      {entity.text} · {entity.label} · {Math.round((entity.confidence ?? 0) * 100)}%
                    </span>
                  ))}
                </div>
              ) : (
                <EmptyDetail title="No entities detected" text="No disease, medicine, symptom, allergy, or lab-value entity was confidently extracted." />
              )}
            </div>

            <div className="dashboard-panel">
              <div className="flex items-center justify-between gap-4">
                <div>
                  <p className="section-eyebrow">Rule validation</p>
                  <h2 className="mt-2 text-2xl font-black text-slate-950">Warnings and status</h2>
                </div>
                <ShieldCheck className="h-6 w-6 text-teal-600" />
              </div>
              {warnings.length > 0 ? (
                <div className="mt-5 space-y-3">
                  {warnings.map((warning, index) => (
                    <article key={`${warning.code}-${index}`} className={`rounded-2xl border p-4 ${warningTone(warning.severity)}`}>
                      <p className="text-sm font-black">{warning.message}</p>
                      {warning.evidence ? <p className="mt-2 text-xs font-bold opacity-75">{warning.evidence}</p> : null}
                    </article>
                  ))}
                </div>
              ) : (
                <EmptyDetail title="No validation alerts" text="No rule warning was stored for this report." />
              )}
            </div>
          </div>

          <form className="space-y-6" onSubmit={saveReport}>
            <div className="dashboard-panel">
              <p className="section-eyebrow">Formatted report</p>
              <h2 className="mt-2 text-2xl font-black text-slate-950">Readable OCR view</h2>
              <pre className="mt-5 max-h-[420px] whitespace-pre-wrap overflow-auto rounded-2xl border border-blue-100 bg-blue-50/70 p-5 text-sm leading-7 text-slate-700">
                {report.formatted_text || report.ocr_cleaned_text || "No readable formatted text is available yet."}
              </pre>
              {report.patient_summary && (
                <div className="mt-5 rounded-2xl border border-emerald-100 bg-emerald-50 p-4">
                  <p className="text-xs font-black uppercase tracking-[0.16em] text-emerald-700">Patient-friendly Summary</p>
                  <p className="mt-2 text-sm font-semibold leading-7 text-emerald-950">{report.patient_summary}</p>
                </div>
              )}
              <div className="mt-5 rounded-2xl border border-teal-100 bg-teal-50 p-4">
                <p className="text-xs font-black uppercase tracking-[0.16em] text-teal-700">Clinical AI Summary</p>
                <p className="mt-2 text-sm font-semibold leading-7 text-teal-950">{summary.summary || report.summary || report.ai_summary || "No summary available."}</p>
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-2">
                <SummaryList title="Key findings" values={summary.key_findings ?? []} />
                <SummaryList title="Diseases" values={summary.detected_diseases ?? []} />
                <SummaryList title="Medicines" values={summary.medicines ?? []} />
                <SummaryList title="Doctor notes" values={summary.doctor_notes ?? []} />
              </div>
            </div>

            <div className="dashboard-panel">
              <div className="grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="text-sm font-bold text-slate-700">Department</label>
                  <select className="form-input" value={department} onChange={(event) => setDepartment(event.target.value)}>
                    {departments.map((item) => (
                      <option key={item.id} value={item.id}>
                        {item.name}
                      </option>
                    ))}
                  </select>
                </div>
                <SmallDetail label="Original file" value={report.original_filename} />
              </div>
              <div className="mt-5">
                <label className="text-sm font-bold text-slate-700">Editable OCR text</label>
                <textarea
                  className="form-input min-h-[360px] font-mono text-sm"
                  value={editableText}
                  onChange={(event) => setEditableText(event.target.value)}
                />
              </div>
              <div className="mt-5 grid gap-3 sm:grid-cols-3">
                <button type="submit" disabled={isSaving} className="gradient-button gap-2">
                  {isSaving ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                  Save edits
                </button>
                <button type="button" onClick={regenerateOcr} disabled={isRegenerating} className="secondary-button gap-2">
                  {isRegenerating ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                  Regenerate OCR
                </button>
                <button
                  type="button"
                  onClick={deleteReport}
                  disabled={isDeleting}
                  className="inline-flex items-center justify-center gap-2 rounded-2xl border border-red-100 bg-red-50 px-5 py-3 text-sm font-bold text-red-700 transition hover:bg-red-100 disabled:cursor-not-allowed disabled:opacity-70"
                >
                  {isDeleting ? <Loader2 className="h-4 w-4 animate-spin" /> : <Trash2 className="h-4 w-4" />}
                  Delete
                </button>
              </div>
              <p className="mt-4 flex gap-2 rounded-2xl border border-amber-100 bg-amber-50 p-4 text-sm font-semibold leading-6 text-amber-900">
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0" />
                OCR text may contain scanning errors. Confirm critical results against the original report before using them for care decisions.
              </p>
            </div>
          </form>
        </section>
      </div>
    </main>
  );
}

function SmallDetail({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-2xl border border-slate-100 bg-slate-50 p-4">
      <p className="text-xs font-black uppercase tracking-[0.16em] text-slate-400">{label}</p>
      <p className="mt-2 break-words text-sm font-black capitalize text-slate-950">{value}</p>
    </div>
  );
}

function SummaryList({ title, values }: { title: string; values: string[] }) {
  return (
    <div className="rounded-2xl border border-blue-100 bg-blue-50/60 p-4">
      <p className="text-xs font-black uppercase tracking-[0.14em] text-blue-700">{title}</p>
      {values.length > 0 ? (
        <ul className="mt-3 space-y-2">
          {values.slice(0, 4).map((value) => (
            <li key={value} className="text-sm font-semibold leading-6 text-slate-700">
              {value}
            </li>
          ))}
        </ul>
      ) : (
        <p className="mt-3 text-sm font-semibold leading-6 text-slate-500">Not detected.</p>
      )}
    </div>
  );
}

function EmptyDetail({ title, text }: { title: string; text: string }) {
  return (
    <div className="mt-5 rounded-2xl border border-dashed border-slate-200 bg-slate-50 p-8 text-center">
      <AlertTriangle className="mx-auto h-6 w-6 text-slate-400" />
      <p className="mt-3 font-black text-slate-950">{title}</p>
      <p className="mt-2 text-sm leading-6 text-slate-500">{text}</p>
    </div>
  );
}
