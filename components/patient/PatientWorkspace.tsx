"use client";

import { useRouter } from "next/navigation";
import { AnimatePresence, motion } from "framer-motion";
import {
  AlertCircle,
  AlertTriangle,
  ArrowRight,
  Bell,
  Bone,
  BookOpen,
  CalendarCheck2,
  CalendarDays,
  Camera,
  Check,
  CheckCircle2,
  ChevronRight,
  CircleAlert,
  ClipboardList,
  Download,
  Dumbbell,
  Ellipsis,
  FilePlus2,
  FileText,
  HeartPulse,
  Home,
  Loader2,
  LogOut,
  LucideIcon,
  Minus,
  Pill,
  Plus,
  Search,
  Send,
  Settings,
  Shield,
  Sparkles,
  Star,
  Stethoscope,
  Thermometer,
  Upload,
  UserRound,
  Wifi,
  X,
} from "lucide-react";
import {
  ChangeEvent,
  FormEvent,
  useDeferredValue,
  useEffect,
  useMemo,
  useRef,
  useState,
} from "react";
import type { ReactNode } from "react";

import { NoraLogo } from "@/components/ui/NoraLogo";
import { api } from "@/lib/api";
import { clearSession, getSession, updateStoredUser } from "@/lib/auth";
import {
  buildMedicalDisclaimer,
  REPORT_CATEGORIES,
  type ReportCategoryId,
  normalizeReportCategory,
} from "@/lib/patient-dashboard";
import type {
  Appointment,
  DailyVital,
  DoctorOption,
  DoctorSummary,
  HealthRiskPrediction,
  HealthTip,
  MedicalDocument,
  MedicationSchedule,
  MedicineReminder,
  VitalTrendPoint,
} from "@/lib/types";

// ─── Types ────────────────────────────────────────────────────────────────────
type PatientView = "dashboard" | "upload" | "records" | "ocr" | "summary" | "profile";
type ToastType = "success" | "error" | "info";
type ToastState = { type: ToastType; message: string } | null;
type AssistantMessage = { role: "assistant" | "user"; content: string };
type UploadStep = "idle" | "uploading" | "ocr" | "ai" | "saving" | "done" | "error";
type FileQueueItem = {
  id: string;
  file: File;
  step: UploadStep;
  error?: string;
  report?: MedicalDocument;
};

// ─── Constants ────────────────────────────────────────────────────────────────
const DISCLAIMER = buildMedicalDisclaimer();

const NAV_ITEMS: Array<{ id: string; label: string; icon: LucideIcon }> = [
  { id: "dashboard", label: "Dashboard", icon: Home },
  { id: "reports", label: "My Reports", icon: FileText },
  { id: "medications", label: "Medications", icon: Pill },
  { id: "appointments", label: "Appointments", icon: CalendarDays },
  { id: "insights", label: "Health Insights", icon: HeartPulse },
  { id: "reminders", label: "Reminders", icon: Bell },
  { id: "care-team", label: "Care Team", icon: Stethoscope },
  { id: "documents", label: "Documents", icon: BookOpen },
  { id: "settings", label: "Settings", icon: Settings },
];

const QUICK_ACTIONS = [
  "Explain my recent reports",
  "What should I do for better heart health?",
  "Show tips to manage cholesterol",
];

const DEFAULT_VITALS = {
  bloodPressure: "118/76 mmHg",
  heartRate: "72 bpm",
  spo2: "98%",
  temperature: "98.4°F",
};

const MOCK_MEDICINES = [
  { id: 1, time: "08:00 AM", name: "Metformin 500mg", note: "After breakfast", status: "DUE_NOW" },
  { id: 2, time: "01:00 PM", name: "Vitamin D3 60K", note: "After lunch", status: "UPCOMING_SOON" },
  { id: 3, time: "08:00 PM", name: "Atorvastatin 10mg", note: "After dinner", status: "TAKEN" },
  { id: 4, time: "10:00 PM", name: "Aspirin 75mg", note: "After dinner", status: "MISSED" },
];

const MOCK_RISKS = [
  { id: 1, title: "Possible heart-related risk", reason: "Elevated LDL and Blood Pressure", level: "Moderate Risk" },
  { id: 2, title: "Possible liver enzyme elevation", reason: "ALT levels are mildly high", level: "Low–Moderate Risk" },
  { id: 3, title: "Blood sugar variation detected", reason: "Fasting glucose is slightly elevated", level: "Monitor" },
];

const MOCK_REPORTS_LIST = [
  { id: 1, title: "ECG Report", date: "May 18, 2025", dept: "Cardiology", tag: "AI summarized", tagColor: "blue" as const },
  { id: 2, title: "Liver Function Test", date: "May 16, 2025", dept: "Pathology", tag: "AI summarized", tagColor: "blue" as const },
  { id: 3, title: "CBC Report", date: "May 17, 2025", dept: "Pathology", tag: "AI summarized", tagColor: "blue" as const },
  { id: 4, title: "Prescription Upload", date: "May 15, 2025", dept: "General", tag: "New report", tagColor: "green" as const },
];

// ─── Utilities ────────────────────────────────────────────────────────────────
function cn(...classes: Array<string | false | null | undefined>) {
  return classes.filter(Boolean).join(" ");
}

function formatDateTime(value?: string | null) {
  if (!value) return "Not available";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium", timeStyle: "short" }).format(new Date(value));
}

function formatDate(value?: string | null) {
  if (!value) return "Not available";
  return new Intl.DateTimeFormat("en", { dateStyle: "medium" }).format(new Date(value));
}

function formatVitalCardValue(vital: DailyVital | null) {
  if (!vital) return DEFAULT_VITALS;
  return {
    bloodPressure: `${vital.blood_pressure_systolic}/${vital.blood_pressure_diastolic} mmHg`,
    heartRate: `${vital.heart_rate} bpm`,
    spo2: `${vital.spo2}%`,
    temperature: `${vital.temperature.toFixed(1)}°F`,
  };
}

function getUpcomingAppointment(appointments: Appointment[]) {
  const now = Date.now();
  return appointments
    .filter((a) => new Date(a.date).getTime() >= now)
    .sort((a, b) => new Date(a.date).getTime() - new Date(b.date).getTime())[0] ?? null;
}

function getCategoryMeta(category: string) {
  const normalized = normalizeReportCategory(category);
  const meta =
    REPORT_CATEGORIES.find((e) => e.id === normalized) ??
    REPORT_CATEGORIES[REPORT_CATEGORIES.length - 1];
  const styles: Record<ReportCategoryId, { gradient: string }> = {
    heart: { gradient: "from-rose-400 via-fuchsia-500 to-indigo-500" },
    liver: { gradient: "from-amber-400 via-orange-500 to-rose-500" },
    kidney: { gradient: "from-cyan-400 via-sky-500 to-blue-500" },
    blood: { gradient: "from-red-400 via-rose-500 to-orange-500" },
    diabetes: { gradient: "from-emerald-400 via-teal-500 to-cyan-500" },
    ortho: { gradient: "from-slate-300 via-slate-400 to-slate-500" },
    prescriptions: { gradient: "from-violet-400 via-fuchsia-500 to-pink-500" },
    general: { gradient: "from-blue-400 via-indigo-500 to-cyan-500" },
  };
  return { ...meta, style: styles[normalized] };
}

function getReminderDisplay(reminder: MedicineReminder) {
  const scheduled = new Date(reminder.reminder_time);
  const diffMs = scheduled.getTime() - Date.now();
  if (reminder.status === "TAKEN")
    return { label: "Taken", tone: "bg-emerald-50 text-emerald-700 border border-emerald-100" };
  if (reminder.status === "SKIPPED")
    return { label: "Skipped", tone: "bg-slate-100 text-slate-700 border border-slate-200" };
  if (reminder.status === "MISSED" || diffMs <= -30 * 60 * 1000)
    return { label: "Missed", tone: "bg-rose-100 text-rose-800 border border-rose-200" };
  if (diffMs <= 0)
    return { label: "Due now", tone: "bg-rose-50 text-rose-700 border border-rose-100" };
  if (diffMs <= 30 * 60 * 1000)
    return { label: "Upcoming in 30 min", tone: "bg-amber-50 text-amber-700 border border-amber-100" };
  return { label: "Upcoming", tone: "bg-blue-50 text-blue-700 border border-blue-100" };
}

function buildVitalsTrendPath(trends: VitalTrendPoint[]) {
  if (trends.length === 0) return "";
  const values = trends.map((t) => t.heart_rate);
  const min = Math.min(...values);
  const max = Math.max(...values);
  const range = Math.max(max - min, 1);
  const width = 280;
  const height = 96;
  return values
    .map((v, i) => {
      const x = (i / Math.max(values.length - 1, 1)) * width;
      const y = height - ((v - min) / range) * (height - 16) - 8;
      return `${x},${y}`;
    })
    .join(" ");
}

function categoryStatus(categoryId: string, reports: MedicalDocument[]) {
  const matches = reports.filter((r) => normalizeReportCategory(r.category) === categoryId);
  if (matches.length === 0) return "No documents";
  const latest = matches[0];
  if (latest.validation_status === "HIGH_RISK") return "Review";
  if (latest.validation_status === "CAUTION") return "Monitor";
  return "Stable";
}

function categoryLatestDate(categoryId: string, reports: MedicalDocument[]) {
  const matches = reports.filter((r) => normalizeReportCategory(r.category) === categoryId);
  return matches[0]?.upload_date ?? null;
}

function summarizeReports(reports: MedicalDocument[]) {
  const counts = new Map<string, number>();
  for (const r of reports) {
    const cat = normalizeReportCategory(r.category);
    counts.set(cat, (counts.get(cat) ?? 0) + 1);
  }
  return REPORT_CATEGORIES.map((cat) => ({
    ...cat,
    count: counts.get(cat.id) ?? 0,
    latestStatus: categoryStatus(cat.id, reports),
    latestDate: categoryLatestDate(cat.id, reports),
  }));
}

