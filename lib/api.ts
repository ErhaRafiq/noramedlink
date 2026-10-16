import type {
  Appointment,
  CheckoutResponse,
  Payment,
  AppointmentBookingResponse,
  AppointmentDoctor,
  AuthResponse,
  AuthUser,
  DailyVital,
  DepartmentTile,
  DoctorDashboard,
  DoctorOverview,
  DoctorOption,
  ClinicalSummaryRegenerateResult,
  ClinicalSummaryStatus,
  ClinicalSummaryVersion,
  ClinicalSummaryVersionMeta,
  HealthFlags,
  LabelEvidence,
  MedicationCheck,
  MedicineOption,
  PatientPrescription,
  Prescription,
  PrescriptionItemInput,
  MedicalDocument,
  MedicationSchedule,
  MedicineReminder,
  PatientVitals,
  SignupPayload,
  SummaryResponse,
  AdminActivity,
  AdminDashboardStats,
  AdminDoctor,
  AdminUser,
  Page,
  PatientProfileInput,
  Availability,
  AvailabilityWindow,
  ConsultationMode,
  DoctorSearch,
  NotificationPage,
  Review,
  SlotsResponse,
  DoctorProfileInput,
  Profile,
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

type RequestOptions = RequestInit;

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
    // A structured detail (e.g. {message, alerts}) is shown by its message.
    if ("message" in detail && typeof (detail as { message: unknown }).message === "string") {
      return (detail as { message: string }).message;
    }
    return JSON.stringify(detail);
  }
  return "Request failed.";
}

