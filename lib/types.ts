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

export type PatientSignupPayload = {
  full_name: string;
  email: string;
  password: string;
  confirm_password: string;
  cnic: string;
  phone: string;
  date_of_birth: string;
  gender: string;
};

export type DoctorSignupPayload = {
  full_name: string;
  email: string;
  password: string;
  confirm_password: string;
  pmdc_number: string;
  specialization: string;
  phone: string;
  hospital_name: string;
};

export type AdminSignupPayload = {
  full_name: string;
  email: string;
  password: string;
  confirm_password: string;
  phone: string;
  admin_invite_code: string;
};

export type SignupOtpPayload = {
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

export type VerifySignupOtpPayload = SignupOtpPayload & {
  otp: string;
};

export type SignupOtpResponse = {
  message: string;
  expires_in_seconds: number;
};

export type AdminDashboardStats = {
  totalUsers: number;
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
  notes?: string | null;
  original_file_name?: string;
  original_filename: string;
  file_url?: string;
  stored_file_path: string;
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
  heart_rate: number;
  spo2: number;
  temperature: number;
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
  rating: number;
  available_today: boolean;
  source: "registered" | "demo";
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

export type AppointmentBookingPayload = {
  doctorId: number;
  doctorName: string;
  specialty: string;
  date: string;
  time: string;
  reason: string;
};

export type AppointmentBookingResponseV2 = {
  message: string;
  appointment: Appointment;
};

export type DoctorOption = {
  id: number;
  name: string;
  specialty: string;
  hospitalName: string;
  rating: number;
  availableToday: boolean;
  source: "registered" | "demo";
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

export type MedicineSafetyCheck = {
  status: "Safe" | "Caution" | "High Risk";
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
  stats: {
    assigned_patients: number;
    pending_consults: number;
    records_reviewed: number;
    future_modules: number;
  };
  modules: Array<{
    title: string;
    description: string;
  }>;
};
