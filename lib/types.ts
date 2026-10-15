export type UserRole = "patient" | "doctor" | "admin";

export type AuthUser = {
  id: number;
  full_name: string;
  email: string;
  role: UserRole;
  phone: string;
  is_email_verified: boolean;
  is_identity_verified: boolean;
  verification_status: "pending" | "verified" | "rejected" | string;
};

export type AuthResponse = {
  access_token: string;
  token_type: "bearer";
  user: AuthUser;
};

export type AdminSignupPayload = {
  full_name: string;
  email: string;
  password: string;
  confirm_password: string;
  phone: string;
  admin_invite_code: string;
};

export type SignupPayload = {
  role: UserRole;
  full_name: string;
  email: string;
  password: string;
  confirm_password: string;
  phone: string;
  cnic?: string;
  date_of_birth?: string;
  gender?: string;
  pmdc_number?: string;
  specialization?: string;
  hospital_name?: string;
  admin_invite_code?: string;
};

/** A page of a paginated list endpoint (backend/pagination.py). */
export type Page<T> = {
  items: T[];
  /** Rows matching the filters, across all pages. */
  total: number;
  limit: number;
  offset: number;
};

export type AdminDashboardStats = {
  totalUsers: number;
  totalPatients: number;
  activeUsers: number;
  activeDoctors: number;
  reportsUploaded: number;
  appointmentsToday: number;
  pendingDoctors: number;
};

export type AdminUser = {
  id: number;
  fullName: string;
  email: string;
  phone: string;
  role: UserRole;
  isActive: boolean;
  isEmailVerified: boolean;
  isIdentityVerified: boolean;
  createdAt: string;
  updatedAt: string;
};

export type AdminDoctor = {
  id: number;
  userId: number;
  fullName: string;
  email: string;
  phone: string;
  pmdcNumber: string;
  specialization: string;
  hospitalName: string;
  verificationStatus: string;
  createdAt: string;
};

export type AdminActivity = {
  id: string;
  type: "user" | "report" | "appointment" | string;
  title: string;
  description: string;
  createdAt: string;
};

export type MedicalDocument = {
  id: number;
  patient_id: number;
  department_id?: number | null;
  department_name?: string;
  department_slug?: string;
  category: string;
  title: string;
  original_file_name?: string;
  original_filename: string;
  file_url?: string;
  stored_file_path: string;
  // Short-lived signed link to the file (or an embedded data: image); null if no file.
  file_access_url?: string | null;
  file_type: string;
  upload_date: string;
  updated_at?: string;
  ocr_status: string;
  ocr_confidence?: number | null;
  extracted_text?: string | null;
  formatted_text?: string | null;
  ocr_raw_text: string | null;
  ocr_cleaned_text: string | null;
  possible_report_type: string | null;
  detected_keywords: string[];
  structured_sections: Record<string, string>;
  structured_data_json?: {
    fields?: Record<string, string>;
    department?: string;
    department_slug?: string;
    detected_keywords?: string[];
    summary?: string;
    bio_bert_entities?: MedicalEntity[];
    rule_warnings?: RuleWarning[];
    rule_validation?: Record<string, unknown>;
    ai_summary?: AiClinicalSummary;
    llm_self_check?: Record<string, unknown>;
    confidence_level?: string;
    error?: string;
    uncertain_values?: UncertainValue[];
    text_edited_by_patient?: boolean;
    [key: string]: unknown;
  };
  summary?: string | null;
  extracted_entities?: MedicalEntity[];
  rule_warnings?: RuleWarning[];
  validation_status?: "SAFE" | "CAUTION" | "HIGH_RISK" | string;
  validation_results?: Record<string, unknown>;
  clinical_summary_json?: AiClinicalSummary;
  llm_self_check?: Record<string, unknown>;
  summary_source?: string;
  ai_summary: string | null;
  patient_summary?: string | null;
  /** Who wrote patient_summary: "gemini", "openai", "groq" or "rule_based". */
  patient_summary_source?: string | null;
  conditions_mentioned?: ConditionMentioned[];
};

/** A condition the report mentions, with its everyday name. Mentioned in the report, not a diagnosis. */
/** The patient's health flags: what the fixed rules found in their own reports, in everyday words. */
export type HealthFlagReport = {
  report_id: number;
  report_title: string;
  upload_date: string;
  severity: "HIGH_RISK" | "CAUTION";
  messages: string[];
};

export type HealthFlags = {
  reports: HealthFlagReport[];
  high_risk_reports: number;
  conditions_mentioned: (ConditionMentioned & { report_ids: number[] })[];
};

export type ConditionMentioned = {
  name: string;
  plain: string;
  chronic: boolean;
};

