import { normalizeReportCategory, reportTypeForCategory } from "@/lib/patient-dashboard";
import { serializeReport } from "@/lib/patient-output";
import type { ReportCategoryId } from "@/lib/patient-dashboard";

type DepartmentLike = {
  name: string | null;
} | null;

export type PatientReportRecordLike = {
  id: number;
  patientId: number;
  departmentId: number | null;
  department?: DepartmentLike;
  title: string;
  originalFileName: string;
  fileUrl: string;
  fileType: string;
  extractedText: string | null;
  formattedText: string | null;
  structuredDataJson: unknown;
  summary: string | null;
  extractedEntities: unknown;
  ruleWarnings: unknown;
  validationStatus: string;
  validationResults: unknown;
  clinicalSummaryJson: unknown;
  llmSelfCheck: unknown;
  summarySource: string;
  ocrStatus: string;
  ocrConfidence: number | null;
  uploadDate: Date;
  updatedAt: Date;
};

function asObject(value: unknown): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    return {};
  }

  return value as Record<string, unknown>;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function asStringArray(value: unknown): string[] {
  return Array.isArray(value) ? value.map(String).filter(Boolean) : [];
}

function getString(value: unknown) {
  return typeof value === "string" && value.trim().length > 0 ? value.trim() : null;
}

export function getReportCategory(report: PatientReportRecordLike): ReportCategoryId {
  const structured = asObject(report.structuredDataJson);
  return normalizeReportCategory(
    getString(structured.category) ??
      getString(structured.department) ??
      report.department?.name ??
      report.title,
  );
}

export function getReportType(report: PatientReportRecordLike, category = getReportCategory(report)) {
  const structured = asObject(report.structuredDataJson);
  return getString(structured.reportType) ?? reportTypeForCategory(category);
}

export function getReportStructuredSections(report: PatientReportRecordLike) {
  const structured = asObject(report.structuredDataJson);
  const sections = asObject(structured.structuredSections);

  if (Object.keys(sections).length > 0) {
    return sections as Record<string, string>;
  }

  const fields = asObject(structured.fields);
  return fields as Record<string, string>;
}

export function getReportDetectedKeywords(report: PatientReportRecordLike) {
  const structured = asObject(report.structuredDataJson);
  return asStringArray(structured.detectedKeywords);
}

export function getReportDoctorSummary(report: PatientReportRecordLike) {
  const structured = asObject(report.structuredDataJson);
  return (
    getString(structured.doctorSummary) ??
    getString(asObject(report.clinicalSummaryJson).summary) ??
    report.summary
  );
}

export function serializePatientReport(report: PatientReportRecordLike) {
  const category = getReportCategory(report);

  return serializeReport({
    id: report.id,
    patientId: report.patientId,
    departmentId: report.departmentId,
    departmentName: report.department?.name ?? null,
    category,
    title: report.title,
    originalFileName: report.originalFileName,
    fileUrl: report.fileUrl,
    fileType: report.fileType,
    extractedText: report.extractedText,
    formattedText: report.formattedText,
    structuredDataJson: asObject(report.structuredDataJson),
    summary: report.summary,
    extractedEntities: asArray(report.extractedEntities),
    ruleWarnings: asArray(report.ruleWarnings),
    validationStatus: report.validationStatus,
    validationResults: asObject(report.validationResults),
    clinicalSummaryJson: asObject(report.clinicalSummaryJson),
    llmSelfCheck: asObject(report.llmSelfCheck),
    summarySource: report.summarySource,
    ocrStatus: report.ocrStatus,
    ocrConfidence: report.ocrConfidence,
    uploadDate: report.uploadDate,
    updatedAt: report.updatedAt,
    possibleReportType: getReportType(report, category),
    detectedKeywords: getReportDetectedKeywords(report),
    structuredSections: getReportStructuredSections(report),
    aiSummary: getReportDoctorSummary(report),
  });
}
