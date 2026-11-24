"use client";

import Link from "next/link";
import { PhoneCall, Send } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { Alert } from "@/components/ui/alert";
import { EmptyState } from "@/components/ui/empty-state";
import { ErrorState } from "@/components/ui/spinner";
import { SkeletonCard } from "@/components/ui/skeleton";
import { useMyHomeVisits } from "@/hooks/home-visits/use-my-home-visits";
import { useStoredSession } from "@/hooks/use-stored-session";
import { RequestFlow } from "./RequestFlow";
import { VisitHistory } from "./VisitHistory";
import { VisitTracker } from "./VisitTracker";

/** The home-visit page (/emergency): the 1122 notice first, then the live visit or the request form. */
export function HomeVisitView() {
  const { ready, session } = useStoredSession();
  const isPatient = session?.user.role === "patient";

  return (
    <PageContainer>
      <PageHeader
        eyebrow="Home visit"
        title="Ask for a doctor at home"
        description="For problems that are not an emergency and do not need a hospital. The best-matched nearby doctor is asked first."
      />

      <div className="mb-6 flex flex-col gap-3 rounded-card border border-rose-200 bg-rose-50 p-5 sm:flex-row sm:items-center" role="alert">
        <PhoneCall className="h-6 w-6 flex-shrink-0 text-rose-600" aria-hidden />
        <p className="text-sm font-semibold leading-6 text-rose-900">
          If this is an emergency, call 1122 or go to the nearest emergency department now. This is not an ambulance or
          emergency service. Do not wait for a reply here.
        </p>
      </div>

      {!ready ? (
        <SkeletonCard lines={5} />
      ) : !session ? (
        <EmptyState
          icon={Send}
          title="Sign in to ask for a home visit"
          description="Home-visit requests are linked to your patient account."
          action={
            <Link href="/login?next=/emergency" className="secondary-button min-h-[36px] px-3 text-xs">
              Sign in
            </Link>
          }
        />
      ) : !isPatient ? (
        <Alert tone="warning">Only patient accounts can ask for a home visit. Doctors manage home visits from their dashboard.</Alert>
      ) : (
        <PatientHomeVisits />
      )}
    </PageContainer>
  );
}

function PatientHomeVisits() {
  const visits = useMyHomeVisits();

  if (visits.status === "loading") return <SkeletonCard lines={6} />;
  if (visits.status === "error") return <ErrorState message={visits.error} onRetry={visits.retry} />;

  const past = visits.items.filter((visit) => visit.id !== visits.active?.id);
  return (
    <>
      {visits.active ? (
        <VisitTracker visit={visits.active} onCancel={() => void visits.cancel(visits.active!.id)} busy={visits.busy} error={visits.actionError} />
      ) : (
        <RequestFlow onCreated={() => void visits.refresh()} />
      )}
      <VisitHistory visits={past} legacy={visits.legacy} />
      <p className="mt-6 text-xs leading-5 text-ink-muted">
        Location comes from your browser only and is used to find doctors near you. Doctors see a rounded straight-line
        distance until they accept. The knowledge used for matching is a demo, not clinically reviewed.
      </p>
    </>
  );
}
