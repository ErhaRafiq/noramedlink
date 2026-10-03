import type {
  AIReportAnalysis,
  MedicalDocument,
  PatientReportCategorySummary,
} from "@/lib/types";

export function parseBloodPressure(value: string) {
  const match = value.match(/(\d{2,3})\s*\/\s*(\d{2,3})/);
  if (!match) {
    return null;
  }
  return {
    systolic: Number(match[1]),
    diastolic: Number(match[2]),
  };
}

export function serializeReport(record: {
  id: number;
  patientId: number;
  departmentId: number | null;
  departmentName: string | null;
  category: string;
  title: string;
  originalFileName: string;
  fileUrl: string;
  fileType: string;
  extractedText: string | null;
  formattedText: string | null;
  structuredDataJson: Record<string, unknown>;
  summary: string | null;
  extractedEntities: unknown[];
  ruleWarnings: unknown[];
  validationStatus: string;
  validationResults: Record<string, unknown>;
  clinicalSummaryJson: Record<string, unknown>;
  llmSelfCheck: Record<string, unknown>;
  summarySource: string;
  ocrStatus: string;
  ocrConfidence: number | null;
  uploadDate: Date;
  updatedAt: Date;
  possibleReportType: string | null;
  detectedKeywords: string[];
  structuredSections: Record<string, string>;
  aiSummary: string | null;
}): MedicalDocument {
  return {
    id: record.id,
    patient_id: record.patientId,
    department_id: record.departmentId,
    department_name: record.departmentName ?? undefined,
    department_slug: record.departmentName?.toLowerCase().replace(/\s+/g, "-") ?? undefined,
    category: record.category,
    title: record.title,
    notes: null,
    original_file_name: record.originalFileName,
    original_filename: record.originalFileName,
    file_url: record.fileUrl,
    stored_file_path: record.fileUrl,
    file_type: record.fileType,
    upload_date: record.uploadDate.toISOString(),
    updated_at: record.updatedAt.toISOString(),
    ocr_status: record.ocrStatus,
    ocr_confidence: record.ocrConfidence,
    extracted_text: record.extractedText,
    formatted_text: record.formattedText,
    ocr_raw_text: record.extractedText,
    ocr_cleaned_text: record.formattedText,
    possible_report_type: record.possibleReportType,
    detected_keywords: record.detectedKeywords,
    structured_sections: record.structuredSections,
    structured_data_json: record.structuredDataJson,
    summary: record.summary,
    extracted_entities: record.extractedEntities as MedicalDocument["extracted_entities"],
    rule_warnings: record.ruleWarnings as MedicalDocument["rule_warnings"],
    validation_status: record.validationStatus,
    validation_results: record.validationResults,
    clinical_summary_json: record.clinicalSummaryJson as MedicalDocument["clinical_summary_json"],
    llm_self_check: record.llmSelfCheck,
    summary_source: record.summarySource,
    ai_summary: record.aiSummary,
  };
}

export function summarizeCategories(records: PatientReportCategorySummary[]) {
  return records;
}

export function reportAnalysisFromText(input: {
  category: string;
  reportType: string;
  patientSummary: string;
  doctorSummary: string;
  abnormalFindings: string[];
  possibleRiskFlags: string[];
  recommendedSpecialist: string;
  urgencyLevel: string;
  disclaimer: string;
}): AIReportAnalysis {
  return input;
}