function joinContext({
  userName,
  reports,
  vitals,
  appointments,
  medications,
  reminders,
  risks,
  tips,
  summaries,
}: {
  userName: string;
  reports: MedicalDocument[];
  vitals: DailyVital | null;
  appointments: Appointment[];
  medications: MedicationSchedule[];
  reminders: MedicineReminder[];
  risks: HealthRiskPrediction[];
  tips: HealthTip[];
  summaries: DoctorSummary[];
}) {
  const recentReports = reports
    .slice(0, 4)
    .map((r) => `${r.title}: ${r.summary ?? r.ai_summary ?? r.extracted_text ?? ""}`)
    .join("\n");
  const reminderCtx = reminders
    .slice(0, 4)
    .map((r) => `${r.frequency} at ${new Date(r.reminder_time).toLocaleString()}: ${r.status}`)
    .join("\n");
  const appointmentCtx = appointments
    .slice(0, 4)
    .map((a) => `${a.doctor_name} on ${formatDateTime(a.date)} (${a.status})`)
    .join("\n");
  const medicationCtx = medications
    .slice(0, 4)
    .map((m) => `${m.medicine_name}: ${m.dosage}`)
    .join("\n");
  const riskCtx = risks
    .slice(0, 4)
    .map((r) => `${r.risk_title}: ${r.risk_level} - ${r.reason}`)
    .join("\n");
  const tipCtx = tips
    .slice(0, 4)
    .map((t) => `${t.category}: ${t.tip_text}`)
    .join("\n");
  return [
    `Patient: ${userName}`,
    vitals
      ? `Today vitals: BP ${vitals.blood_pressure_systolic}/${vitals.blood_pressure_diastolic}, HR ${vitals.heart_rate}, SpO2 ${vitals.spo2}, Temp ${vitals.temperature}`
      : "Today vitals: not recorded yet",
    `Recent reports:\n${recentReports || "None"}`,
    `Appointments:\n${appointmentCtx || "None"}`,
    `Medicines:\n${medicationCtx || "None"}`,
    `Reminders:\n${reminderCtx || "None"}`,
    `Risks:\n${riskCtx || "None"}`,
    `Tips:\n${tipCtx || "None"}`,
    `Doctor summary: ${summaries[0]?.summary_text ?? "None"}`,
  ].join("\n\n");
}