// The session is an HttpOnly cookie the browser sends by itself (same origin); no token is ever
// held or sent from JavaScript. The Next.js server adds it to the call it forwards to FastAPI.
async function apiRequest<T>(path: string, options: RequestOptions = {}, base = API_BASE_URL): Promise<T> {
  const init = options;
  const headers = new Headers(init.headers);
  const isFormData = init.body instanceof FormData;

  if (!isFormData && init.body && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }

  let response: Response;
  try {
    response = await fetch(`${base}${path}`, { ...init, headers });
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
  // Sign-in and sign-up go to the Next.js auth routes (app/api/auth): they put the tokens into HttpOnly
  // cookies and return only the user.
  signupAccount(payload: SignupPayload) {
    return apiRequest<AuthResponse>("/signup", { method: "POST", body: JSON.stringify(payload) }, "/api/auth");
  },
  login(payload: { email: string; password: string }) {
    return apiRequest<AuthResponse>("/login", { method: "POST", body: JSON.stringify(payload) }, "/api/auth");
  },
  logout() {
    return apiRequest<{ message: string }>("/logout", { method: "POST" }, "/api/auth");
  },
  me(init?: { signal?: AbortSignal }) {
    return apiRequest<AuthUser>("/api/auth/me", { signal: init?.signal });
  },
  adminDashboardStats() {
    return apiRequest<AdminDashboardStats>("/api/admin/dashboard-stats");
  },
  adminUsers(page?: PageQuery) {
    return apiRequest<Page<AdminUser>>(withPage("/api/admin/users", page));
  },
  adminPendingDoctors() {
    return apiRequest<AdminDoctor[]>("/api/admin/doctors/pending");
  },
  approveAdminDoctor(doctorId: number) {
    return apiRequest<AdminDoctor>(`/api/admin/doctors/${doctorId}/approve`, {
      method: "PATCH",
    });
  },
  rejectAdminDoctor(doctorId: number) {
    return apiRequest<AdminDoctor>(`/api/admin/doctors/${doctorId}/reject`, {
      method: "PATCH",
    });
  },
  adminRecentActivity() {
    return apiRequest<AdminActivity[]>("/api/admin/recent-activity");
  },
  patientDocument(documentId: number) {
    return apiRequest<MedicalDocument>(`/patient/reports/${documentId}`);
  },
  patientDepartmentTiles() {
    return apiRequest<DepartmentTile[]>("/patient/reports/tiles");
  },
  basicVitalsHistory() {
    return apiRequest<PatientVitals[]>("/patient/vitals/basic");
  },
  addBasicVitals(payload: { blood_pressure: string; sugar_level: string }) {
    return apiRequest<PatientVitals>("/patient/vitals/basic", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  patientVitalsToday() {
    return apiRequest<DailyVital | null>("/patient/vitals/today");
  },
  async doctors(): Promise<DoctorOption[]> {
    // Verified doctors only (FastAPI /appointments/doctors), in the workspace's shape.
    const doctors = await apiRequest<AppointmentDoctor[]>("/appointments/doctors");
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
  reports(query: ReportListQuery = {}, init?: { signal?: AbortSignal }) {
    const path = withQuery("/patient/reports", {
      limit: query.limit,
      offset: query.offset,
      q: query.q?.trim(),
      department: query.department,
      validation_status: query.validationStatus,
    });
    return apiRequest<Page<MedicalDocument>>(path, { signal: init?.signal });
  },
  uploadReport(formData: FormData) {
    return apiRequest<MedicalDocument>("/patient/reports/upload", {
      method: "POST",
      body: formData,
    });
  },
  medicines() {
    return apiRequest<MedicationSchedule[]>("/patient/medications");
  },
  createMedicineSchedule(
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
      body: JSON.stringify(payload),
    });
  },
  issueDashboardOtp() {
    return apiRequest<{ message: string; otp: { code: string; expiresAt: string } }>("/patient/dashboard-otp", {
      method: "POST",
    });
  },
  doctorOverview() {
    return apiRequest<DoctorOverview>("/doctor/overview");
  },
  unlockPatientDashboard(patientAccessOtp: string) {
    return apiRequest<{ message: string; patient: { id: number; name: string; email: string }; expiresAt: string }>(
      "/doctor/access/unlock",
      { method: "POST", body: JSON.stringify({ patientAccessOtp }) },
    );
  },
  endPatientDashboardAccess(patientId: number) {
    return apiRequest<{ message: string }>("/doctor/access/end", {
      method: "POST",
      body: JSON.stringify({ patientId }),
    });
  },
  createEmergencyRequest(
    payload: { patientName: string; phone: string; address: string; symptoms: string; latitude?: string; longitude?: string },
  ) {
    const coordinate = (value?: string) => (value && Number.isFinite(Number(value)) ? Number(value) : null);
    return apiRequest<{
      message: string;
      emergencyNotice: string;
      booking: { id: number; doctorName: string | null; status: string; estimatedMinutes: number | null };
    }>("/emergency/requests", {
      method: "POST",
      body: JSON.stringify({
        ...payload,
        latitude: coordinate(payload.latitude),
        longitude: coordinate(payload.longitude),
      }),
    });
  },
  summarizeText(text: string) {
    return apiRequest<SummaryResponse>("/nlp/summarize", {
      method: "POST",
      body: JSON.stringify({ text, category: "medical-report" }),
    });
  },
  summarizeSavedReports() {
    return apiRequest<SummaryResponse>("/nlp/summarize/saved-reports", { method: "POST" });
  },
  payments(page?: PageQuery) {
    return apiRequest<Page<Payment>>(withPage("/payments", page));
  },
  /** Opens Stripe Checkout for the patient's appointment, at the doctor's fee (set on the server). */
  startCheckout(appointmentId: number) {
    return apiRequest<CheckoutResponse>("/payments/checkout", {
      method: "POST",
      body: JSON.stringify({ appointment_id: appointmentId }),
    });
  },
  payment(id: number) {
    return apiRequest<Payment>(`/payments/${id}`);
  },
  paymentForSession(sessionId: string) {
    return apiRequest<Payment>(`/payments/session/${encodeURIComponent(sessionId)}`);
  },
  profile() {
    return apiRequest<Profile>("/profile");
  },
  updateAccount(payload: { full_name: string; phone: string }) {
    return apiRequest<Profile>("/profile/account", { method: "PATCH", body: JSON.stringify(payload) });
  },
  updatePatientProfile(payload: PatientProfileInput) {
    return apiRequest<Profile>("/patient/profile", { method: "PUT", body: JSON.stringify(payload) });
  },
  updateDoctorProfile(payload: DoctorProfileInput) {
    return apiRequest<Profile>("/doctor/profile", { method: "PUT", body: JSON.stringify(payload) });
  },
  createReminder(
    payload: {
      medicationId: number;
      reminderTime: string;
      frequency: string;
    },
  ) {
    return apiRequest<MedicineReminder>("/patient/medicine-reminders", {
      method: "POST",
      body: JSON.stringify(payload),
    });
  },
  remindersToday() {
    return apiRequest<MedicineReminder[]>("/patient/medicine-reminders/today");
  },
  markReminderTaken(reminderId: number) {
    return apiRequest<MedicineReminder>(`/patient/medicine-reminders/${reminderId}/mark-taken`, {
      method: "PATCH",
    });
  },
  skipReminder(reminderId: number) {
    return apiRequest<MedicineReminder>(`/patient/medicine-reminders/${reminderId}/skip`, {
      method: "PATCH",
    });
  },

  updateDocument(documentId: number, payload: { title?: string; department?: string; extracted_text?: string; formatted_text?: string }) {
    return apiRequest<MedicalDocument>(`/patient/reports/${documentId}`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    });
  },
  regenerateDocumentOcr(documentId: number) {
    return apiRequest<MedicalDocument>(`/patient/reports/${documentId}/regenerate-ocr`, {
      method: "POST",
    });
  },
  deleteDocument(documentId: number) {
    return apiRequest<{ message: string }>(`/patient/reports/${documentId}`, {
      method: "DELETE",
    });
  },
  /** A patient's clinical summary for the doctor (active access grant required). */
  clinicalSummary(patientId: number, init?: { signal?: AbortSignal }) {
    return apiRequest<ClinicalSummaryStatus>(`/doctor/patients/${patientId}/clinical-summary`, { signal: init?.signal });
  },
  regenerateClinicalSummary(patientId: number, init?: { signal?: AbortSignal }) {
    return apiRequest<ClinicalSummaryRegenerateResult>(`/doctor/patients/${patientId}/clinical-summary/regenerate`, {
      method: "POST",
      signal: init?.signal,
    });
  },
  clinicalSummaryVersions(patientId: number, query: { limit?: number; offset?: number } = {}) {
    return apiRequest<Page<ClinicalSummaryVersionMeta>>(
      withQuery(`/doctor/patients/${patientId}/clinical-summary/versions`, { limit: query.limit, offset: query.offset }),
    );
  },
  clinicalSummaryVersion(patientId: number, version: number) {
    return apiRequest<ClinicalSummaryVersion>(`/doctor/patients/${patientId}/clinical-summary/versions/${version}`);
  },
  /** Medicine names (generic, alias, brand), fuzzy. */
  searchMedicines(query: string, init?: { signal?: AbortSignal }) {
    return apiRequest<MedicineOption[]>(withQuery("/doctor/medicines/search", { q: query }), { signal: init?.signal });
  },
  medicineLabel(generic: string) {
    return apiRequest<LabelEvidence>(`/doctor/medicines/${encodeURIComponent(generic)}/label`);
  },
  medicationCheck(patientId: number, items: PrescriptionItemInput[], init?: { signal?: AbortSignal }) {
    return apiRequest<MedicationCheck>(`/doctor/patients/${patientId}/medication-check`, {
      method: "POST",
      body: JSON.stringify({ items }),
      signal: init?.signal,
    });
  },
  createPrescription(
    patientId: number,
    payload: { items: PrescriptionItemInput[]; overrides: { alert_id: string; justification: string }[]; notes?: string },
  ) {
    return apiRequest<Prescription>(`/doctor/patients/${patientId}/prescriptions`, { method: "POST", body: JSON.stringify(payload) });
  },
  prescriptions(patientId: number) {
    return apiRequest<Page<Prescription>>(withQuery(`/doctor/patients/${patientId}/prescriptions`, { limit: 20 }));
  },
  cancelPrescription(patientId: number, prescriptionId: number) {
    return apiRequest<Prescription>(`/doctor/patients/${patientId}/prescriptions/${prescriptionId}/cancel`, { method: "POST" });
  },
  myPrescriptions() {
    return apiRequest<Page<PatientPrescription>>(withQuery("/patient/prescriptions", { limit: 20 }));
  },
  /** What the fixed rules found in the patient's reports, in everyday words (not AI). */
  healthFlags() {
    return apiRequest<HealthFlags>("/patient/health-flags");
  },
  doctorDashboard() {
    return apiRequest<DoctorDashboard>("/doctor/dashboard");
  },
  appointmentDoctors(search: DoctorSearch = {}, init?: { signal?: AbortSignal }) {
    const path = withQuery("/appointments/doctors", {
      query: search.query?.trim(),
      specialty: search.specialty,
      city: search.city?.trim(),
      mode: search.mode,
      available_today: search.availableToday ? "true" : undefined,
      max_fee: search.maxFee,
      min_rating: search.minRating,
      sort: search.sort,
    });
    return apiRequest<AppointmentDoctor[]>(path, { signal: init?.signal });
  },
  doctorSlots(doctorId: number, days = 7, init?: { signal?: AbortSignal }) {
    return apiRequest<SlotsResponse>(`/appointments/doctors/${doctorId}/slots?days=${days}`, { signal: init?.signal });
  },
  doctorReviews(doctorId: number) {
    return apiRequest<Review[]>(`/appointments/doctors/${doctorId}/reviews?limit=5`);
  },
  bookAppointment(payload: {
    doctorId: number;
    date: string;
    mode: ConsultationMode;
    reason?: string | null;
    notes?: string | null;
    patientAccessOtp?: string | null;
  }) {
    return apiRequest<AppointmentBookingResponse>("/appointments", {
      method: "POST",
      body: JSON.stringify({
        doctor_id: payload.doctorId,
        date: payload.date,
        mode: payload.mode,
        reason: payload.reason || null,
        notes: payload.notes || null,
        patient_access_otp: payload.patientAccessOtp || null,
      }),
    });
  },
  reviewAppointment(appointmentId: number, payload: { rating: number; comment?: string | null }) {
    return apiRequest<Review>(`/appointments/${appointmentId}/review`, {
      method: "POST",
      body: JSON.stringify({ rating: payload.rating, comment: payload.comment || null }),
    });
  },
  availability() {
    return apiRequest<Availability>("/doctor/availability");
  },
  setAvailability(windows: AvailabilityWindow[]) {
    return apiRequest<Availability>("/doctor/availability", { method: "PUT", body: JSON.stringify({ windows }) });
  },
  notifications(page?: PageQuery, init?: { signal?: AbortSignal }) {
    return apiRequest<NotificationPage>(withPage("/notifications", page), { signal: init?.signal });
  },
  markNotificationRead(id: number) {
    return apiRequest<{ message: string }>(`/notifications/${id}/read`, { method: "POST" });
  },
  markAllNotificationsRead() {
    return apiRequest<{ message: string }>("/notifications/read-all", { method: "POST" });
  },
  appointments(page?: PageQuery) {
    return apiRequest<Page<Appointment>>(withPage("/appointments", page));
  },
  updateAppointment(
    appointmentId: number,
    payload: {
      date?: string;
      status?: string;
      notes?: string | null;
    },
  ) {
    return apiRequest<Appointment>(`/appointments/${appointmentId}`, {
      method: "PUT",
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