/** A number OCR read with low confidence (below 0.90), still in the text as read. */
export type UncertainValue = {
  page?: number | null;
  line: string;
  text: string;
  score: number;
};

export type MedicalEntity = {
  text: string;
  label: string;
  confidence: number;
  source?: string;
};

export type RuleWarning = {
  code: string;
  severity: "SAFE" | "CAUTION" | "HIGH_RISK" | string;
  message: string;
  evidence?: string;
  /** The same alert in everyday words, for patients (the clinical message is for doctors). */
  patient_message?: string;
};

export type AiClinicalSummary = {
  patient_overview?: string;
  key_findings?: string[];
  detected_diseases?: string[];
  medicines?: string[];
  risks_alerts?: string[];
  doctor_notes?: string[];
  confidence_level?: string;
  missing_data?: string[];
  summary?: string;
  [key: string]: unknown;
};

export type DepartmentTile = {
  id: number;
  name: string;
  slug: string;
  icon: string | null;
  description: string | null;
  total_reports: number;
  latest_upload_date: string | null;
  preview_text: string | null;
  health_status?: string;
  risk_level?: "Low" | "Medium" | "High" | string;
  validation_status?: "SAFE" | "CAUTION" | "HIGH_RISK" | string;
};

export type DashboardCategory = {
  category: string;
  document_count: number;
  last_updated: string | null;
};

export type PatientDashboard = {
  patient: AuthUser;
  total_reports: number;
  categories_used: number;
  latest_upload: MedicalDocument | null;
  ocr_processed_reports: number;
  ai_summaries_generated: number;
  categories: DashboardCategory[];
  recent_documents: MedicalDocument[];
  medicine_count: number;
  latest_risk_prediction: HealthRiskPrediction | null;
  latest_doctor_summary: DoctorSummary | null;
};

export type PatientVitals = {
  id: number;
  user_id: number;
  blood_pressure: string;
  sugar_level: string;
  created_at: string;
};

export type DailyVital = {
  id: number;
  patient_id: number;
  blood_pressure_systolic: number;
  blood_pressure_diastolic: number;
  heart_rate: number | null;
  spo2: number | null;
  temperature: number | null;
  sugar_level: number | null;
  weight: number | null;
  recorded_at: string;
  created_at: string;
};

export type VitalTrendPoint = {
  recorded_at: string;
  blood_pressure_systolic: number;
  blood_pressure_diastolic: number;
  heart_rate: number;
  spo2: number;
  temperature: number;
  sugar_level: number | null;
  weight: number | null;
};

export type MedicineHistory = {
  id: number;
  patient_id: number;
  medicine_name: string;
  dosage: string;
  frequency: string;
  start_date: string;
  end_date: string | null;
  reason: string;
  prescribed_by: string | null;
  side_effects: string | null;
  created_at: string;
  updated_at: string;
};

export type MedicationSchedule = {
  id: number;
  patient_id: number;
  medicine_name: string;
  dosage: string;
  instructions: string | null;
  start_date: string | null;
  end_date: string | null;
  status: string;
  created_at: string;
};

export type MedicineReminder = {
  id: number;
  medication_id: number;
  patient_id: number;
  reminder_time: string;
  frequency: string;
  status: "UPCOMING" | "DUE_NOW" | "TAKEN" | "MISSED" | "SKIPPED" | string;
  taken_at: string | null;
  skipped_at: string | null;
  created_at: string;
  updated_at: string;
  medication?: MedicationSchedule;
};

export type ReminderLog = {
  id: number;
  reminder_id: number;
  patient_id: number;
  scheduled_for: string;
  status: "UPCOMING" | "DUE_NOW" | "TAKEN" | "MISSED" | "SKIPPED" | string;
  taken_at: string | null;
  created_at: string;
};

export type MedicineHistoryPayload = {
  medicine_name: string;
  dosage: string;
  frequency: string;
  start_date: string;
  end_date?: string | null;
  reason: string;
  prescribed_by?: string | null;
  side_effects?: string | null;
};

export type HealthRiskPrediction = {
  id: number;
  patient_id: number;
  risk_title: string;
  risk_level: "Low" | "Medium" | "High" | string;
  reason: string;
  recommendation: string;
  created_at: string;
};

export type HealthTip = {
  id: number;
  patient_id: number;
  category: "Food to prefer" | "Food to avoid" | "Lifestyle advice" | "When to consult a doctor" | string;
  tip_text: string;
  based_on_data: string;
  created_at: string;
};

export type DoctorSummary = {
  id: number;
  patient_id: number;
  summary_text: string;
  generated_at: string;
};

export type AppointmentDoctor = {
  id: number;
  doctor_id: number | null;
  name: string;
  specialty: string;
  location: string;
  rating: number | null;
  available_today: boolean | null;
  source: "registered";
};