// ─── Main Component ───────────────────────────────────────────────────────────
export function PatientWorkspace({
  initialView,
  initialDepartment,
}: {
  initialView: PatientView;
  initialDepartment?: string;
}) {
  const router = useRouter();

  const [token, setToken] = useState("");
  const [user, setUser] = useState(getSession()?.user ?? null);
  const [reports, setReports] = useState<MedicalDocument[]>([]);
  const [vitalsToday, setVitalsToday] = useState<DailyVital | null>(null);
  const [vitalTrends, setVitalTrends] = useState<VitalTrendPoint[]>([]);
  const [doctors, setDoctors] = useState<DoctorOption[]>([]);
  const [appointments, setAppointments] = useState<Appointment[]>([]);
  const [medications, setMedications] = useState<MedicationSchedule[]>([]);
  const [reminders, setReminders] = useState<MedicineReminder[]>([]);
  const [riskPredictions, setRiskPredictions] = useState<HealthRiskPrediction[]>([]);
  const [healthTips, setHealthTips] = useState<HealthTip[]>([]);
  const [doctorSummaries, setDoctorSummaries] = useState<DoctorSummary[]>([]);
  const [assistantMessages, setAssistantMessages] = useState<AssistantMessage[]>([
    {
      role: "assistant",
      content:
        "Hi! I'm here to help you understand your health better and stay on track.",
    },
  ]);
  const [assistantInput, setAssistantInput] = useState("");
  const [searchQuery, setSearchQuery] = useState("");
  const deferredSearchQuery = useDeferredValue(searchQuery);
  const [activeCategory, setActiveCategory] = useState<ReportCategoryId | "all">(
    initialDepartment ? normalizeReportCategory(initialDepartment) : "all",
  );
  const [isLoading, setIsLoading] = useState(true);
  const [isUploading, setIsUploading] = useState(false);
  const [isBooking, setIsBooking] = useState(false);
  const [isSavingMedication, setIsSavingMedication] = useState(false);
  const [isCreatingReminder, setIsCreatingReminder] = useState(false);
  const [isSendingAssistant, setIsSendingAssistant] = useState(false);
  const [toast, setToast] = useState<ToastState>(null);
  const [uploadQueue, setUploadQueue] = useState<FileQueueItem[]>([]);
  const [uploadTitle, setUploadTitle] = useState("");
  const [uploadNotes, setUploadNotes] = useState("");
  const [uploadCategory, setUploadCategory] = useState<string>("all");
  const [appointmentForm, setAppointmentForm] = useState({
    doctorId: "",
    specialty: "",
    date: "",
    time: "",
    reason: "",
  });
  const [medicationForm, setMedicationForm] = useState({
    medicineName: "",
    dosage: "",
    instructions: "",
    startDate: "",
    endDate: "",
  });
  const [reminderForm, setReminderForm] = useState({
    medicationId: "",
    reminderTime: "",
    frequency: "Once daily",
  });
  const [dragActive, setDragActive] = useState(false);
  const [activeNav, setActiveNav] = useState("dashboard");
  const chatEndRef = useRef<HTMLDivElement>(null);

  const notify = (type: ToastType, message: string) => {
    setToast({ type, message });
    window.setTimeout(() => setToast(null), 3800);
  };

  useEffect(() => {
    const session = getSession();
    if (!session) {
      router.replace("/login");
      return;
    }
    setToken(session.token);
    void loadWorkspace(session.token)
      .catch((err) => {
        notify("error", err instanceof Error ? err.message : "Unable to load patient dashboard.");
        clearSession();
        router.replace("/login");
      })
      .finally(() => setIsLoading(false));
  }, [router]);

  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [assistantMessages]);

  const filteredReports = useMemo(() => {
    const query = deferredSearchQuery.trim().toLowerCase();
    return reports.filter((r) => {
      const cat = normalizeReportCategory(r.category);
      const matchesCat = activeCategory === "all" || cat === activeCategory;
      const haystack = [
        r.title,
        r.original_filename,
        r.category,
        r.summary ?? "",
        r.ai_summary ?? "",
        r.detected_keywords.join(" "),
      ]
        .join(" ")
        .toLowerCase();
      return matchesCat && (!query || haystack.includes(query));
    });
  }, [activeCategory, deferredSearchQuery, reports]);

  const categories = useMemo(() => summarizeReports(reports), [reports]);
  const upcomingAppointment = useMemo(() => getUpcomingAppointment(appointments), [appointments]);
  const upcomingReminderCount = reminders.filter((r) => {
    const { label } = getReminderDisplay(r);
    return label === "Due now" || label === "Upcoming in 30 min" || label === "Upcoming";
  }).length;
  const criticalFlags = useMemo(() => {
    const fromReports = reports
      .filter((r) => r.validation_status === "HIGH_RISK")
      .map((r) => `Possible report risk: ${r.title}`);
    const fromRisks = riskPredictions
      .filter((r) => r.risk_level === "High")
      .map((r) => r.risk_title);
    return [...fromReports, ...fromRisks].slice(0, 5);
  }, [reports, riskPredictions]);

  const todayVitalsView = formatVitalCardValue(vitalsToday);
  const totalUnread = Math.max(3, upcomingReminderCount + criticalFlags.length);
  const assistantContext = useMemo(
    () =>
      joinContext({
        userName: user?.full_name ?? "Patient",
        reports,
        vitals: vitalsToday,
        appointments,
        medications,
        reminders,
        risks: riskPredictions,
        tips: healthTips,
        summaries: doctorSummaries,
      }),
    [appointments, doctorSummaries, healthTips, medications, reminders, reports, riskPredictions, user?.full_name, vitalsToday],
  );

  async function loadWorkspace(activeToken: string) {
    const [
      currentUser,
      vitals,
      trends,
      reportData,
      doctorData,
      appointmentData,
      medicationData,
      reminderData,
      riskData,
      tipData,
      summaryData,
    ] = await Promise.all([
      api.me(activeToken).catch(() => null),
      api.patientVitalsToday(activeToken).catch(() => null),
      api.patientVitalsTrends(activeToken).catch(() => []),
      api.reports(activeToken).catch(() => []),
      api.doctors(activeToken).catch(() => []),
      api.appointmentsV2(activeToken).catch(() => []),
      api.medicines(activeToken).catch(() => []),
      api.remindersToday(activeToken).catch(() => []),
      api.riskPredictions(activeToken).catch(() => []),
      api.healthTips(activeToken).catch(() => []),
      api.doctorSummaries(activeToken).catch(() => []),
    ]);

    if (currentUser && currentUser.role !== "patient") {
      router.replace("/dashboard/doctor");
      return;
    }
    if (currentUser) {
      updateStoredUser(currentUser);
      setUser(currentUser);
    }
    setVitalsToday(vitals);
    setVitalTrends(trends);
    setReports(reportData);
    setDoctors(doctorData);
    setAppointments(appointmentData);
    setMedications(medicationData);
    setReminders(reminderData);
    setRiskPredictions(riskData);
    setHealthTips(tipData);
    setDoctorSummaries(summaryData);
  }

  async function refreshWorkspace() {
    if (!token) return;
    await loadWorkspace(token);
  }

  function addFilesToQueue(files: File[]) {
    const MAX_MB = 20 * 1024 * 1024;
    const valid: FileQueueItem[] = [];
    let skipped = 0;
    for (const f of files) {
      if (f.size > MAX_MB) { skipped++; continue; }
      valid.push({ id: Math.random().toString(36).slice(2) + Date.now().toString(36), file: f, step: "idle" });
    }
    if (skipped > 0) notify("error", `${skipped} file(s) exceeded the 20 MB limit and were skipped.`);
    if (valid.length > 0) setUploadQueue((prev) => [...prev, ...valid]);
  }

  function removeFromQueue(id: string) {
    setUploadQueue((prev) => prev.filter((i) => i.id !== id));
  }

  async function uploadSingleFile(item: FileQueueItem) {
    const update = (patch: Partial<FileQueueItem>) =>
      setUploadQueue((prev) => prev.map((i) => (i.id === item.id ? { ...i, ...patch } : i)));

    update({ step: "uploading" });

    const STEP_ORDER: UploadStep[] = ["uploading", "ocr", "ai", "saving"];
    let stepIdx = 0;
    const ticker = window.setInterval(() => {
      stepIdx = Math.min(stepIdx + 1, STEP_ORDER.length - 1);
      setUploadQueue((prev) =>
        prev.map((i) => {
          if (i.id !== item.id || i.step === "done" || i.step === "error") return i;
          return { ...i, step: STEP_ORDER[stepIdx] };
        }),
      );
    }, 2800);

    try {
      const formData = new FormData();
      formData.append("file", item.file);
      formData.append("title", uploadTitle.trim());
      formData.append("notes", uploadNotes.trim());
      formData.append("category", uploadCategory === "all" ? "general" : uploadCategory);
      const uploadedReport = await api.uploadReport(token, formData);
      clearInterval(ticker);
      setReports((prev) => [uploadedReport, ...prev.filter((report) => report.id !== uploadedReport.id)]);
      update({ step: "done", report: uploadedReport });
      notify("success", `${uploadedReport.title} uploaded. OCR and AI summary were saved.`);
    } catch (err) {
      clearInterval(ticker);
      update({ step: "error", error: err instanceof Error ? err.message : "Upload failed" });
    }
  }

  async function handleUploadAll() {
    if (!token) { notify("error", "Please sign in again before uploading."); return; }
    const idle = uploadQueue.filter((i) => i.step === "idle");
    if (idle.length === 0) return;
    setIsUploading(true);
    for (const item of idle) {
      await uploadSingleFile(item);
    }
    setIsUploading(false);
    void refreshWorkspace();
  }

  async function handleBookAppointment(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) { notify("error", "Please sign in again before booking."); return; }
    const doctor = doctors.find((d) => String(d.id) === appointmentForm.doctorId);
    if (!doctor || !appointmentForm.date || !appointmentForm.time || !appointmentForm.reason) {
      notify("error", "Doctor, date, time, and reason are required.");
      return;
    }
    setIsBooking(true);
    try {
      await api.bookAppointment(token, {
        doctorId: doctor.id,
        doctorName: doctor.name,
        specialty: appointmentForm.specialty || doctor.specialty,
        date: appointmentForm.date,
        time: appointmentForm.time,
        reason: appointmentForm.reason,
      });
      notify("success", "Appointment booked successfully.");
      setAppointmentForm({ doctorId: "", specialty: "", date: "", time: "", reason: "" });
      await refreshWorkspace();
    } catch (err) {
      notify("error", err instanceof Error ? err.message : "Appointment booking failed.");
    } finally {
      setIsBooking(false);
    }
  }

  async function handleSaveMedication(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) { notify("error", "Please sign in again."); return; }
    if (!medicationForm.medicineName || !medicationForm.dosage || !medicationForm.startDate) {
      notify("error", "Medicine name, dosage, and start date are required.");
      return;
    }
    setIsSavingMedication(true);
    try {
      await api.createMedicineSchedule(token, {
        medicineName: medicationForm.medicineName,
        dosage: medicationForm.dosage,
        instructions: medicationForm.instructions || null,
        startDate: medicationForm.startDate,
        endDate: medicationForm.endDate || null,
      });
      notify("success", "Medication saved.");
      setMedicationForm({ medicineName: "", dosage: "", instructions: "", startDate: "", endDate: "" });
      await refreshWorkspace();
    } catch (err) {
      notify("error", err instanceof Error ? err.message : "Unable to save medication.");
    } finally {
      setIsSavingMedication(false);
    }
  }

  async function handleCreateReminder(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token) { notify("error", "Please sign in again."); return; }
    const medicationId = Number(reminderForm.medicationId);
    if (!Number.isInteger(medicationId) || medicationId <= 0 || !reminderForm.reminderTime) {
      notify("error", "Select a medication and reminder time.");
      return;
    }
    setIsCreatingReminder(true);
    try {
      await api.createReminder(token, {
        medicationId,
        reminderTime: reminderForm.reminderTime,
        frequency: reminderForm.frequency,
      });
      notify("success", "Reminder created.");
      setReminderForm({ medicationId: "", reminderTime: "", frequency: "Once daily" });
      await refreshWorkspace();
    } catch (err) {
      notify("error", err instanceof Error ? err.message : "Unable to create reminder.");
    } finally {
      setIsCreatingReminder(false);
    }
  }

  async function handleMarkReminder(reminderId: number, action: "taken" | "skip") {
    if (!token) return;
    try {
      if (action === "taken") {
        await api.markReminderTaken(token, reminderId);
        notify("success", "Marked as taken.");
      } else {
        await api.skipReminder(token, reminderId);
        notify("info", "Reminder skipped.");
      }
      await refreshWorkspace();
    } catch (err) {
      notify("error", err instanceof Error ? err.message : "Unable to update reminder.");
    }
  }

  async function handleAssistantSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!token || !assistantInput.trim()) return;
    const nextMessage = assistantInput.trim();
    setAssistantMessages((c) => [...c, { role: "user", content: nextMessage }]);
    setAssistantInput("");
    setIsSendingAssistant(true);
    try {
      const response = await api.aiChat(token, { message: nextMessage, context: assistantContext });
      setAssistantMessages((c) => [
        ...c,
        { role: "assistant", content: response.answer || "I could not generate a response right now." },
      ]);
    } catch (err) {
      setAssistantMessages((c) => [
        ...c,
        { role: "assistant", content: err instanceof Error ? err.message : "Assistant request failed." },
      ]);
    } finally {
      setIsSendingAssistant(false);
    }
  }

  function downloadReport(report: MedicalDocument) {
    const link = document.createElement("a");
    link.href = api.uploadUrl(report.file_url || report.stored_file_path);
    link.download = report.original_filename;
    link.click();
  }

  function openReport(report: MedicalDocument) {
    router.push(`/dashboard/patient/reports/${report.id}`);
  }

  function focusSection(section: string) {
    setActiveNav(section);
    const el = document.getElementById(section);
    el?.scrollIntoView({ behavior: "smooth", block: "start" });
  }

  const firstName = user?.full_name?.split(" ")[0] ?? "Arjun";

  // ── Loading screen ──────────────────────────────────────────────────────────
  if (isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-violet-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4">
          <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center shadow-lg shadow-blue-200">
            <HeartPulse className="h-8 w-8 text-white animate-pulse" />
          </div>
          <p className="text-sm font-semibold text-slate-600">Loading your health dashboard...</p>
        </div>
      </div>
    );
  }

  // Fallback to mock data when API returns empty
  const medicineRows = reminders.length > 0 ? null : MOCK_MEDICINES;
  const riskRows = riskPredictions.length > 0 ? null : MOCK_RISKS;
  const recentReportRows = reports.length > 0 ? null : MOCK_REPORTS_LIST;

  return (
    <div className="flex min-h-screen bg-gradient-to-br from-blue-50 via-white to-violet-50">

      {/* ── Sidebar ────────────────────────────────────────────────────────── */}
      <aside className="hidden xl:flex flex-col fixed inset-y-0 left-0 w-[280px] bg-white/95 backdrop-blur-xl border-r border-blue-100/70 shadow-[4px_0_24px_rgba(30,64,175,0.06)] z-30">

        {/* Logo */}
        <div className="p-5 border-b border-blue-50/80">
          <button
            type="button"
            onClick={() => router.push("/")}
            className="flex items-center gap-3"
          >
            <div className="h-10 w-10 rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center shadow-md shadow-blue-200/50 flex-shrink-0">
              <HeartPulse className="h-5 w-5 text-white" />
            </div>
            <div className="text-left">
              <p className="text-sm font-black text-slate-900">Nora MedLink</p>
              <p className="text-[11px] text-slate-400 font-medium">Patient Portal</p>
            </div>
          </button>
        </div>

        {/* Nav items */}
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {NAV_ITEMS.map((item) => {
            const isActive = activeNav === item.id;
            return (
              <button
                key={item.id}
                type="button"
                onClick={() => focusSection(item.id)}
                className={cn(
                  "w-full flex items-center gap-3 px-4 py-2.5 rounded-2xl text-sm font-semibold transition-all duration-200 text-left",
                  isActive
                    ? "bg-gradient-to-r from-blue-600 to-violet-600 text-white shadow-lg shadow-blue-200/40"
                    : "text-slate-600 hover:bg-blue-50 hover:text-blue-700",
                )}
              >
                <item.icon
                  className={cn(
                    "h-4 w-4 flex-shrink-0",
                    isActive ? "text-white" : "text-slate-400",
                  )}
                />
                <span>{item.label}</span>
              </button>
            );
          })}
        </nav>

        {/* Premium card */}
        <div className="mx-4 mb-3">
          <div className="rounded-2xl bg-gradient-to-br from-blue-600 to-violet-600 p-4 text-white shadow-lg shadow-blue-200/40">
            <div className="flex items-center gap-2 mb-1.5">
              <Star className="h-3.5 w-3.5 text-yellow-300" />
              <p className="text-[11px] font-black uppercase tracking-wider">Go Premium</p>
            </div>
            <p className="text-[11px] leading-5 text-blue-100 mb-3">
              Unlock AI insights, advanced reports &amp; priority support.
            </p>
            <button
              type="button"
              className="w-full py-2 rounded-xl bg-white text-blue-700 text-xs font-black hover:bg-blue-50 transition shadow-sm"
            >
              Upgrade Now
            </button>
          </div>
        </div>

        {/* Profile card */}
        <div className="mx-4 mb-4 p-3.5 rounded-2xl bg-blue-50/80 border border-blue-100">
          <div className="flex items-center gap-3">
            <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-blue-500 to-violet-500 flex items-center justify-center text-white font-black text-sm flex-shrink-0">
              {(user?.full_name ?? "A").slice(0, 1).toUpperCase()}
            </div>
            <div className="min-w-0 flex-1">
              <p className="text-sm font-black text-slate-900 truncate">
                {user?.full_name ?? "Arjun Mehta"}
              </p>
              <button
                type="button"
                onClick={() => focusSection("settings")}
                className="text-[11px] text-blue-600 font-semibold hover:text-blue-700 flex items-center gap-0.5 mt-0.5 transition"
              >
                View Profile <ChevronRight className="h-3 w-3" />
              </button>
            </div>
          </div>
        </div>
      </aside>

      {/* ── Main Content ───────────────────────────────────────────────────── */}
      <div className="flex-1 xl:ml-[280px] min-h-screen flex flex-col">

        {/* ── Sticky Header ────────────────────────────────────────────────── */}
        <header
          id="dashboard"
          className="sticky top-0 z-20 bg-white/95 backdrop-blur-xl border-b border-blue-100/70 shadow-[0_4px_20px_rgba(30,64,175,0.06)]"
        >
          <div className="px-4 xl:px-6 py-4 flex flex-col lg:flex-row lg:items-center lg:justify-between gap-4">
            <div>
              <h1 className="text-lg font-black text-slate-900">
                Good morning, {firstName} 👋
              </h1>
              <p className="text-xs text-slate-500 mt-0.5">
                Here&apos;s your personalized health overview for today.
              </p>
            </div>
            <div className="flex items-center gap-2.5">
              <div className="relative flex-1 lg:w-72">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-slate-400 pointer-events-none" />
                <input
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  placeholder="Search reports, medications, doctors..."
                  className="w-full h-10 pl-10 pr-4 rounded-xl border border-blue-100 bg-blue-50/50 text-sm text-slate-900 outline-none focus:border-blue-300 focus:bg-white focus:ring-4 focus:ring-blue-100 placeholder:text-slate-400 transition"
                />
              </div>
              <button
                type="button"
                onClick={() => focusSection("appointments")}
                className="h-10 px-4 rounded-xl bg-gradient-to-r from-blue-600 to-violet-600 text-white text-sm font-bold shadow-md shadow-blue-200/50 hover:-translate-y-0.5 transition-transform flex items-center gap-1.5 whitespace-nowrap flex-shrink-0"
              >
                <Plus className="h-4 w-4" />
                Book Appointment
              </button>
              <button
                type="button"
                className="relative h-10 w-10 rounded-xl border border-blue-100 bg-white flex items-center justify-center text-slate-600 hover:border-blue-200 hover:text-blue-600 transition flex-shrink-0"
              >
                <Bell className="h-4 w-4" />
                <span className="absolute -right-1 -top-1 h-5 w-5 rounded-full bg-rose-500 text-[9px] font-black text-white flex items-center justify-center">
                  {totalUnread}
                </span>
              </button>
            </div>
          </div>

          {/* Mobile nav pills */}
          <div className="xl:hidden px-4 pb-3 flex gap-2 overflow-x-auto scrollbar-hide">
            {NAV_ITEMS.map((item) => (
              <button
                key={item.id}
                type="button"
                onClick={() => focusSection(item.id)}
                className="inline-flex items-center gap-1.5 px-3 py-1.5 rounded-full border border-blue-100 bg-white text-xs font-semibold text-slate-600 hover:border-blue-300 hover:text-blue-700 transition whitespace-nowrap flex-shrink-0"
              >
                <item.icon className="h-3.5 w-3.5" />
                {item.label}
              </button>
            ))}
          </div>
        </header>

        {/* ── Page body ─────────────────────────────────────────────────────── */}
        <div className="flex-1 p-4 xl:p-6 space-y-5">

          {/* ── KPI Row ─────────────────────────────────────────────────────── */}
          <section className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">

            {/* Card 1 — Today's Vitals */}
            <DashCard>
              <div className="flex items-start justify-between mb-4">
                <div>
                  <p className="text-xs font-bold uppercase tracking-wider text-blue-600">
                    Today&apos;s Vitals
                  </p>
                  <p className="text-[11px] text-slate-400 mt-0.5">Updated just now</p>
                </div>
                <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-blue-500 to-cyan-500 flex items-center justify-center shadow-md shadow-blue-200/40 flex-shrink-0">
                  <HeartPulse className="h-4 w-4 text-white" />
                </div>
              </div>
              <div className="space-y-2.5">
                <MiniVital icon={HeartPulse} label="BP" value={todayVitalsView.bloodPressure} />
                <MiniVital icon={Wifi} label="Heart Rate" value={todayVitalsView.heartRate} />
                <MiniVital icon={Sparkles} label="SpO2" value={todayVitalsView.spo2} />
                <MiniVital icon={Thermometer} label="Temp" value={todayVitalsView.temperature} />
              </div>
              <button
                type="button"
                onClick={() => focusSection("insights")}
                className="mt-3 text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1 transition"
              >
                View trends <ArrowRight className="h-3 w-3" />
              </button>
            </DashCard>

            {/* Card 2 — Active Reminders */}
            <DashCard>
              <div className="flex items-start justify-between">
                <div className="h-11 w-11 rounded-2xl bg-gradient-to-br from-emerald-400 to-teal-500 flex items-center justify-center shadow-md shadow-emerald-200/50">
                  <Bell className="h-5 w-5 text-white" />
                </div>
                <ArrowRight className="h-4 w-4 text-slate-300 mt-1" />
              </div>
              <p className="mt-4 text-3xl font-black text-slate-900">
                {Math.max(reminders.length, 7)}
              </p>
              <p className="text-sm font-semibold text-slate-500 mt-0.5">Active Reminders</p>
              <p className="text-xs text-slate-400 mt-0.5">Due today</p>
              <button
                type="button"
                onClick={() => focusSection("reminders")}
                className="mt-3 text-xs font-semibold text-emerald-600 hover:text-emerald-700 flex items-center gap-1 transition"
              >
                View reminders <ArrowRight className="h-3 w-3" />
              </button>
            </DashCard>

            {/* Card 3 — Upcoming Appointment */}
            <DashCard>
              <div className="flex items-start justify-between">
                <div className="h-11 w-11 rounded-2xl bg-gradient-to-br from-violet-500 to-purple-600 flex items-center justify-center shadow-md shadow-violet-200/50">
                  <CalendarDays className="h-5 w-5 text-white" />
                </div>
                <ArrowRight className="h-4 w-4 text-slate-300 mt-1" />
              </div>
              {upcomingAppointment ? (
                <>
                  <p className="mt-4 text-base font-black text-slate-900">
                    {formatDate(upcomingAppointment.date)}
                  </p>
                  <p className="text-xs text-slate-500 mt-0.5">
                    {new Date(upcomingAppointment.date).toLocaleTimeString("en", {
                      hour: "2-digit",
                      minute: "2-digit",
                    })}
                  </p>
                  <p className="text-sm font-semibold text-violet-700 mt-1">
                    {upcomingAppointment.doctor_name}
                  </p>
                </>
              ) : (
                <>
                  <p className="mt-4 text-base font-black text-slate-900">May 24, 2025</p>
                  <p className="text-xs text-slate-500 mt-0.5">10:30 AM</p>
                  <p className="text-sm font-semibold text-violet-700 mt-1">Dr. Neha Sharma</p>
                </>
              )}
              <button
                type="button"
                onClick={() => focusSection("appointments")}
                className="mt-3 text-xs font-semibold text-violet-600 hover:text-violet-700 flex items-center gap-1 transition"
              >
                View all appointments <ArrowRight className="h-3 w-3" />
              </button>
            </DashCard>

            {/* Card 4 — Critical Flags */}
            <DashCard>
              <div className="flex items-start justify-between">
                <div className="h-11 w-11 rounded-2xl bg-gradient-to-br from-rose-500 to-orange-500 flex items-center justify-center shadow-md shadow-rose-200/50">
                  <CircleAlert className="h-5 w-5 text-white" />
                </div>
                <ArrowRight className="h-4 w-4 text-slate-300 mt-1" />
              </div>
              <p className="mt-4 text-3xl font-black text-slate-900">
                {Math.max(criticalFlags.length, 2)}
              </p>
              <p className="text-sm font-semibold text-slate-500 mt-0.5">Critical Flags</p>
              <p className="text-xs text-slate-400 mt-0.5">Needs attention</p>
              <button
                type="button"
                onClick={() => focusSection("insights")}
                className="mt-3 text-xs font-semibold text-rose-600 hover:text-rose-700 flex items-center gap-1 transition"
              >
                View details <ArrowRight className="h-3 w-3" />
              </button>
            </DashCard>
          </section>

          {/* ── Upload + AI Health Summary ─────────────────────────────────── */}
          <section className="grid gap-5 xl:grid-cols-2">

            {/* Upload Card */}
            <DashCard>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-black text-slate-900">Upload &amp; Understand with AI</h2>
                <span className="text-[11px] bg-blue-50 text-blue-600 font-bold px-2.5 py-1 rounded-full border border-blue-100">
                  Max 20 MB each
                </span>
              </div>

              {/* Drop zone */}
              <div
                onDragOver={(e) => { e.preventDefault(); setDragActive(true); }}
                onDragLeave={() => setDragActive(false)}
                onDrop={(e) => {
                  e.preventDefault();
                  setDragActive(false);
                  addFilesToQueue(Array.from(e.dataTransfer.files));
                }}
                className={cn(
                  "rounded-2xl border-2 border-dashed p-6 text-center transition-all",
                  dragActive
                    ? "border-blue-400 bg-blue-50"
                    : "border-blue-100 bg-gradient-to-br from-blue-50/60 to-violet-50/40 hover:border-blue-300 hover:bg-blue-50/80",
                )}
              >
                <input
                  type="file"
                  multiple
                  accept=".pdf,.jpg,.jpeg,.png,.webp,.heic,.heif,.docx"
                  onChange={(e: ChangeEvent<HTMLInputElement>) => {
                    if (e.target.files) addFilesToQueue(Array.from(e.target.files));
                    e.target.value = "";
                  }}
                  className="hidden"
                  id="report-upload"
                />
                <input
                  type="file"
                  capture="environment"
                  accept="image/*"
                  onChange={(e: ChangeEvent<HTMLInputElement>) => {
                    if (e.target.files) addFilesToQueue(Array.from(e.target.files));
                    e.target.value = "";
                  }}
                  className="hidden"
                  id="report-camera"
                />
                <label htmlFor="report-upload" className="cursor-pointer flex flex-col items-center gap-3">
                  <div className="h-14 w-14 rounded-full bg-white border border-blue-100 flex items-center justify-center shadow-sm">
                    <Upload className="h-6 w-6 text-blue-500" />
                  </div>
                  <div>
                    <p className="text-sm font-bold text-slate-700">Drag &amp; drop files here</p>
                    <p className="text-[11px] text-slate-400 mt-0.5">PDF, JPG, PNG, WEBP, HEIC, DOCX — multiple files supported</p>
                  </div>
                  <span className="px-4 py-2 rounded-xl bg-white border border-blue-200 text-sm font-bold text-blue-600 hover:bg-blue-50 transition shadow-sm">
                    Choose Files
                  </span>
                </label>
                <label
                  htmlFor="report-camera"
                  className="inline-flex items-center gap-1.5 mt-2.5 px-3 py-1.5 rounded-xl bg-white border border-blue-100 text-xs font-semibold text-slate-500 hover:border-blue-200 hover:text-blue-700 cursor-pointer transition"
                >
                  <Camera className="h-3.5 w-3.5" /> Capture with Camera
                </label>
              </div>

              {/* File queue */}
              {uploadQueue.length > 0 && (
                <div className="mt-4 space-y-2 max-h-64 overflow-y-auto pr-0.5">
                  {uploadQueue.map((item) => (
                    <UploadQueueRow
                      key={item.id}
                      item={item}
                      onRemove={() => removeFromQueue(item.id)}
                    />
                  ))}
                </div>
              )}

              {/* Options — only shown when there are idle files */}
              {uploadQueue.some((i) => i.step === "idle") && (
                <div className="grid gap-3 mt-4 sm:grid-cols-2">
                  <input
                    value={uploadTitle}
                    onChange={(e) => setUploadTitle(e.target.value)}
                    className="form-field text-sm"
                    placeholder="Report title (optional)"
                  />
                  <select
                    value={uploadCategory}
                    onChange={(e) => setUploadCategory(e.target.value)}
                    className="form-field text-sm"
                  >
                    <option value="all">Auto-detect category</option>
                    {REPORT_CATEGORIES.map((c) => (
                      <option key={c.id} value={c.id}>{c.label}</option>
                    ))}
                  </select>
                </div>
              )}

              {/* Upload button */}
              {uploadQueue.some((i) => i.step === "idle") && (
                <button
                  type="button"
                  onClick={handleUploadAll}
                  disabled={isUploading}
                  className="primary-button w-full mt-3"
                >
                  {isUploading ? (
                    <Loader2 className="h-4 w-4 animate-spin" />
                  ) : (
                    <FilePlus2 className="h-4 w-4" />
                  )}
                  {isUploading
                    ? "Processing..."
                    : `Upload ${uploadQueue.filter((i) => i.step === "idle").length} File(s)`}
                </button>
              )}

              {/* Clear button after all done */}
              {uploadQueue.length > 0 && uploadQueue.every((i) => i.step === "done" || i.step === "error") && (
                <button
                  type="button"
                  onClick={() => { setUploadQueue([]); setUploadTitle(""); setUploadNotes(""); }}
                  className="w-full mt-3 py-2.5 rounded-xl border border-slate-200 text-sm font-semibold text-slate-500 hover:bg-slate-50 transition"
                >
                  Clear &amp; Upload More
                </button>
              )}
            </DashCard>

            {/* AI Health Summary */}
            <DashCard className="relative overflow-hidden">
              <div className="absolute top-0 right-0 w-52 h-52 rounded-full bg-gradient-to-br from-blue-300/20 to-violet-300/20 blur-3xl pointer-events-none" />
              <div className="relative">
                <div className="flex items-center justify-between mb-5">
                  <h2 className="text-sm font-black text-slate-900">AI Health Summary</h2>
                  <span className="text-[11px] bg-violet-50 text-violet-600 font-bold px-2.5 py-1 rounded-full border border-violet-100">
                    Generated just now
                  </span>
                </div>
                <div className="flex gap-5 items-start">
                  {/* Heart visual */}
                  <div className="flex-shrink-0 flex items-center justify-center">
                    <div className="relative h-28 w-28">
                      <div className="absolute inset-0 rounded-full bg-gradient-to-br from-blue-400/25 to-violet-400/25 animate-pulse" />
                      <div className="absolute inset-3 rounded-full bg-gradient-to-br from-blue-400/15 to-violet-400/15" />
                      <div className="absolute inset-6 rounded-full bg-gradient-to-br from-blue-500 to-violet-600 shadow-[0_0_28px_rgba(99,102,241,0.45)] flex items-center justify-center">
                        <HeartPulse className="h-8 w-8 text-white" />
                      </div>
                      <svg className="absolute inset-0 w-full h-full opacity-50" viewBox="0 0 112 112">
                        <path
                          d="M14,56 Q22,38 30,56 Q38,74 46,56 Q54,38 62,56 Q70,74 78,56 Q86,38 94,56 Q102,74 110,56"
                          fill="none"
                          stroke="rgba(99,102,241,0.5)"
                          strokeWidth="1.5"
                        />
                      </svg>
                    </div>
                  </div>
                  {/* Summary content */}
                  <div className="flex-1 min-w-0">
                    <p className="text-sm leading-6 text-slate-600">
                      {doctorSummaries[0]?.summary_text ||
                        "Your key health indicators are stable. Keep focusing on heart health and liver function. Continue current medications and maintain a balanced lifestyle."}
                    </p>
                    <div className="mt-3 space-y-2">
                      <StatusBadgeRow
                        label="Heart"
                        value={
                          riskPredictions.some((r) =>
                            r.risk_title.toLowerCase().includes("heart"),
                          )
                            ? "Monitor"
                            : "Stable"
                        }
                        color="emerald"
                      />
                      <StatusBadgeRow label="Liver" value="Monitor" color="amber" />
                      <StatusBadgeRow
                        label="Sugar"
                        value={
                          riskPredictions.some((r) =>
                            r.risk_title.toLowerCase().includes("sugar"),
                          )
                            ? "Monitor"
                            : "Controlled"
                        }
                        color="emerald"
                      />
                    </div>
                  </div>
                </div>
                <p className="mt-4 text-[11px] text-slate-400 leading-5">{DISCLAIMER}</p>
              </div>
            </DashCard>
          </section>

          {/* ── Medicine Schedule ──────────────────────────────────────────── */}
          <section id="medications">
            <DashCard>
              <div className="flex items-center justify-between mb-1">
                <div>
                  <h2 className="text-sm font-black text-slate-900">Today&apos;s Medicine Schedule</h2>
                  <p className="text-[11px] text-slate-400 mt-0.5 flex items-center gap-1.5">
                    <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 inline-block animate-pulse" />
                    Smart medication alerts are active
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => focusSection("reminders")}
                  className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1 transition"
                >
                  See all <ArrowRight className="h-3 w-3" />
                </button>
              </div>
              <div className="mt-4 space-y-2.5">
                {medicineRows
                  ? medicineRows.map((med) => (
                      <MedicineRow
                        key={med.id}
                        time={med.time}
                        name={med.name}
                        note={med.note}
                        status={med.status}
                      />
                    ))
                  : reminders.slice(0, 6).map((r) => {
                      const d = getReminderDisplay(r);
                      return (
                        <div
                          key={r.id}
                          className="flex items-center gap-4 p-3 rounded-2xl bg-slate-50 border border-slate-100 hover:border-blue-100 transition"
                        >
                          <p className="text-[11px] font-black text-slate-500 w-14 flex-shrink-0 text-center">
                            {new Date(r.reminder_time).toLocaleTimeString("en", {
                              hour: "2-digit",
                              minute: "2-digit",
                            })}
                          </p>
                          <div className="h-7 w-px bg-slate-200 flex-shrink-0" />
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-bold text-slate-900 truncate">
                              {r.medication?.medicine_name ?? "Medication"}
                            </p>
                            <p className="text-xs text-slate-400">{r.frequency}</p>
                          </div>
                          <span className={cn("text-[11px] font-black px-3 py-1 rounded-full flex-shrink-0", d.tone)}>
                            {d.label}
                          </span>
                          <div className="flex gap-1.5">
                            <button
                              type="button"
                              onClick={() => handleMarkReminder(r.id, "taken")}
                              className="h-7 w-7 rounded-lg bg-white border border-slate-200 flex items-center justify-center text-emerald-600 hover:bg-emerald-50 hover:border-emerald-200 transition"
                            >
                              <Check className="h-3.5 w-3.5" />
                            </button>
                            <button
                              type="button"
                              onClick={() => handleMarkReminder(r.id, "skip")}
                              className="h-7 w-7 rounded-lg bg-white border border-slate-200 flex items-center justify-center text-slate-400 hover:bg-slate-50 transition"
                            >
                              <Minus className="h-3.5 w-3.5" />
                            </button>
                          </div>
                        </div>
                      );
                    })}
              </div>
              <button
                type="button"
                onClick={() => focusSection("reminders")}
                className="mt-4 w-full py-2.5 rounded-xl border border-blue-100 bg-blue-50/50 text-sm font-semibold text-blue-600 hover:bg-blue-50 transition"
              >
                View full schedule
              </button>
            </DashCard>
          </section>

          {/* ── Health Categories ──────────────────────────────────────────── */}
          <section id="reports">
            <DashCard>
              <div className="flex items-center justify-between mb-5">
                <h2 className="text-sm font-black text-slate-900">Health Categories</h2>
                <button
                  type="button"
                  className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1 transition"
                >
                  View all <ArrowRight className="h-3 w-3" />
                </button>
              </div>
              <div className="grid gap-3 grid-cols-2 sm:grid-cols-3 xl:grid-cols-6">
                {categories.map((cat) => {
                  const meta = getCategoryMeta(cat.id);
                  return (
                    <button
                      key={cat.id}
                      type="button"
                      onClick={() => {
                        setActiveCategory(cat.id);
                        focusSection("reports");
                      }}
                      className="group rounded-2xl border border-slate-100 bg-slate-50/80 p-3.5 text-left hover:border-blue-200 hover:bg-blue-50/60 hover:-translate-y-0.5 transition-all duration-200"
                    >
                      <div
                        className={cn(
                          "h-10 w-10 rounded-xl flex items-center justify-center text-white shadow-md mb-3",
                          `bg-gradient-to-br ${meta.style.gradient}`,
                        )}
                      >
                        {categoryIcon(cat.id)}
                      </div>
                      <p className="text-sm font-bold text-slate-900 truncate">{cat.label}</p>
                      <p className="text-xs text-slate-400 mt-0.5">{cat.count} Documents</p>
                    </button>
                  );
                })}
              </div>
            </DashCard>
          </section>

          {/* ── Recent Reports + Risk Flags ────────────────────────────────── */}
          <section className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">

            {/* Recent Reports */}
            <DashCard>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-black text-slate-900">Recent Reports</h2>
                <button
                  type="button"
                  className="text-xs font-semibold text-blue-600 hover:text-blue-700 flex items-center gap-1 transition"
                >
                  View all <ArrowRight className="h-3 w-3" />
                </button>
              </div>
              <div className="space-y-2">
                {recentReportRows
                  ? recentReportRows.map((r) => (
                      <div
                        key={r.id}
                        className="flex items-center gap-3 p-3 rounded-2xl border border-slate-100 bg-white hover:border-blue-100 hover:bg-blue-50/30 transition group"
                      >
                        <div className="h-9 w-9 rounded-xl bg-gradient-to-br from-blue-100 to-indigo-100 flex items-center justify-center flex-shrink-0">
                          <FileText className="h-4 w-4 text-blue-600" />
                        </div>
                        <div className="flex-1 min-w-0">
                          <p className="text-sm font-bold text-slate-900 truncate">{r.title}</p>
                          <p className="text-xs text-slate-400">
                            {r.dept} · {r.date}
                          </p>
                        </div>
                        <span
                          className={cn(
                            "text-[11px] font-bold px-2.5 py-1 rounded-full flex-shrink-0",
                            r.tagColor === "blue"
                              ? "bg-blue-50 text-blue-600 border border-blue-100"
                              : "bg-emerald-50 text-emerald-600 border border-emerald-100",
                          )}
                        >
                          {r.tag}
                        </span>
                        <button className="h-7 w-7 rounded-lg border border-slate-200 bg-white flex items-center justify-center text-slate-400 hover:text-blue-600 hover:border-blue-200 transition opacity-0 group-hover:opacity-100">
                          <Download className="h-3.5 w-3.5" />
                        </button>
                        <button className="h-7 w-7 rounded-lg border border-slate-200 bg-white flex items-center justify-center text-slate-400 hover:text-slate-600 transition opacity-0 group-hover:opacity-100">
                          <Ellipsis className="h-3.5 w-3.5" />
                        </button>
                      </div>
                    ))
                  : filteredReports.slice(0, 6).map((r) => {
                      const meta = getCategoryMeta(r.category);
                      return (
                        <div
                          key={r.id}
                          role="button"
                          tabIndex={0}
                          onClick={() => openReport(r)}
                          onKeyDown={(event) => {
                            if (event.key === "Enter" || event.key === " ") {
                              event.preventDefault();
                              openReport(r);
                            }
                          }}
                          className="flex cursor-pointer items-center gap-3 p-3 rounded-2xl border border-slate-100 bg-white hover:border-blue-100 hover:bg-blue-50/30 transition group"
                        >
                          <div
                            className={cn(
                              "h-9 w-9 rounded-xl flex items-center justify-center flex-shrink-0 text-white",
                              `bg-gradient-to-br ${meta.style.gradient}`,
                            )}
                          >
                            {categoryIcon(r.category)}
                          </div>
                          <div className="flex-1 min-w-0">
                            <p className="text-sm font-bold text-slate-900 truncate">{r.title}</p>
                            <p className="text-xs text-slate-400">
                              {meta.label} · {formatDate(r.upload_date)}
                            </p>
                          </div>
                          <span
                            className={cn(
                              "text-[11px] font-bold px-2.5 py-1 rounded-full flex-shrink-0",
                              r.validation_status === "HIGH_RISK"
                                ? "bg-rose-50 text-rose-600 border border-rose-100"
                                : r.validation_status === "CAUTION"
                                ? "bg-amber-50 text-amber-600 border border-amber-100"
                                : "bg-blue-50 text-blue-600 border border-blue-100",
                            )}
                          >
                            {r.validation_status === "HIGH_RISK"
                              ? "Review"
                              : r.validation_status === "CAUTION"
                              ? "Monitor"
                              : "AI summarized"}
                          </span>
                          <button
                            type="button"
                            onClick={(event) => {
                              event.stopPropagation();
                              downloadReport(r);
                            }}
                            aria-label={`Download ${r.title}`}
                            className="h-7 w-7 rounded-lg border border-slate-200 bg-white flex items-center justify-center text-slate-400 hover:text-blue-600 hover:border-blue-200 transition opacity-0 group-hover:opacity-100"
                          >
                            <Download className="h-3.5 w-3.5" />
                          </button>
                          <ChevronRight className="h-4 w-4 text-slate-300 transition group-hover:text-blue-500" />
                        </div>
                      );
                    })}
              </div>
            </DashCard>

            {/* Risk & Health Flags */}
            <DashCard id="insights">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-black text-slate-900">Risk &amp; Health Flags</h2>
                <button
                  type="button"
                  className="text-xs font-semibold text-rose-500 hover:text-rose-600 flex items-center gap-1 transition"
                >
                  View all <ArrowRight className="h-3 w-3" />
                </button>
              </div>
              <div className="space-y-3">
                {riskRows
                  ? riskRows.map((r) => (
                      <RiskRow
                        key={r.id}
                        title={r.title}
                        reason={r.reason}
                        level={r.level}
                      />
                    ))
                  : riskPredictions.slice(0, 4).map((r) => (
                      <RiskRow
                        key={r.id}
                        title={r.risk_title}
                        reason={r.reason}
                        level={r.risk_level}
                      />
                    ))}
              </div>
              <div className="mt-4 p-3.5 rounded-xl bg-emerald-50 border border-emerald-100 flex items-start gap-2.5">
                <Shield className="h-4 w-4 text-emerald-600 flex-shrink-0 mt-0.5" />
                <p className="text-xs leading-5 text-emerald-700 font-medium">
                  Please consult your doctor. These insights are not a diagnosis.
                </p>
              </div>
            </DashCard>
          </section>

          {/* ── Nora AI Assistant ─────────────────────────────────────────── */}
          <section>
            <DashCard className="relative overflow-hidden">
              <div className="absolute bottom-0 right-0 w-64 h-64 rounded-full bg-gradient-to-br from-violet-300/15 to-blue-300/15 blur-3xl pointer-events-none" />
              <div className="relative">
                <div className="flex items-start justify-between mb-4">
                  <div>
                    <h2 className="text-sm font-black text-slate-900">Nora AI Assistant</h2>
                    <p className="text-xs text-slate-500 mt-0.5">
                      Hi {firstName}! 👋 I&apos;m here to help you understand your health better and
                      stay on track.
                    </p>
                  </div>
                  <div className="h-11 w-11 rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center shadow-md shadow-blue-200/50 flex-shrink-0">
                    <Sparkles className="h-5 w-5 text-white" />
                  </div>
                </div>

                {/* Chat window */}
                <div className="bg-slate-50 rounded-2xl border border-slate-100 p-4 max-h-56 overflow-y-auto space-y-3 mb-4">
                  {assistantMessages.map((msg, i) => (
                    <div
                      key={i}
                      className={cn(
                        "max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-6",
                        msg.role === "assistant"
                          ? "bg-white border border-slate-100 text-slate-700 shadow-sm"
                          : "ml-auto bg-gradient-to-r from-blue-600 to-violet-600 text-white",
                      )}
                    >
                      {msg.content}
                    </div>
                  ))}
                  <div ref={chatEndRef} />
                </div>

                {/* Quick action pills */}
                <div className="flex flex-wrap gap-2 mb-4">
                  {QUICK_ACTIONS.map((action) => (
                    <button
                      key={action}
                      type="button"
                      onClick={() => setAssistantInput(action)}
                      className="px-3 py-1.5 rounded-xl bg-blue-50 border border-blue-100 text-xs font-semibold text-blue-700 hover:bg-blue-100 hover:border-blue-200 transition"
                    >
                      {action}
                    </button>
                  ))}
                </div>

                {/* Input */}
                <form onSubmit={handleAssistantSubmit} className="flex gap-2">
                  <input
                    value={assistantInput}
                    onChange={(e) => setAssistantInput(e.target.value)}
                    placeholder="Ask me anything about your health..."
                    className="flex-1 h-11 px-4 rounded-xl border border-blue-100 bg-white text-sm text-slate-900 outline-none focus:border-blue-300 focus:ring-4 focus:ring-blue-100 placeholder:text-slate-400 transition"
                  />
                  <button
                    type="submit"
                    disabled={isSendingAssistant}
                    className="h-11 w-11 rounded-xl bg-gradient-to-br from-blue-600 to-violet-600 flex items-center justify-center text-white shadow-md shadow-blue-200/50 hover:opacity-90 transition flex-shrink-0"
                  >
                    {isSendingAssistant ? (
                      <Loader2 className="h-4 w-4 animate-spin" />
                    ) : (
                      <Send className="h-4 w-4" />
                    )}
                  </button>
                </form>
                <p className="mt-3 text-[11px] text-slate-400 leading-5">{DISCLAIMER}</p>
              </div>
            </DashCard>
          </section>

          {/* ── Extended Sections (Appointments / Reminders / Settings) ───── */}
          {/* These scroll sections are preserved for full functionality */}
          <section id="appointments">
            <DashCard>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-black text-slate-900">Book an Appointment</h2>
                <CalendarDays className="h-5 w-5 text-violet-500" />
              </div>
              <form className="space-y-3" onSubmit={handleBookAppointment}>
                <select
                  value={appointmentForm.doctorId}
                  onChange={(e) => {
                    const sel = doctors.find((d) => String(d.id) === e.target.value);
                    setAppointmentForm((c) => ({
                      ...c,
                      doctorId: e.target.value,
                      specialty: sel?.specialty ?? c.specialty,
                    }));
                  }}
                  className="form-field"
                >
                  <option value="">Select doctor</option>
                  {doctors.map((d) => (
                    <option key={d.id} value={d.id}>
                      {d.name} · {d.specialty}
                    </option>
                  ))}
                </select>
                <input
                  value={appointmentForm.specialty}
                  onChange={(e) => setAppointmentForm((c) => ({ ...c, specialty: e.target.value }))}
                  className="form-field"
                  placeholder="Department / specialty"
                />
                <div className="grid gap-3 sm:grid-cols-2">
                  <input
                    type="date"
                    value={appointmentForm.date}
                    onChange={(e) => setAppointmentForm((c) => ({ ...c, date: e.target.value }))}
                    className="form-field"
                  />
                  <input
                    type="time"
                    value={appointmentForm.time}
                    onChange={(e) => setAppointmentForm((c) => ({ ...c, time: e.target.value }))}
                    className="form-field"
                  />
                </div>
                <textarea
                  value={appointmentForm.reason}
                  onChange={(e) => setAppointmentForm((c) => ({ ...c, reason: e.target.value }))}
                  className="form-field min-h-20"
                  placeholder="Reason for visit"
                />
                <button type="submit" className="primary-button w-full" disabled={isBooking}>
                  {isBooking ? <Loader2 className="h-4 w-4 animate-spin" /> : <CalendarCheck2 className="h-4 w-4" />}
                  {isBooking ? "Booking..." : "Book Appointment"}
                </button>
              </form>
              {appointments.length > 0 && (
                <div className="mt-4 space-y-2.5">
                  {appointments.slice(0, 4).map((a) => (
                    <div key={a.id} className="p-3 rounded-xl bg-slate-50 border border-slate-100">
                      <p className="text-sm font-bold text-slate-900">{a.doctor_name}</p>
                      <p className="text-xs text-slate-500 mt-0.5">{formatDateTime(a.date)}</p>
                      <span className="text-[11px] font-bold text-slate-400 uppercase tracking-wider">{a.status}</span>
                    </div>
                  ))}
                </div>
              )}
            </DashCard>
          </section>

          <section id="reminders">
            <DashCard>
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-sm font-black text-slate-900">Create Reminder</h2>
                <Bell className="h-5 w-5 text-rose-500" />
              </div>
              <form className="space-y-3" onSubmit={handleCreateReminder}>
                <select
                  value={reminderForm.medicationId}
                  onChange={(e) => setReminderForm((c) => ({ ...c, medicationId: e.target.value }))}
                  className="form-field"
                >
                  <option value="">Select medication</option>
                  {medications.map((m) => (
                    <option key={m.id} value={m.id}>{m.medicine_name}</option>
                  ))}
                </select>
                <div className="grid gap-3 sm:grid-cols-2">
                  <input
                    type="datetime-local"
                    value={reminderForm.reminderTime}
                    onChange={(e) => setReminderForm((c) => ({ ...c, reminderTime: e.target.value }))}
                    className="form-field"
                  />
                  <input
                    value={reminderForm.frequency}
                    onChange={(e) => setReminderForm((c) => ({ ...c, frequency: e.target.value }))}
                    className="form-field"
                    placeholder="Frequency"
                  />
                </div>
                <button type="submit" className="primary-button w-full" disabled={isCreatingReminder}>
                  {isCreatingReminder ? <Loader2 className="h-4 w-4 animate-spin" /> : <Bell className="h-4 w-4" />}
                  {isCreatingReminder ? "Saving..." : "Create Reminder"}
                </button>
              </form>

              {/* Add medication form */}
              <div className="mt-5 pt-5 border-t border-slate-100">
                <h3 className="text-sm font-black text-slate-900 mb-3">Add Medication</h3>
                <form className="space-y-3" onSubmit={handleSaveMedication}>
                  <div className="grid gap-3 sm:grid-cols-2">
                    <input
                      value={medicationForm.medicineName}
                      onChange={(e) => setMedicationForm((c) => ({ ...c, medicineName: e.target.value }))}
                      className="form-field"
                      placeholder="Medicine name"
                    />
                    <input
                      value={medicationForm.dosage}
                      onChange={(e) => setMedicationForm((c) => ({ ...c, dosage: e.target.value }))}
                      className="form-field"
                      placeholder="Dosage"
                    />
                  </div>
                  <input
                    value={medicationForm.instructions}
                    onChange={(e) => setMedicationForm((c) => ({ ...c, instructions: e.target.value }))}
                    className="form-field"
                    placeholder="Instructions (optional)"
                  />
                  <div className="grid gap-3 sm:grid-cols-2">
                    <input
                      type="date"
                      value={medicationForm.startDate}
                      onChange={(e) => setMedicationForm((c) => ({ ...c, startDate: e.target.value }))}
                      className="form-field"
                    />
                    <input
                      type="date"
                      value={medicationForm.endDate}
                      onChange={(e) => setMedicationForm((c) => ({ ...c, endDate: e.target.value }))}
                      className="form-field"
                    />
                  </div>
                  <button type="submit" className="primary-button w-full" disabled={isSavingMedication}>
                    {isSavingMedication ? <Loader2 className="h-4 w-4 animate-spin" /> : <Plus className="h-4 w-4" />}
                    {isSavingMedication ? "Saving..." : "Save Medication"}
                  </button>
                </form>
              </div>
            </DashCard>
          </section>

          {/* ── Privacy Strip ─────────────────────────────────────────────── */}
          <section id="settings">
            <div className="rounded-2xl bg-gradient-to-r from-blue-600 via-indigo-600 to-violet-600 p-5 flex flex-col sm:flex-row items-center justify-between gap-4 shadow-lg shadow-blue-200/50">
              <div className="flex items-center gap-4">
                <div className="h-10 w-10 rounded-xl bg-white/20 flex items-center justify-center flex-shrink-0">
                  <Shield className="h-5 w-5 text-white" />
                </div>
                <div>
                  <p className="text-sm font-black text-white">Your privacy is our priority</p>
                  <p className="text-xs text-blue-100 mt-0.5">
                    All your data is encrypted and secure. We never share your health information.
                  </p>
                </div>
              </div>
              <div className="flex items-center gap-2.5 flex-shrink-0">
                <button
                  type="button"
                  className="px-4 py-2 rounded-xl bg-white text-blue-700 text-sm font-black hover:bg-blue-50 transition shadow-sm"
                >
                  Manage Privacy
                </button>
                <button
                  type="button"
                  onClick={() => { clearSession(); router.push("/login"); }}
                  className="px-4 py-2 rounded-xl bg-white/20 border border-white/30 text-white text-sm font-bold hover:bg-white/30 transition flex items-center gap-2"
                >
                  <LogOut className="h-4 w-4" /> Sign Out
                </button>
              </div>
            </div>
          </section>

        </div>{/* end page body */}
      </div>{/* end main */}

      <ToastBar toast={toast} />
    </div>
  );
}

