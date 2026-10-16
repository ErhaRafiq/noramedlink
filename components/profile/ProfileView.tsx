"use client";

import { ArrowLeft } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { ButtonLink } from "@/components/ui/button";
import { SkeletonCard } from "@/components/ui/skeleton";
import { ErrorState, PageLoader } from "@/components/ui/spinner";
import { useAuthGuard } from "@/hooks/use-auth-guard";
import { useProfile } from "@/hooks/profile/use-profile";
import { dashboardPathForRole } from "@/lib/auth";
import { AccountForm } from "./AccountForm";
import { Activity } from "./Activity";
import { AvailabilityEditor } from "./AvailabilityEditor";
import { DoctorForm } from "./DoctorForm";
import { PatientForm } from "./PatientForm";

/** "My profile" for every role: the account, plus the patient or doctor part. */
export function ProfileView() {
  const auth = useAuthGuard("any");
  if (auth.status === "error") return <ErrorState message={auth.message} onRetry={() => window.location.reload()} />;
  if (auth.status !== "ready") return <PageLoader message="Checking your session..." />;
  return <ProfileContent role={auth.user.role} />;
}

function ProfileContent({ role }: { role: "patient" | "doctor" | "admin" }) {
  const { profile, error, saving, retry, saveAccount, savePatient, saveDoctor } = useProfile();
  return (
    <PageContainer narrow>
      <PageHeader
        eyebrow="Account"
        title="My profile"
        description="Keep your details up to date. Only you can change them."
        actions={
          <ButtonLink href={dashboardPathForRole(role)} variant="secondary" size="sm" icon={<ArrowLeft className="h-4 w-4" />}>
            Back to dashboard
          </ButtonLink>
        }
      />
      {error ? (
        <ErrorState message={error} onRetry={retry} />
      ) : !profile ? (
        <div role="status" aria-label="Loading your profile" className="space-y-6">
          <SkeletonCard lines={4} />
          <SkeletonCard lines={6} />
        </div>
      ) : (
        <div className="space-y-6">
          <Activity profile={profile} />
          <AccountForm key={`a-${profile.account.full_name}-${profile.account.phone}`} account={profile.account} saving={saving === "account"} onSave={saveAccount} />
          {profile.patient ? <PatientForm patient={profile.patient} saving={saving === "patient"} onSave={savePatient} /> : null}
          {profile.doctor ? <DoctorForm doctor={profile.doctor} saving={saving === "doctor"} onSave={saveDoctor} /> : null}
          {profile.doctor ? <AvailabilityEditor /> : null}
        </div>
      )}
    </PageContainer>
  );
}