export type Appointment = {
  id: number;
  user_id: number;
  doctor_id: number | null;
  doctor_name: string;
  specialty?: string | null;
  reason?: string | null;
  date: string;
  status: string;
  payment_status: string;
  notes: string | null;
  created_at: string;
  updated_at: string;
};

export type AppointmentBookingResponse = {
  message: string;
  appointment: Appointment;
  dashboard_access_granted: boolean;
};

export type DoctorOption = {
  id: number;
  name: string;
  specialty: string;
  hospitalName: string;
  rating: number | null;
  availableToday: boolean | null;
  source: "registered";
};

export type PatientReportCategorySummary = {
  category: string;
  document_count: number;
  latest_status: string;
  latest_upload_date: string | null;
  icon: string;
};

export type AIReportAnalysis = {
  category: string;
  reportType: string;
  patientSummary: string;
  doctorSummary: string;
  abnormalFindings: string[];
  possibleRiskFlags: string[];
  recommendedSpecialist: string;
  urgencyLevel: "Low" | "Medium" | "High" | string;
  disclaimer: string;
};

export type AIChatResponse = {
  answer: string;
  disclaimer: string;
};

/** POST /nlp/summarize and /nlp/summarize/saved-reports. */
export type SummaryResponse = {
  summary: string;
  method: "gemini" | "openai" | "groq" | "rule_based";
  warning: string | null;
  /** Values and terms found in the text, as written. */
  key_findings: string[];
  /** Alerts from the backend's deterministic report rules only. */
  risk_indicators: string[];
  recommendations: string[];
};

export type MedicineSafetyCheck = {
  /** Set by deterministic rules only; "No data" means no rule matched, never "safe". */
  status: "No data" | "Caution" | "High Risk";
  reason: string;
  warnings: string[];
};

export type DoctorDashboard = {
  doctor: {
    id: number;
    full_name: string;
    email: string;
    phone: string;
    specialization: string;
    hospital_name: string;
    verification_status: string;
  };
};

/** GET /doctor/overview: the doctor's appointments and emergency visits, plus medical
 *  data only for patients who granted access with a one-time code. */
export type DoctorOverview = {
  doctor: { id: number; name: string; email: string; role: string };
  stats: {
    appointments: number;
    patients: number;
    emergencyBookings: number;
    medicalRecords: number;
    medications: number;
  };
  appointments: Array<{
    id: number;
    userId: number;
    date: string;
    patientName: string;
    patientEmail: string;
    hasDashboardAccess: boolean;
    accessExpiresAt: string | null;
  }>;
  emergencyBookings: Array<{
    id: number;
    userId: number;
    patientName: string;
    phone: string;
    address: string;
    symptoms: string;
    status: string;
    estimatedMinutes: number;
    createdAt: string;
    hasDashboardAccess: boolean;
    accessExpiresAt: string | null;
  }>;
  patients: Array<{
    id: number;
    name: string;
    email: string;
    latestVitals: { bloodPressure: string; sugarLevel: string; createdAt: string } | null;
    recordCount: number;
    appointmentCount: number;
    accessExpiresAt: string;
  }>;
  medicalRecords: Array<{
    id: number;
    userId: number;
    title: string;
    fileName: string;
    scanStatus: string;
    extractedText: string | null;
    department: string;
    summary: string | null;
    validationStatus: string | null;
    createdAt: string;
    patientName: string;
  }>;
  medications: Array<{
    id: number;
    userId: number;
    name: string;
    dosage: string;
    status: string;
    createdAt: string;
    patientName: string;
  }>;
};

/** Clinical summary for doctors (GET /doctor/patients/{id}/clinical-summary). Built by fixed rules. */
export type ClinicalSummaryVersionMeta = {
  version: number;
  generated_at: string;
  trigger: string;
  source: "rule_based" | string;
  is_current: boolean;
};

/** Where a flag or item came from: a report (title, printed date) or values entered in the app. */
export type ClinicalSource = {
  report_id: number | string;
  title?: string | null;
  date?: string | null;
  date_source?: string | null;
  kind?: "report" | "vitals" | string;
  printed?: string;
  medicine?: string;
  dose?: string | null;
  frequency?: string | null;
};

/** A flag set by the fixed rules (backend/services/icse/flags.py). */
export type ClinicalFlag = {
  code: string;
  kind: "result" | "persistent" | "trend" | "chronic_condition" | "ongoing_treatment" | "high_alert_medicine" | "check_original" | string;
  severity: "HIGH_RISK" | "CAUTION" | "INFO";
  subject: string;
  message: string;
  reason: string;
  rule?: string;
  sources: ClinicalSource[];
};