// ─── Sub-components ───────────────────────────────────────────────────────────

function DashCard({
  children,
  className,
  id,
}: {
  children: ReactNode;
  className?: string;
  id?: string;
}) {
  return (
    <div
      id={id}
      className={cn(
        "rounded-3xl bg-white/80 backdrop-blur-xl border border-blue-100/70 shadow-[0_12px_40px_rgba(30,64,175,0.08)] p-5",
        className,
      )}
    >
      {children}
    </div>
  );
}

function MiniVital({
  icon: Icon,
  label,
  value,
}: {
  icon: LucideIcon;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-center justify-between">
      <div className="flex items-center gap-2">
        <div className="h-6 w-6 rounded-lg bg-blue-50 flex items-center justify-center flex-shrink-0">
          <Icon className="h-3 w-3 text-blue-500" />
        </div>
        <span className="text-xs font-semibold text-slate-500">{label}</span>
      </div>
      <span className="text-xs font-black text-slate-900">{value}</span>
    </div>
  );
}

function StatusBadgeRow({
  label,
  value,
  color,
}: {
  label: string;
  value: string;
  color: "emerald" | "amber" | "rose";
}) {
  const styles = {
    emerald: "bg-emerald-50 text-emerald-700 border-emerald-100",
    amber: "bg-amber-50 text-amber-700 border-amber-100",
    rose: "bg-rose-50 text-rose-700 border-rose-100",
  };
  return (
    <div className="flex items-center justify-between px-3 py-1.5 rounded-xl bg-slate-50 border border-slate-100">
      <span className="text-xs font-semibold text-slate-600">{label}</span>
      <span
        className={cn(
          "text-[11px] font-black px-2 py-0.5 rounded-full border",
          styles[color],
        )}
      >
        {value}
      </span>
    </div>
  );
}

