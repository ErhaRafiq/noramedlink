import type {
  AIChatResponse,
  AIReportAnalysis,
  AppointmentBookingPayload,
  AppointmentBookingResponseV2,
  Appointment,
  AppointmentBookingResponse,
  AppointmentDoctor,
  AuthResponse,
  AuthUser,
  DailyVital,
  DepartmentTile,
  DoctorSummary,
  DoctorDashboard,
  DoctorOption,
  DoctorSignupPayload,
  HealthRiskPrediction,
  HealthTip,
  MedicalDocument,
  MedicineHistory,
  MedicineHistoryPayload,
  MedicineSafetyCheck,
  MedicationSchedule,
  MedicineReminder,
  PatientDashboard,
  PatientReportCategorySummary,
  PatientSignupPayload,
  PatientVitals,
  ReminderLog,
  VitalTrendPoint,
  SignupOtpPayload,
  AdminActivity,
  AdminDashboardStats,
  AdminDoctor,
  AdminUser,
} from "@/lib/types";

const API_BASE_URL = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000").replace(
  /\/$/,
  "",
);

type RequestOptions = RequestInit & {
  token?: string;
  baseUrl?: string;
};

function formatApiDetail(detail: unknown) {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    return detail
      .map((item) => {
        if (item && typeof item === "object" && "msg" in item) {
          return String((item as { msg: unknown }).msg);
        }
        return JSON.stringify(item);
      })
      .join(" ");
  }
  if (detail && typeof detail === "object") {
    return JSON.stringify(detail);
  }
  return "Request failed.";
}

async function apiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers = new Headers(options.headers);
  const isFormData = options.body instanceof FormData;
  const baseUrl = (options.baseUrl ?? API_BASE_URL).replace(/\/$/, "");

  if (!isFormData && options.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (options.token) {
    headers.set("Authorization", `Bearer ${options.token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${baseUrl}${path}`, {
      ...options,
      headers,
    });
  } catch (error) {
    const detail = error instanceof Error ? ` (${error.message})` : "";
    throw new Error(
      `Unable to reach the backend API. Make sure the FastAPI server is running.${detail}`,
    );
  }

  const contentType = response.headers.get("Content-Type") ?? "";
  const data = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const detail =
      typeof data === "object" && data && "detail" in data
        ? formatApiDetail((data as { detail: unknown }).detail)
        : typeof data === "object" && data && "message" in data
          ? formatApiDetail((data as { message: unknown }).message)
          : "Request failed.";
    throw new Error(detail);
  }

  return data as T;
}

async function authApiRequest<T>(path: string, options: RequestOptions = {}): Promise<T> {
  try {
    return await apiRequest<T>(path, options);
  } catch (error) {
    if (
      typeof window !== "undefined" &&
      path.startsWith("/api/auth/") &&
      error instanceof Error &&
      (error.message.includes("Unable to reach the backend API") ||
        error.message.includes("404") ||
        error.message.toLowerCase().includes("not found"))
    ) {
      return apiRequest<T>(path, {
        ...options,
        baseUrl: "",
      });
    }

    throw error;
  }
}

