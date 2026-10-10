"use client";

import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";
import { HeartPulse } from "lucide-react";

import { api } from "@/lib/api";
import { clearSession } from "@/lib/auth";
import { normalizeReportCategory, type ReportCategoryId } from "@/lib/patient-dashboard";
import type { MedicalDocument } from "@/lib/types";
import { useAuthGuard } from "@/hooks/use-auth-guard";
import { useNotificationPermission, useScheduledNotifications } from "@/hooks/use-browser-notifications";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { useToast } from "@/hooks/use-toast";
import { usePatientWorkspaceData } from "@/hooks/patient/use-patient-workspace-data";
import { useUploadQueue } from "@/hooks/patient/use-upload-queue";
import { AiSummaryCard } from "./workspace/AiSummaryCard";
import { AppointmentsSection } from "./workspace/AppointmentsSection";
import { DoctorAccessCard } from "./workspace/DoctorAccessCard";
import {
  formatVitalCardValue,
  getUpcomingAppointment,
  isReminderPending,
  isToday,
  scrollToSection,
} from "./workspace/helpers";
import { KpiRow } from "./workspace/KpiRow";
import { QuickLinks, SettingsStrip, WorkspaceHeader, WorkspaceSidebar } from "./workspace/layout";
import { MedicineScheduleCard } from "./workspace/MedicineScheduleCard";
import { RemindersSection } from "./workspace/RemindersSection";
import { HealthCategoriesCard, RecentReportsCard, RiskFlagsCard } from "./workspace/ReportsSection";
import { ToastBar } from "./workspace/ui";
import { UploadCard } from "./workspace/UploadCard";
import { VitalsSection } from "./workspace/VitalsSection";

type PatientView = "dashboard" | "upload" | "records" | "ocr" | "summary" | "profile";

const SEARCH_DEBOUNCE_MS = 200;
const CRITICAL_FLAGS_SHOWN = 5;

