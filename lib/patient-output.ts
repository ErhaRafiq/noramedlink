import type {
  AIReportAnalysis,
  Appointment,
  DailyVital,
  DoctorOption,
  MedicalDocument,
  MedicationSchedule,
  MedicineReminder,
  PatientReportCategorySummary,
  VitalTrendPoint,
} from "@/lib/types";

export function serializeDailyVital(record: {
  id: number;
  patientId: number;
  bloodPressureSystolic: number;
  bloodPressureDiastolic: number;
  heartRate: number;
  spo2: number;
  temperature: number;
  sugarLevel: number | null;
  weight: number | null;
  recordedAt: Date;
  createdAt: Date;
}): DailyVital {
  return {
    id: record.id,
    patient_id: record.patientId,
    blood_pressure_systolic: record.bloodPressureSystolic,
    blood_pressure_diastolic: record.bloodPressureDiastolic,
    heart_rate: record.heartRate,
    spo2: record.spo2,
    temperature: record.temperature,
    sugar_level: record.sugarLevel,
    weight: record.weight,
    recorded_at: record.recordedAt.toISOString(),
    created_at: record.createdAt.toISOString(),
  };
}

export function serializeVitalTrend(record: {
  recordedAt: Date;
  bloodPressureSystolic: number;
  bloodPressureDiastolic: number;
  heartRate: number;
  spo2: number;
  temperature: number;
  sugarLevel: number | null;
  weight: number | null;
}): VitalTrendPoint {
  return {
    recorded_at: record.recordedAt.toISOString(),
    blood_pressure_systolic: record.bloodPressureSystolic,
    blood_pressure_diastolic: record.bloodPressureDiastolic,
    heart_rate: record.heartRate,
    spo2: record.spo2,
    temperature: record.temperature,
    sugar_level: record.sugarLevel,
    weight: record.weight,
  };
}

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

export function parseNumber(value: unknown) {
  if (typeof value === "number" && Number.isFinite(value)) {
    return value;
  }
  if (typeof value === "string" && value.trim().length > 0) {
    const next = Number(value);
    return Number.isFinite(next) ? next : null;
  }
  return null;
}

export function serializeAppointment(record: {
  id: number;
  userId: number;
  doctorId: number | null;
  doctorName: string;
  specialty: string | null;
  reason: string | null;
  date: Date;
  status: string;
  paymentStatus: string;
  notes: string | null;
  createdAt: Date;
  updatedAt: Date;
}): Appointment {
  return {
    id: record.id,
    user_id: record.userId,
    doctor_id: record.doctorId,
    doctor_name: record.doctorName,
    specialty: record.specialty,
    reason: record.reason,
    date: record.date.toISOString(),
    status: record.status,
    payment_status: record.paymentStatus,
    notes: record.notes,
    created_at: record.createdAt.toISOString(),
    updated_at: record.updatedAt.toISOString(),
  };
}

export function serializeMedication(record: {
  id: number;
  patientId: number;
  medicineName: string;
  dosage: string;
  instructions: string | null;
  startDate: Date | null;
  endDate: Date | null;
  status: string;
  createdAt: Date;
}): MedicationSchedule {
  return {
    id: record.id,
    patient_id: record.patientId,
    medicine_name: record.medicineName,
    dosage: record.dosage,
    instructions: record.instructions,
    start_date: record.startDate ? record.startDate.toISOString() : null,
    end_date: record.endDate ? record.endDate.toISOString() : null,
    status: record.status,
    created_at: record.createdAt.toISOString(),
  };
}

export function serializeReminder(record: {
  id: number;
  medicationId: number;
  patientId: number;
  reminderTime: Date;
  frequency: string;
  status: string;
  takenAt: Date | null;
  skippedAt: Date | null;
  createdAt: Date;
  updatedAt: Date;
  medication?: {
    id: number;
    patientId: number;
    medicineName: string;
    dosage: string;
    instructions: string | null;
    startDate: Date | null;
    endDate: Date | null;
    status: string;
    createdAt: Date;
  } | null;
}): MedicineReminder {
  return {
    id: record.id,
    medication_id: record.medicationId,
    patient_id: record.patientId,
    reminder_time: record.reminderTime.toISOString(),
    frequency: record.frequency,
    status: record.status,
    taken_at: record.takenAt ? record.takenAt.toISOString() : null,
    skipped_at: record.skippedAt ? record.skippedAt.toISOString() : null,
    created_at: record.createdAt.toISOString(),
    updated_at: record.updatedAt.toISOString(),
    medication: record.medication ? serializeMedication(record.medication) : undefined,
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

export function serializeDoctors(records: Array<{
  id: number;
  name: string;
  specialty: string;
  hospitalName: string;
  rating: number;
  availableToday: boolean;
  source: "registered" | "demo";
}>): DoctorOption[] {
  return records.map((record) => ({
    id: record.id,
    name: record.name,
    specialty: record.specialty,
    hospitalName: record.hospitalName,
    rating: record.rating,
    availableToday: record.availableToday,
    source: record.source,
  }));
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
