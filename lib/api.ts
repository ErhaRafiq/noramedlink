import type {
  Appointment,
  AppointmentBookingResponse,
  AppointmentDoctor,
  AuthResponse,
  AuthUser,
  DailyVital,
  DepartmentTile,
  DoctorDashboard,
  DoctorOverview,
  DoctorOption,
  HealthFlags,
  MedicalDocument,
  MedicationSchedule,
  MedicineReminder,
  PatientVitals,
  SignupOtpPayload,
  SummaryResponse,
  AdminActivity,
  AdminDashboardStats,
  AdminDoctor,
  AdminUser,
  Page,
} from "@/lib/types";

// All FastAPI calls go through the same-origin proxy (app/api/backend/[...path]),
// which forwards to the server-side SERVER_API_URL. NEXT_PUBLIC_API_URL is no longer used.
const API_BASE_URL = "/api/backend";

/** A failed API call. `status` is the HTTP status, or 0 when the backend could not be reached. */
export class ApiError extends Error {
  readonly status: number;
  /** For 429 responses: seconds the server asked us to wait (Retry-After), if given. */
  readonly retryAfterSeconds: number | null;

  constructor(message: string, status: number, retryAfterSeconds: number | null = null) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.retryAfterSeconds = retryAfterSeconds;
  }
}

export function isApiError(error: unknown, status?: number): error is ApiError {
  return error instanceof ApiError && (status === undefined || error.status === status);
}

/** Optional ?limit=&offset= for paginated list endpoints (server default 20, max 100). */
export type PageQuery = { limit?: number; offset?: number };

/** Filters for GET /patient/reports, on top of paging. */
export type ReportListQuery = PageQuery & {
  q?: string;
  department?: string;
  validationStatus?: "SAFE" | "CAUTION" | "HIGH_RISK" | "NOT_VALIDATED";
};

function withQuery(path: string, values: Record<string, string | number | undefined>) {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(values)) {
    if (value !== undefined && value !== "") params.set(key, String(value));
  }
  const query = params.toString();
  return query ? `${path}?${query}` : path;
}

function withPage(path: string, page: PageQuery = {}) {
  return withQuery(path, { limit: page.limit, offset: page.offset });
}

type RequestOptions = RequestInit & {
  token?: string;
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
  const { token, ...init } = options;
  const headers = new Headers(init.headers);
  const isFormData = init.body instanceof FormData;

  if (!isFormData && init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  if (token) {
    headers.set("Authorization", `Bearer ${token}`);
  }

  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, { ...init, headers });
  } catch (error) {
    const detail = error instanceof Error ? ` (${error.message})` : "";
    if (init.signal?.aborted) {
      throw error;
    }
    throw new ApiError(`Unable to reach the backend API. Make sure the FastAPI server is running.${detail}`, 0);
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
    const retryAfter = Number(response.headers.get("Retry-After"));
    throw new ApiError(detail, response.status, Number.isFinite(retryAfter) && retryAfter > 0 ? retryAfter : null);
  }

  return data as T;
}

