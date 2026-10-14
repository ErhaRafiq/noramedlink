"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useState } from "react";
import { ArrowLeft, FileQuestion } from "lucide-react";

import { PageContainer } from "@/components/layout/PageHeader";
import { Alert } from "@/components/ui/alert";
import { ConfirmDialog } from "@/components/ui/confirm-dialog";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState, PageLoader } from "@/components/ui/spinner";
import { api } from "@/lib/api";
import { departmentLabel } from "@/lib/departments";
import { formatDateTime } from "@/lib/datetime";
import { useAuthGuard } from "@/hooks/use-auth-guard";
import { useReportDetail, type ActionResult } from "@/hooks/patient/use-report-detail";
import { ReportEditor } from "./report/ReportEditor";
import { ReportAttention } from "./report/ReportAttention";
import { ReportDetailSkeleton, ReportExtraction, ReportFilePreview, ReportStats, ReportSummary } from "./report/ReportSections";

const BACK_HREF = "/dashboard/patient#recent-reports";

function BackLink() {
  return (
    <Link href={BACK_HREF} className="inline-flex items-center gap-1.5 text-sm font-medium text-brand-blue hover:underline">
      <ArrowLeft className="h-4 w-4" aria-hidden />
      Back to my reports
    </Link>
  );
}

export function PatientReportDetail({ reportId }: { reportId: number }) {
  const router = useRouter();
  const auth = useAuthGuard("patient");
  const detail = useReportDetail(auth.status === "ready" ? auth.token : null, reportId);
  const [notice, setNotice] = useState<ActionResult | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);

  async function run(action: () => Promise<ActionResult>) {
    setNotice(null);
    setNotice(await action());
  }

  async function deleteReport() {
    const result = await detail.remove();
    if (result.ok) {
      router.replace(BACK_HREF);
      return;
    }
    setConfirmDelete(false);
    setNotice(result);
  }

  if (auth.status === "error") return <ErrorState message={auth.message} onRetry={() => window.location.reload()} />;
  if (auth.status !== "ready") return <PageLoader message="Checking your session..." />;

  const { report } = detail;

  return (
    <PageContainer>
      <BackLink />
      <div className="mt-5">
        {detail.status === "loading" ? (
          <ReportDetailSkeleton />
        ) : detail.status === "not-found" ? (
          <EmptyState icon={FileQuestion} title="Report not found" description="It may have been deleted, or it belongs to another account." />
        ) : detail.status === "error" || !report ? (
          <Alert tone="error" title="This report could not be loaded">
            {detail.error}
          </Alert>
        ) : (
          <>
            <header className="mb-6">
              <p className="section-eyebrow">{departmentLabel(report.department_slug ?? report.category)}</p>
              <h1 className="mt-2 break-words text-3xl font-semibold tracking-tight text-ink">{report.title}</h1>
              <p className="mt-1 text-sm text-ink-muted">Uploaded {formatDateTime(report.upload_date)}</p>
            </header>
            <ReportStats report={report} />
            <ReportAttention report={report} />
            {notice ? (
              <Alert tone={notice.ok ? "success" : "error"} className="mt-6">
                {notice.message}
              </Alert>
            ) : null}
            <div className="mt-6 grid gap-6 xl:grid-cols-2">
              <div className="space-y-6">
                <ReportSummary report={report} />
                <ReportEditor
                  detail={detail}
                  onSave={() => void run(detail.save)}
                  onRegenerate={() => void run(detail.regenerate)}
                  onDelete={() => setConfirmDelete(true)}
                />
              </div>
              <div className="space-y-6">
                <ReportFilePreview report={report} fileUrl={report.file_access_url ? api.uploadUrl(report.file_access_url) : ""} />
                <ReportExtraction report={report} />
              </div>
            </div>
            <ConfirmDialog
              open={confirmDelete}
              title="Delete this report?"
              description={
                <>
                  <strong className="font-semibold text-ink">{report.title}</strong> and its file will be removed permanently. Doctors
                  will no longer see it. This cannot be undone.
                </>
              }
              confirmLabel="Delete report"
              pendingLabel="Deleting..."
              pending={detail.pending === "delete"}
              onConfirm={() => void deleteReport()}
              onCancel={() => setConfirmDelete(false)}
            />
          </>
        )}
      </div>
    </PageContainer>
  );
}
