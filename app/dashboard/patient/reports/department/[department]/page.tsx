import { PatientWorkspace } from "@/components/patient/PatientWorkspace";

type DepartmentPageProps = {
  params: Promise<{
    department: string;
  }>;
};

export default async function PatientDepartmentReportsPage({ params }: DepartmentPageProps) {
  const { department } = await params;
  return <PatientWorkspace initialView="records" initialDepartment={decodeURIComponent(department)} />;
}
