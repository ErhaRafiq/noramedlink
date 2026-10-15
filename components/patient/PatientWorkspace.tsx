"use client";

import { useRouter } from "next/navigation";
import { useCallback, useMemo, useState } from "react";

import { ErrorState, PageLoader } from "@/components/ui/spinner";
import { api } from "@/lib/api";
import { signOut as endSession } from "@/lib/auth";
import { isDepartmentSlug, type DepartmentSlug } from "@/lib/departments";
import type { MedicalDocument } from "@/lib/types";
import { useAuthGuard } from "@/hooks/use-auth-guard";
import { useNotificationPermission, useScheduledNotifications } from "@/hooks/use-browser-notifications";
import { useDebouncedValue } from "@/hooks/use-debounced-value";
import { useScrollSpy } from "@/hooks/use-scroll-spy";
import { useToast } from "@/hooks/use-toast";
import { usePatientWorkspaceData } from "@/hooks/patient/use-patient-workspace-data";
import { useReportList } from "@/hooks/patient/use-report-list";
import { useUploadQueue } from "@/hooks/patient/use-upload-queue";
import { AppointmentsSection } from "./workspace/AppointmentsSection";
import { DoctorAccessCard } from "./workspace/DoctorAccessCard";
import { formatVitalCardValue, getUpcomingAppointment, isReminderPending, isToday, scrollToSection } from "./workspace/helpers";
import { KpiRow } from "./workspace/KpiRow";
import { NAV_ITEMS, QuickLinks, SettingsStrip, WorkspaceHeader, WorkspaceSidebar } from "./workspace/layout";
import { MedicineScheduleCard } from "./workspace/MedicineScheduleCard";
import { RemindersSection } from "./workspace/RemindersSection";
import { HealthFlagsCard } from "./workspace/HealthFlagsCard";
import { PrescriptionsCard } from "./workspace/PrescriptionsCard";
import { HealthCategoriesCard, RecentReportsCard } from "./workspace/ReportsSection";
import { ToastBar } from "./workspace/ui";
import { UploadCard } from "./workspace/UploadCard";
import { VitalsSection } from "./workspace/VitalsSection";
import { WorkspaceSkeleton } from "./workspace/WorkspaceSkeleton";

type PatientView = "dashboard" | "upload" | "records" | "ocr" | "summary" | "profile";

const SEARCH_DEBOUNCE_MS = 300;
// Sections the sidebar highlights while scrolling ("dashboard" is the header, the fallback).
const SPY_SECTIONS = NAV_ITEMS.map((item) => item.id).filter((id) => id !== "dashboard");