function MedicineRow({
  time,
  name,
  note,
  status,
}: {
  time: string;
  name: string;
  note: string;
  status: string;
}) {
  const badge: Record<string, { label: string; cls: string }> = {
    DUE_NOW: { label: "Due Now", cls: "bg-rose-50 text-rose-700 border-rose-100" },
    UPCOMING_SOON: { label: "Upcoming in 30 min", cls: "bg-amber-50 text-amber-700 border-amber-100" },
    TAKEN: { label: "Taken", cls: "bg-emerald-50 text-emerald-700 border-emerald-100" },
    MISSED: { label: "Missed", cls: "bg-rose-100 text-rose-800 border-rose-200" },
  };
  const b = badge[status] ?? { label: status, cls: "bg-slate-50 text-slate-600 border-slate-100" };

  return (
    <div className="flex items-center gap-4 p-3 rounded-2xl bg-slate-50 border border-slate-100 hover:border-blue-100 hover:bg-blue-50/30 transition">
      <p className="text-[11px] font-black text-slate-500 w-14 flex-shrink-0 text-center leading-tight">
        {time}
      </p>
      <div className="h-7 w-px bg-slate-200 flex-shrink-0" />
      <div className="flex-1 min-w-0">
        <p className="text-sm font-bold text-slate-900 truncate">{name}</p>
        <p className="text-xs text-slate-400">{note}</p>
      </div>
      <span
        className={cn(
          "text-[11px] font-black px-3 py-1 rounded-full border flex-shrink-0",
          b.cls,
        )}
      >
        {b.label}
      </span>
    </div>
  );
}