export function PatientWorkspace({
  initialDepartment,
}: {
  /** Accepted for the /dashboard/patient/* routes; every route currently shows the full workspace. */
  initialView: PatientView;
  initialDepartment?: string;
}) {
  const router = useRouter();
  const auth = useAuthGuard("patient");
  const token = auth.status === "ready" ? auth.token : null;
  const user = auth.status === "ready" ? auth.user : null;

  const { toast, notify } = useToast();
  const { data, isLoading, refresh, addReport } = usePatientWorkspaceData(token);
  const upload = useUploadQueue({ token, notify, onUploaded: addReport });
  const notifications = useNotificationPermission();

  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearch = useDebouncedValue(searchQuery, SEARCH_DEBOUNCE_MS);
  const [activeCategory, setActiveCategory] = useState<ReportCategoryId | "all">(
    initialDepartment ? normalizeReportCategory(initialDepartment) : "all",
  );
  const [activeNav, setActiveNav] = useState("dashboard");

  const { reports, reminders, riskPredictions, appointments, basicVitals, vitalsToday } = data;

  // Pop-ups for today's reminders that are not taken or skipped, while the page is open.
  const popups = useMemo(
    () =>
      reminders
        .filter((r) => !r.taken_at && !r.skipped_at)
        .map((r) => {
          const name = r.medication?.medicine_name ?? "your medicine";
          const dosage = r.medication?.dosage ? ` (${r.medication.dosage})` : "";
          return { id: `reminder-${r.id}`, at: r.reminder_time, title: "Medicine reminder", body: `Time to take ${name}${dosage}.` };
        }),
    [reminders],
  );
  useScheduledNotifications(popups, notifications.permission === "granted");

  const filteredReports = useMemo(() => {
    const query = debouncedSearch.trim().toLowerCase();
    return reports.filter((r) => {
      const matchesCategory = activeCategory === "all" || normalizeReportCategory(r.category) === activeCategory;
      if (!matchesCategory) return false;
      if (!query) return true;
      const haystack = [r.title, r.original_filename, r.category, r.summary ?? "", r.ai_summary ?? "", r.detected_keywords.join(" ")]
        .join(" ")
        .toLowerCase();
      return haystack.includes(query);
    });
  }, [activeCategory, debouncedSearch, reports]);

  const upcomingAppointment = useMemo(() => getUpcomingAppointment(appointments), [appointments]);
  const criticalFlags = useMemo(() => {
    const fromReports = reports.filter((r) => r.validation_status === "HIGH_RISK").map((r) => `Possible report risk: ${r.title}`);
    const fromRisks = riskPredictions.filter((r) => r.risk_level === "High").map((r) => r.risk_title);
    return [...fromReports, ...fromRisks].slice(0, CRITICAL_FLAGS_SHOWN);
  }, [reports, riskPredictions]);
  const pendingReminderCount = reminders.filter(isReminderPending).length;

  // A detailed reading wins; otherwise show a BP entered today through the simple log.
  const basicToday = !vitalsToday && basicVitals[0] && isToday(basicVitals[0].created_at) ? basicVitals[0] : null;
  const todayVitals = basicToday
    ? { ...formatVitalCardValue(null), bloodPressure: basicToday.blood_pressure }
    : formatVitalCardValue(vitalsToday);
  const todayVitalsRecordedAt = vitalsToday?.recorded_at ?? basicToday?.created_at ?? null;

  const navigate = useCallback((section: string) => {
    setActiveNav(section);
    scrollToSection(section);
  }, []);

  const markReminder = useCallback(
    async (reminderId: number, action: "taken" | "skip") => {
      if (!token) return;
      try {
        if (action === "taken") {
          await api.markReminderTaken(token, reminderId);
          notify("success", "Marked as taken.");
        } else {
          await api.skipReminder(token, reminderId);
          notify("info", "Reminder skipped.");
        }
        await refresh();
      } catch (err) {
        notify("error", err instanceof Error ? err.message : "Unable to update reminder.");
      }
    },
    [notify, refresh, token],
  );

  function downloadReport(report: MedicalDocument) {
    if (!report.file_access_url) return;
    const link = document.createElement("a");
    link.href = api.uploadUrl(report.file_access_url);
    link.download = report.original_filename;
    link.click();
  }

  function signOut() {
    clearSession();
    router.push("/login");
  }

  if (auth.status === "error") {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-violet-50 flex items-center justify-center px-4">
        <p role="alert" className="max-w-md text-center text-sm font-semibold text-rose-700">
          {auth.message}
        </p>
      </div>
    );
  }

  if (!token || isLoading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-blue-50 via-white to-violet-50 flex items-center justify-center">
        <div className="flex flex-col items-center gap-4" role="status">
          <div className="h-16 w-16 rounded-2xl bg-gradient-to-br from-blue-500 to-violet-600 flex items-center justify-center shadow-lg shadow-blue-200">
            <HeartPulse className="h-8 w-8 text-white animate-pulse" />
          </div>
          <p className="text-sm font-semibold text-slate-600">Loading your health dashboard...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex min-h-screen bg-gradient-to-br from-blue-50 via-white to-violet-50">
      <WorkspaceSidebar activeNav={activeNav} onNavigate={navigate} userName={user?.full_name ?? null} />

      <div className="flex-1 xl:ml-[280px] min-h-screen flex flex-col">
        <WorkspaceHeader
          firstName={user?.full_name?.split(" ")[0] ?? ""}
          searchQuery={searchQuery}
          onSearchChange={setSearchQuery}
          unreadCount={pendingReminderCount + criticalFlags.length}
          onNavigate={navigate}
        />

        <main className="flex-1 p-4 xl:p-6 space-y-5">
          <QuickLinks />

          <KpiRow
            vitals={todayVitals}
            vitalsRecordedAt={todayVitalsRecordedAt}
            reminderCount={reminders.length}
            upcomingAppointment={upcomingAppointment}
            criticalFlagCount={criticalFlags.length}
            onNavigate={navigate}
          />

          <DoctorAccessCard token={token} notify={notify} />

          <VitalsSection token={token} history={basicVitals} notify={notify} onSaved={refresh} />

          <section className="grid gap-5 xl:grid-cols-2">
            <UploadCard upload={upload} onAllUploaded={() => void refresh()} />
            <AiSummaryCard summary={data.doctorSummaries[0]} />
          </section>

          <MedicineScheduleCard
            reminders={reminders}
            permission={notifications.permission}
            onEnablePopups={() => void notifications.request()}
            onMark={(id, action) => void markReminder(id, action)}
            onSeeAll={() => navigate("reminders")}
          />

          <HealthCategoriesCard reports={reports} onSelect={setActiveCategory} />

          <section className="grid gap-5 xl:grid-cols-[1.1fr_0.9fr]">
            <RecentReportsCard
              totalReports={reports.length}
              filteredReports={filteredReports}
              activeCategory={activeCategory}
              onShowAll={() => setActiveCategory("all")}
              onOpen={(report) => router.push(`/dashboard/patient/reports/${report.id}`)}
              onDownload={downloadReport}
            />
            <RiskFlagsCard risks={riskPredictions} />
          </section>

          <AppointmentsSection token={token} doctors={data.doctors} appointments={appointments} notify={notify} onSaved={refresh} />

          <RemindersSection
            token={token}
            medications={data.medications}
            notify={notify}
            onSaved={refresh}
            beforeCreateReminder={notifications.request}
          />

          <SettingsStrip onSignOut={signOut} />
        </main>
      </div>

      <ToastBar toast={toast} />
    </div>
  );
}