export function PatientWorkspace({
  initialDepartment,
}: {
  /** Accepted for the /dashboard/patient/* routes; every route currently shows the full workspace. */
  initialView: PatientView;
  initialDepartment?: string;
}) {
  const router = useRouter();
  const auth = useAuthGuard("patient");
  const signedIn = auth.status === "ready";
  const user = auth.status === "ready" ? auth.user : null;

  const { toast, notify } = useToast();
  const { data, isLoading, refresh } = usePatientWorkspaceData(signedIn);
  const notifications = useNotificationPermission();

  const [searchQuery, setSearchQuery] = useState("");
  const debouncedSearch = useDebouncedValue(searchQuery, SEARCH_DEBOUNCE_MS);
  const [department, setDepartment] = useState<DepartmentSlug | null>(
    isDepartmentSlug(initialDepartment) ? (initialDepartment.toLowerCase() as DepartmentSlug) : null,
  );
  const reportList = useReportList({ signedIn, search: debouncedSearch, department });
  const upload = useUploadQueue({ signedIn, notify, onUploaded: reportList.refresh });
  const [activeNav, setActiveNav] = useScrollSpy(SPY_SECTIONS, { fallback: "dashboard" });

  const { reminders, appointments, basicVitals, vitalsToday } = data;

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

  const upcomingAppointment = useMemo(() => getUpcomingAppointment(appointments), [appointments]);
  // Reports whose fixed-rule checks need prompt attention (an AI never sets this count).
  const criticalFlagCount = data.healthFlags?.high_risk_reports ?? data.highRiskTotal;
  const pendingReminderCount = reminders.filter(isReminderPending).length;

  // A detailed reading wins; otherwise show a BP entered today through the simple log.
  const basicToday = !vitalsToday && basicVitals[0] && isToday(basicVitals[0].created_at) ? basicVitals[0] : null;
  const todayVitals = basicToday
    ? { ...formatVitalCardValue(null), bloodPressure: basicToday.blood_pressure }
    : formatVitalCardValue(vitalsToday);
  const todayVitalsRecordedAt = vitalsToday?.recorded_at ?? basicToday?.created_at ?? null;

  const navigate = useCallback(
    (section: string) => {
      setActiveNav(section);
      scrollToSection(section);
    },
    [setActiveNav],
  );

  const refreshAll = useCallback(async () => {
    reportList.refresh();
    await refresh();
  }, [refresh, reportList]);

  const markReminder = useCallback(
    async (reminderId: number, action: "taken" | "skip") => {
      if (!signedIn) return;
      try {
        if (action === "taken") {
          await api.markReminderTaken(reminderId);
          notify("success", "Marked as taken.");
        } else {
          await api.skipReminder(reminderId);
          notify("info", "Reminder skipped.");
        }
        await refresh();
      } catch (err) {
        notify("error", err instanceof Error ? err.message : "Unable to update reminder.");
      }
    },
    [notify, refresh, signedIn],
  );

  function selectDepartment(slug: DepartmentSlug) {
    setDepartment((current) => (current === slug ? null : slug));
    scrollToSection("recent-reports");
  }

  function downloadReport(report: MedicalDocument) {
    if (!report.file_access_url) return;
    const link = document.createElement("a");
    link.href = api.uploadUrl(report.file_access_url);
    link.download = report.original_filename;
    link.click();
  }

  function signOut() {
    void endSession();
    router.push("/login");
  }

  if (auth.status === "error") return <ErrorState message={auth.message} onRetry={() => window.location.reload()} />;
  if (!signedIn) return <PageLoader message="Checking your session..." />;
  if (isLoading) return <WorkspaceSkeleton />;

  return (
    <div className="flex min-h-screen bg-surface-page">
      <WorkspaceSidebar activeNav={activeNav} onNavigate={navigate} userName={user?.full_name ?? null} />

      {/* min-w-0: lets the column shrink to the screen instead of growing to fit the scrolling section pills. */}
      <div className="flex min-h-screen min-w-0 flex-1 flex-col xl:ml-[264px]">
        <WorkspaceHeader
          firstName={user?.full_name?.split(" ")[0] ?? ""}
          searchQuery={searchQuery}
          onSearchChange={(value) => {
            setSearchQuery(value);
            if (value.trim()) scrollToSection("recent-reports");
          }}
          attentionCount={pendingReminderCount + criticalFlagCount}
          onNavigate={navigate}
        />

        <main className="mx-auto w-full max-w-6xl flex-1 space-y-6 p-4 sm:p-6 xl:p-8">
          <QuickLinks />

          <KpiRow
            vitals={todayVitals}
            vitalsRecordedAt={todayVitalsRecordedAt}
            reminderCount={reminders.length}
            upcomingAppointment={upcomingAppointment}
            criticalFlagCount={criticalFlagCount}
            onNavigate={navigate}
          />

          <DoctorAccessCard notify={notify} />

          <VitalsSection history={basicVitals} notify={notify} onSaved={refresh} />

          <section className="grid gap-5 xl:grid-cols-2">
            <UploadCard upload={upload} onAllUploaded={() => void refreshAll()} />
            <HealthFlagsCard flags={data.healthFlags} onRetry={() => void refresh()} />
          </section>

          <MedicineScheduleCard
            reminders={reminders}
            permission={notifications.permission}
            onEnablePopups={() => void notifications.request()}
            onMark={(id, action) => void markReminder(id, action)}
            onSeeAll={() => navigate("reminders")}
          />

          <PrescriptionsCard prescriptions={data.prescriptions} onRetry={() => void refresh()} />

          <HealthCategoriesCard tiles={data.departmentTiles} activeDepartment={department} onSelect={selectDepartment} />

          <section>
            <RecentReportsCard
              list={reportList}
              activeDepartment={department}
              search={debouncedSearch}
              onClearFilters={() => {
                setDepartment(null);
                setSearchQuery("");
              }}
              onOpen={(report) => router.push(`/dashboard/patient/reports/${report.id}`)}
              onDownload={downloadReport}
            />
          </section>

          <AppointmentsSection doctors={data.doctors} appointments={appointments} notify={notify} onSaved={refresh} />

          <RemindersSection
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
