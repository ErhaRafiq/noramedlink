import { PatientReportDetail } from "@/components/patient/PatientReportDetail";

type ReportPageProps = {
  params: Promise<{
    id: string;
  }>;
};

export default async function PatientReportDetailPage({ params }: ReportPageProps) {
  const { id } = await params;
  return <PatientReportDetail reportId={Number(id)} />;
}