export type ClinicalCondition = {
  name: string;
  icd10?: string | null;
  chronic?: boolean;
  relatives?: string[];
  sources: ClinicalSource[];
};

/** The sections of a clinical summary (backend/services/icse/summary.py). */
export type ClinicalSummaryContent = {
  section_limit?: number;
  key_findings: { text: string; source: string; rule_text?: string; ai_not_used?: string | null };
  abnormal_results: ClinicalFlag[];
  conditions: ClinicalCondition[];
  family_history: ClinicalCondition[];
  medications: {
    from_app: { name: string; dosage?: string | null; list?: string; start_date?: string | null; end_date?: string | null }[];
    from_reports: ClinicalSource[];
    stopped_in_reports: string[];
  };
  allergies: { status: "listed" | "none_recorded" | "not_recorded"; items: { name: string; sources: ClinicalSource[] }[]; no_known_allergies_in: ClinicalSource[] };
  flags: ClinicalFlag[];
  check_original: ClinicalFlag[];
  missing_data: string[];
  notes: string[];
};

export type ClinicalSummaryVersion = ClinicalSummaryVersionMeta & {
  patient_id: number;
  summary_text: string;
  content: ClinicalSummaryContent;
  note: string;
};

export type ClinicalSummaryStatus = {
  patient_id: number;
  summary: ClinicalSummaryVersion | null;
  out_of_date: boolean;
  pending_change: string | null;
};

export type ClinicalSummaryRegenerateResult = {
  summary: ClinicalSummaryVersion;
  created: boolean;
};

/* --- Medication safety and prescribing (MSCIE, Module 4) ------------------------------------- */

export type MedicineOption = { name: string; generic: string; brand: string | null; classes: string[]; match: number };

export type SafetySeverity = "contraindicated" | "major" | "moderate" | "minor" | "info";

/** One alert, set by fixed rules; every one has its rule, evidence from the record and sources. */
export type SafetyAlert = {
  id: string;
  rule_id: string;
  kind: "allergy" | "interaction" | "duplicate" | "contraindication" | "dose" | "previous_response" | "high_alert" | "no_data" | string;
  severity: SafetySeverity;
  level: "HIGH_RISK" | "CAUTION" | "INFO";
  requires_justification: boolean;
  medicine: string;
  title: string;
  effect: string;
  management: string;
  evidence: string[];
  sources: { label: string; reference?: string }[];
};

export type RankedAlternative = {
  rank: number;
  medicine: string;
  classes: string[];
  use: string;
  reason: string;
  sources: { label: string }[];
  alerts: SafetyAlert[];
  score: number;
  breakdown: { factor: string; value: number; weight: number; contribution: number; reason: string }[];
};

export type CheckedItem = {
  medicine: string;
  resolved: { name: string; generics: string[]; classes: string[]; high_alert: boolean; known: boolean };
  dose: string | null;
  frequency: string | null;
  duration: string | null;
  alerts: SafetyAlert[];
  worst: SafetySeverity | null;
  alternatives: RankedAlternative[];
};

export type MedicationCheck = {
  context: {
    medicines: { name: string; known: boolean; source: string; date: string | null }[];
    conditions: { name: string; source: string }[];
    allergies: { name: string; source: string }[];
    allergy_status: "listed" | "none_recorded" | "not_recorded";
    labs: { test: string; value: number; unit: string; date: string | null; source: string }[];
    previous: { generic: string; problem: boolean; note: string }[];
  };
  items: CheckedItem[];
  worst: SafetySeverity | null;
  requires_justification: SafetyAlert[];
  note: string;
};

export type PrescriptionItemInput = {
  medicine: string;
  dose?: string;
  frequency?: string;
  duration?: string;
  instructions?: string;
  replaced_medicine?: string;
};

export type Prescription = {
  id: number;
  patient_id: number;
  doctor_id: number | null;
  doctor_name: string;
  status: "confirmed" | "cancelled";
  notes: string | null;
  created_at: string;
  cancelled_at: string | null;
  items: (PrescriptionItemInput & { generic: string | null })[];
  overrides: { alert_id: string; severity: string; title: string; justification: string; created_at: string }[];
  alerts_at_confirmation: SafetyAlert[];
};

export type PatientPrescription = {
  id: number;
  doctor_name: string;
  status: "confirmed" | "cancelled";
  created_at: string;
  items: { medicine: string; generic: string | null; how_to_take: string; duration: string | null; instructions: string | null }[];
};

export type LabelEvidence = {
  generic: string;
  available: boolean;
  reason?: string | null;
  sections?: Record<string, string | null> | null;
  effective_time?: string | null;
  source?: string | null;
};