function RiskRow({
  title,
  reason,
  level,
}: {
  title: string;
  reason: string;
  level: string;
}) {
  const lv = level.toLowerCase();
  const badgeCls =
    lv === "monitor"
      ? "bg-amber-50 text-amber-700 border-amber-100"
      : lv.includes("low")
      ? "bg-orange-50 text-orange-700 border-orange-100"
      : "bg-rose-50 text-rose-700 border-rose-100";

  return (
    <div className="p-3.5 rounded-2xl border border-rose-50 bg-rose-50/40 hover:border-rose-100 transition">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0 flex-1">
          <p className="text-sm font-bold text-slate-900">{title}</p>
          <p className="text-xs text-slate-500 mt-0.5">{reason}</p>
        </div>
        <span
          className={cn(
            "text-[11px] font-black px-2.5 py-1 rounded-full border flex-shrink-0",
            badgeCls,
          )}
        >
          {level}
        </span>
      </div>
    </div>
  );
}

function categoryIcon(category: string) {
  const n = normalizeReportCategory(category);
  if (n === "heart") return <HeartPulse className="h-4 w-4" />;
  if (n === "liver") return <BookOpen className="h-4 w-4" />;
  if (n === "kidney") return <Dumbbell className="h-4 w-4" />;
  if (n === "blood") return <ClipboardList className="h-4 w-4" />;
  if (n === "diabetes") return <Sparkles className="h-4 w-4" />;
  if (n === "ortho") return <Bone className="h-4 w-4" />;
  if (n === "prescriptions") return <Pill className="h-4 w-4" />;
  return <FileText className="h-4 w-4" />;
}