export const api = {
  baseUrl: API_BASE_URL,
  signupPatient(payload: PatientSignupPayload) {
    return apiRequest<AuthResponse>("/api/auth/signup/patient", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  signupDoctor(payload: DoctorSignupPayload) {
    return apiRequest<AuthResponse>("/api/auth/signup/doctor", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  signupAccount(payload: SignupOtpPayload) {
    return authApiRequest<AuthResponse>("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  requestSignupOtp(payload: SignupOtpPayload) {
    return authApiRequest<{ message: string; expires_in_seconds: number }>("/api/auth/request-otp", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  verifySignupOtp(payload: SignupOtpPayload & { otp: string }) {
    return authApiRequest<AuthResponse>("/api/auth/verify-otp-signup", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  login(payload: { email: string; password: string }) {
    return authApiRequest<AuthResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  me(token: string) {
    return apiRequest<AuthUser>("/api/auth/me", { token });
  },
  adminDashboardStats(token: string) {
    return apiRequest<AdminDashboardStats>("/api/admin/dashboard-stats", { token });
  },
  adminUsers(token: string) {
    return apiRequest<AdminUser[]>("/api/admin/users", { token });
  },
  adminPendingDoctors(token: string) {
    return apiRequest<AdminDoctor[]>("/api/admin/doctors/pending", { token });
  },
  approveAdminDoctor(token: string, doctorId: number) {
    return apiRequest<AdminDoctor>(`/api/admin/doctors/${doctorId}/approve`, {
      method: "PATCH",
      token,
    });
  },
  rejectAdminDoctor(token: string, doctorId: number) {
    return apiRequest<AdminDoctor>(`/api/admin/doctors/${doctorId}/reject`, {
      method: "PATCH",
      token,
    });
  },
  adminRecentActivity(token: string) {
    return apiRequest<AdminActivity[]>("/api/admin/recent-activity", { token });
  },
  patientDashboard(token: string) {
    return apiRequest<PatientDashboard>("/patient/dashboard", { token });
  },
  patientDocuments(token: string) {
    return apiRequest<MedicalDocument[]>("/patient/reports", { token });
  },
  patientDocument(token: string, documentId: number) {
    return apiRequest<MedicalDocument>(`/reports/${documentId}`, { token, baseUrl: API_BASE_URL });
  },
  patientDepartmentReports(token: string, department: string) {
    return apiRequest<MedicalDocument[]>(`/patient/reports/department/${encodeURIComponent(department)}`, { token });
  },
  patientDepartmentTiles(token: string) {
    return apiRequest<DepartmentTile[]>("/patient/reports/tiles", { token });
  },
  patientLatestVitals(token: string) {
    return apiRequest<PatientVitals | null>("/patient/vitals/latest", { token });
  },
  patientVitalsToday(token: string) {
    return apiRequest<DailyVital | null>("/api/patient/vitals/today", { token });
  },
  patientVitalsTrends(token: string) {
    return apiRequest<VitalTrendPoint[]>("/api/patient/vitals/trends", { token });
  },
  createPatientVital(
    token: string,
    payload: {
      bloodPressureSystolic: number;
      bloodPressureDiastolic: number;
      heartRate: number;
      spo2: number;
      temperature: number;
      sugarLevel?: number | null;
      weight?: number | null;
      recordedAt?: string;
    },
  ) {
    return apiRequest<DailyVital>("/api/patient/vitals", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },
  doctors(token: string) {
    return apiRequest<DoctorOption[]>("/api/doctors", { token });
  },
  bookAppointment(token: string, payload: AppointmentBookingPayload) {
    return apiRequest<AppointmentBookingResponseV2>("/api/appointments/book", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },
  appointmentsV2(token: string) {
    return apiRequest<Appointment[]>("/api/appointments", { token });
  },
  reports(token: string) {
    return apiRequest<MedicalDocument[]>("/reports", { token, baseUrl: API_BASE_URL });
  },
  reportsByCategory(token: string, category: string) {
    return apiRequest<MedicalDocument[]>(`/reports/department/${encodeURIComponent(category)}`, { token, baseUrl: API_BASE_URL });
  },
  uploadReport(token: string, formData: FormData) {
    return apiRequest<MedicalDocument>("/reports/upload", {
      method: "POST",
      token,
      body: formData,
      baseUrl: API_BASE_URL,
    });
  },
  extractOcr(
    token: string,
    formData: FormData,
  ) {
    return apiRequest<{ rawText: string; cleanedText: string; possibleReportType: string; detectedKeywords: string[]; structuredSections: Record<string, string> }>(
      "/api/ocr/extract",
      {
        method: "POST",
        token,
        body: formData,
      },
    );
  },
  analyzeReport(token: string, payload: { text: string; category?: string; fileName?: string; reportType?: string }) {
    return apiRequest<AIReportAnalysis>("/api/ai/analyze-report", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },
  medicines(token: string) {
    return apiRequest<MedicationSchedule[]>("/api/medicines", { token });
  },
  createMedicineSchedule(
    token: string,
    payload: {
      medicineName: string;
      dosage: string;
      instructions?: string | null;
      startDate: string;
      endDate?: string | null;
    },
  ) {
    return apiRequest<MedicationSchedule>("/api/medicines", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },
  createReminder(
    token: string,
    payload: {
      medicationId: number;
      reminderTime: string;
      frequency: string;
    },
  ) {
    return apiRequest<MedicineReminder>("/api/reminders/create", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },
  remindersToday(token: string) {
    return apiRequest<MedicineReminder[]>("/api/reminders/today", { token });
  },
  markReminderTaken(token: string, reminderId: number) {
    return apiRequest<MedicineReminder>(`/api/reminders/${reminderId}/mark-taken`, {
      method: "PATCH",
      token,
    });
  },
  skipReminder(token: string, reminderId: number) {
    return apiRequest<MedicineReminder>(`/api/reminders/${reminderId}/skip`, {
      method: "PATCH",
      token,
    });
  },
  aiChat(token: string, payload: { message: string; context?: string }) {
    return apiRequest<AIChatResponse>("/api/ai/chat", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },
  uploadDocument(token: string, formData: FormData) {
    return apiRequest<MedicalDocument>("/patient/reports/upload", {
      method: "POST",
      token,
      body: formData,
    });
  },
  updateOcrText(token: string, documentId: number, cleanedText: string) {
    return apiRequest<MedicalDocument>(`/reports/${documentId}`, {
      method: "PATCH",
      token,
      body: JSON.stringify({ extracted_text: cleanedText }),
      baseUrl: API_BASE_URL,
    });
  },
  updateDocument(token: string, documentId: number, payload: { title?: string; department?: string; extracted_text?: string; formatted_text?: string }) {
    return apiRequest<MedicalDocument>(`/reports/${documentId}`, {
      method: "PATCH",
      token,
      body: JSON.stringify(payload),
      baseUrl: API_BASE_URL,
    });
  },
  regenerateDocumentOcr(token: string, documentId: number) {
    return apiRequest<MedicalDocument>(`/api/reports/${documentId}/regenerate-ocr`, {
      method: "POST",
      token,
      baseUrl: API_BASE_URL,
    });
  },
  deleteDocument(token: string, documentId: number) {
    return apiRequest<{ message: string }>(`/reports/${documentId}`, {
      method: "DELETE",
      token,
      baseUrl: API_BASE_URL,
    });
  },
  patientMedicines(token: string) {
    return apiRequest<MedicineHistory[]>("/patient/medicines", { token });
  },
  createMedicine(token: string, payload: MedicineHistoryPayload) {
    return apiRequest<MedicineHistory>("/patient/medicines", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },
  updateMedicine(token: string, medicineId: number, payload: Partial<MedicineHistoryPayload>) {
    return apiRequest<MedicineHistory>(`/patient/medicines/${medicineId}`, {
      method: "PUT",
      token,
      body: JSON.stringify(payload),
    });
  },
  deleteMedicine(token: string, medicineId: number) {
    return apiRequest<{ message: string }>(`/patient/medicines/${medicineId}`, {
      method: "DELETE",
      token,
    });
  },
  riskPredictions(token: string) {
    return apiRequest<HealthRiskPrediction[]>("/patient/risk-predictions", { token });
  },
  generateRiskPredictions(token: string) {
    return apiRequest<HealthRiskPrediction[]>("/patient/risk-predictions/generate", {
      method: "POST",
      token,
    });
  },
  healthTips(token: string) {
    return apiRequest<HealthTip[]>("/patient/health-tips", { token });
  },
  generateHealthTips(token: string) {
    return apiRequest<HealthTip[]>("/patient/health-tips/generate", {
      method: "POST",
      token,
    });
  },
  doctorSummaries(token: string) {
    return apiRequest<DoctorSummary[]>("/patient/doctor-summaries", { token });
  },
  generateDoctorSummary(token: string) {
    return apiRequest<DoctorSummary>("/patient/doctor-summaries/generate", {
      method: "POST",
      token,
    });
  },
  checkMedicineSafety(
    token: string,
    payload: { medicine_name: string; dosage?: string | null; known_allergies?: string | null },
  ) {
    return apiRequest<MedicineSafetyCheck>("/patient/medicine-safety/check", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },
  doctorDashboard(token: string) {
    return apiRequest<DoctorDashboard>("/doctor/dashboard", { token });
  },
  appointmentDoctors(params: {
    query?: string;
    specialty?: string;
    availableToday?: boolean;
  } = {}) {
    const searchParams = new URLSearchParams();
    if (params.query?.trim()) {
      searchParams.set("query", params.query.trim());
    }
    if (params.specialty?.trim() && params.specialty !== "All Specialties") {
      searchParams.set("specialty", params.specialty.trim());
    }
    if (typeof params.availableToday === "boolean") {
      searchParams.set("available_today", String(params.availableToday));
    }
    const query = searchParams.toString();
    return apiRequest<AppointmentDoctor[]>(`/appointments/doctors${query ? `?${query}` : ""}`);
  },
  appointments(token: string) {
    return apiRequest<Appointment[]>("/appointments", { token });
  },
  createAppointment(
    token: string,
    payload: {
      doctor_name: string;
      doctor_id?: number | null;
      date?: string | null;
      notes?: string | null;
      patient_access_otp?: string | null;
    },
  ) {
    return apiRequest<AppointmentBookingResponse>("/appointments", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },
  updateAppointment(
    token: string,
    appointmentId: number,
    payload: {
      date?: string;
      status?: string;
      payment_status?: string;
      notes?: string | null;
    },
  ) {
    return apiRequest<Appointment>(`/appointments/${appointmentId}`, {
      method: "PUT",
      token,
      body: JSON.stringify(payload),
    });
  },
  deleteAppointment(token: string, appointmentId: number) {
    return apiRequest<{ message: string }>(`/appointments/${appointmentId}`, {
      method: "DELETE",
      token,
    });
  },
  uploadUrl(path: string) {
    if (path.startsWith("http")) {
      return path;
    }
    const normalized = path.replace(/\\/g, "/").replace(/^\/+/, "");
    return `${API_BASE_URL}/${normalized}`;
  },
};
