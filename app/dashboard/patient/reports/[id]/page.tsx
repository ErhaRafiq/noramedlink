import type { Metadata } from "next";
import { notFound } from "next/navigation";

import { SitePage } from "@/components/layout/SitePage";
import { PatientReportDetail } from "@/components/patient/PatientReportDetail";

export const metadata: Metadata = {
  title: "Report",
};

type ReportPageProps = {
  params: Promise<{
    id: string;
  }>;
};

export default async function PatientReportDetailPage({ params }: ReportPageProps) {
  const { id } = await params;
  const reportId = Number(id);
  if (!Number.isInteger(reportId) || reportId <= 0) notFound();
  return (
    <SitePage>
      <PatientReportDetail reportId={reportId} />
    </SitePage>
  );
}