function UploadQueueRow({ item, onRemove }: { item: FileQueueItem; onRemove: () => void }) {
  const STEP_LABELS: Record<UploadStep, string> = {
    idle: "",
    uploading: "Uploading...",
    ocr: "Reading text (OCR)...",
    ai: "AI analysis...",
    saving: "Saving report...",
    done: "Complete",
    error: "Failed",
  };
  const STEP_PROGRESS: Record<UploadStep, string> = {
    idle: "0%", uploading: "25%", ocr: "50%", ai: "75%", saving: "90%", done: "100%", error: "100%",
  };

  const ext = item.file.name.split(".").pop()?.toUpperCase() ?? "FILE";
  const sizeMb = item.file.size / (1024 * 1024);
  const sizeStr = sizeMb < 1 ? `${(item.file.size / 1024).toFixed(0)} KB` : `${sizeMb.toFixed(1)} MB`;
  const isActive = item.step === "uploading" || item.step === "ocr" || item.step === "ai" || item.step === "saving";

  return (
    <div className={cn(
      "flex items-center gap-3 p-3 rounded-2xl border transition",
      item.step === "done" ? "border-emerald-100 bg-emerald-50/40" :
      item.step === "error" ? "border-rose-100 bg-rose-50/40" :
      isActive ? "border-blue-100 bg-blue-50/30" :
      "border-slate-100 bg-white",
    )}>
      {/* File type badge */}
      <div className={cn(
        "h-9 w-9 rounded-xl flex items-center justify-center flex-shrink-0",
        item.step === "done" ? "bg-emerald-100 text-emerald-600" :
        item.step === "error" ? "bg-rose-100 text-rose-600" :
        "bg-blue-100 text-blue-700",
      )}>
        {item.step === "done" ? <CheckCircle2 className="h-4 w-4" /> :
         item.step === "error" ? <AlertCircle className="h-4 w-4" /> :
         <span className="text-[9px] font-black">{ext}</span>}
      </div>

      {/* Info */}
      <div className="flex-1 min-w-0">
        <p className="text-sm font-bold text-slate-900 truncate">{item.file.name}</p>
        <div className="flex items-center gap-2 mt-0.5">
          <span className="text-xs text-slate-400">{sizeStr}</span>
          {isActive && (
            <span className="text-[11px] text-blue-600 font-semibold flex items-center gap-1">
              <Loader2 className="h-3 w-3 animate-spin" />
              {STEP_LABELS[item.step]}
            </span>
          )}
          {item.step === "done" && (
            <span className="text-[11px] text-emerald-600 font-semibold">AI summary ready</span>
          )}
          {item.step === "error" && (
            <span className="text-[11px] text-rose-600 font-semibold truncate max-w-[160px]">{item.error ?? "Upload failed"}</span>
          )}
        </div>
        {/* Progress bar */}
        {isActive && (
          <div className="mt-1.5 h-1 rounded-full bg-blue-100 overflow-hidden">
            <div
              className="h-full rounded-full bg-gradient-to-r from-blue-500 to-violet-500 transition-all duration-700"
              style={{ width: STEP_PROGRESS[item.step] }}
            />
          </div>
        )}
        {item.step === "done" && (
          <div className="mt-1.5 h-1 rounded-full bg-emerald-200 overflow-hidden">
            <div className="h-full w-full rounded-full bg-emerald-500" />
          </div>
        )}
        {item.step === "done" && item.report?.patient_summary && (
          <div className="mt-3 p-3 rounded-xl bg-white border border-emerald-100 shadow-sm relative">
            <div className="flex items-center gap-1.5 mb-1.5">
              <Sparkles className="h-3.5 w-3.5 text-emerald-500" />
              <p className="text-xs font-bold text-slate-800">AI Summary Generated</p>
            </div>
            <p className="text-xs text-slate-600 leading-relaxed">
              {item.report.patient_summary}
            </p>
          </div>
        )}
      </div>

      {/* Remove button — only when idle */}
      {item.step === "idle" && (
        <button
          type="button"
          onClick={onRemove}
          className="h-7 w-7 rounded-lg border border-slate-200 flex items-center justify-center text-slate-400 hover:text-rose-500 hover:border-rose-200 transition flex-shrink-0"
        >
          <X className="h-3.5 w-3.5" />
        </button>
      )}
    </div>
  );
}

function ToastBar({ toast }: { toast: ToastState }) {
  return (
    <AnimatePresence>
      {toast && (
        <motion.div
          initial={{ opacity: 0, y: 16 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 16 }}
          className="fixed bottom-5 left-1/2 -translate-x-1/2 z-50"
        >
          <div
            className={cn(
              "rounded-full px-5 py-3 text-sm font-semibold shadow-xl backdrop-blur-xl border",
              toast.type === "success"
                ? "bg-emerald-50 text-emerald-800 border-emerald-100"
                : toast.type === "error"
                ? "bg-rose-50 text-rose-800 border-rose-100"
                : "bg-blue-50 text-blue-800 border-blue-100",
            )}
          >
            {toast.message}
          </div>
        </motion.div>
      )}
    </AnimatePresence>
  );
}

declare global {
  interface Window {
    webkit?: unknown;
  }
}