export const api = {
  signupAccount(payload: SignupOtpPayload) {
    return apiRequest<AuthResponse>("/api/auth/signup", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  login(payload: { email: string; password: string }) {
    return apiRequest<AuthResponse>("/api/auth/login", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  me(token: string, init?: { signal?: AbortSignal }) {
    return apiRequest<AuthUser>("/api/auth/me", { token, signal: init?.signal });
  },
  adminDashboardStats(token: string) {
    return apiRequest<AdminDashboardStats>("/api/admin/dashboard-stats", { token });
  },
  adminUsers(token: string, page?: PageQuery) {
    return apiRequest<Page<AdminUser>>(withPage("/api/admin/users", page), { token });
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
  patientDocument(token: string, documentId: number) {
    return apiRequest<MedicalDocument>(`/patient/reports/${documentId}`, { token });
  },
  patientDepartmentTiles(token: string) {
    return apiRequest<DepartmentTile[]>("/patient/reports/tiles", { token });
  },
  basicVitalsHistory(token: string) {
    return apiRequest<PatientVitals[]>("/patient/vitals/basic", { token });
  },
  addBasicVitals(token: string, payload: { blood_pressure: string; sugar_level: string }) {
    return apiRequest<PatientVitals>("/patient/vitals/basic", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },
  patientVitalsToday(token: string) {
    return apiRequest<DailyVital | null>("/patient/vitals/today", { token });
  },
  async doctors(token: string): Promise<DoctorOption[]> {
    // Verified doctors only (FastAPI /appointments/doctors), in the workspace's shape.
    const doctors = await apiRequest<AppointmentDoctor[]>("/appointments/doctors", { token });
    return doctors.map((doctor) => ({
      id: doctor.id,
      name: doctor.name,
      specialty: doctor.specialty,
      hospitalName: doctor.location,
      rating: doctor.rating,
      availableToday: doctor.available_today,
      source: doctor.source,
    }));
  },
  reports(token: string, query: ReportListQuery = {}, init?: { signal?: AbortSignal }) {
    const path = withQuery("/patient/reports", {
      limit: query.limit,
      offset: query.offset,
      q: query.q?.trim(),
      department: query.department,
      validation_status: query.validationStatus,
    });
    return apiRequest<Page<MedicalDocument>>(path, { token, signal: init?.signal });
  },
  uploadReport(token: string, formData: FormData) {
    return apiRequest<MedicalDocument>("/patient/reports/upload", {
      method: "POST",
      token,
      body: formData,
    });
  },
  medicines(token: string) {
    return apiRequest<MedicationSchedule[]>("/patient/medications", { token });
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
    return apiRequest<MedicationSchedule>("/patient/medications", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },
  issueDashboardOtp(token: string) {
    return apiRequest<{ message: string; otp: { code: string; expiresAt: string } }>("/patient/dashboard-otp", {
      method: "POST",
      token,
    });
  },
  doctorOverview(token: string) {
    return apiRequest<DoctorOverview>("/doctor/overview", { token });
  },
  unlockPatientDashboard(token: string, patientAccessOtp: string) {
    return apiRequest<{ message: string; patient: { id: number; name: string; email: string }; expiresAt: string }>(
      "/doctor/access/unlock",
      { method: "POST", token, body: JSON.stringify({ patientAccessOtp }) },
    );
  },
  endPatientDashboardAccess(token: string, patientId: number) {
    return apiRequest<{ message: string }>("/doctor/access/end", {
      method: "POST",
      token,
      body: JSON.stringify({ patientId }),
    });
  },
  createEmergencyRequest(
    token: string,
    payload: { patientName: string; phone: string; address: string; symptoms: string; latitude?: string; longitude?: string },
  ) {
    const coordinate = (value?: string) => (value && Number.isFinite(Number(value)) ? Number(value) : null);
    return apiRequest<{
      message: string;
      emergencyNotice: string;
      booking: { id: number; doctorName: string | null; status: string; estimatedMinutes: number | null };
    }>("/emergency/requests", {
      method: "POST",
      token,
      body: JSON.stringify({
        ...payload,
        latitude: coordinate(payload.latitude),
        longitude: coordinate(payload.longitude),
      }),
    });
  },
  summarizeText(token: string, text: string) {
    return apiRequest<SummaryResponse>("/nlp/summarize", {
      method: "POST",
      token,
      body: JSON.stringify({ text, category: "medical-report" }),
    });
  },
  summarizeSavedReports(token: string) {
    return apiRequest<SummaryResponse>("/nlp/summarize/saved-reports", { method: "POST", token });
  },
  createPayment(
    token: string,
    payload: { amount: number; method: string; purpose: string; phone?: string; appointment_id?: number },
  ) {
    return apiRequest<{ id: number; reference: string; status: string; amount: number; method: string }>("/payments", {
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
    return apiRequest<MedicineReminder>("/patient/medicine-reminders", {
      method: "POST",
      token,
      body: JSON.stringify(payload),
    });
  },
  remindersToday(token: string) {
    return apiRequest<MedicineReminder[]>("/patient/medicine-reminders/today", { token });
  },
  markReminderTaken(token: string, reminderId: number) {
    return apiRequest<MedicineReminder>(`/patient/medicine-reminders/${reminderId}/mark-taken`, {
      method: "PATCH",
      token,
    });
  },
  skipReminder(token: string, reminderId: number) {
    return apiRequest<MedicineReminder>(`/patient/medicine-reminders/${reminderId}/skip`, {
      method: "PATCH",
      token,
    });
  },

  updateDocument(token: string, documentId: number, payload: { title?: string; department?: string; extracted_text?: string; formatted_text?: string }) {
    return apiRequest<MedicalDocument>(`/patient/reports/${documentId}`, {
      method: "PATCH",
      token,
      body: JSON.stringify(payload),
    });
  },
  regenerateDocumentOcr(token: string, documentId: number) {
    return apiRequest<MedicalDocument>(`/patient/reports/${documentId}/regenerate-ocr`, {
      method: "POST",
      token,
    });
  },
  deleteDocument(token: string, documentId: number) {
    return apiRequest<{ message: string }>(`/patient/reports/${documentId}`, {
      method: "DELETE",
      token,
    });
  },
  /** What the fixed rules found in the patient's reports, in everyday words (not AI). */
  healthFlags(token: string) {
    return apiRequest<HealthFlags>("/patient/health-flags", { token });
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
  /** Books a verified doctor. `date` must be an ISO string with a time zone (Date#toISOString). */
  bookAppointment(
    token: string,
    payload: { doctorId: number; date: string; reason?: string | null; notes?: string | null; patientAccessOtp?: string | null },
  ) {
    return apiRequest<AppointmentBookingResponse>("/appointments", {
      method: "POST",
      token,
      body: JSON.stringify({
        doctor_id: payload.doctorId,
        date: payload.date,
        reason: payload.reason || null,
        notes: payload.notes || null,
        patient_access_otp: payload.patientAccessOtp || null,
      }),
    });
  },
  appointments(token: string, page?: PageQuery) {
    return apiRequest<Page<Appointment>>(withPage("/appointments", page), { token });
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
  uploadUrl(path: string) {
    if (path.startsWith("http") || path.startsWith("data:")) {
      return path;
    }
    const normalized = path.replace(/\\/g, "/").replace(/^\/+/, "");
    return `${API_BASE_URL}/${normalized}`;
  },
};
