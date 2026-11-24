"use client";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { SkeletonCard } from "@/components/ui/skeleton";
import { useChecklist, useHomeVisitRequest } from "@/hooks/home-visits/use-home-visit-request";
import type { PatientHomeVisit } from "@/lib/types";
import { RequestForm } from "./RequestForm";
import { StopNotice } from "./StopNotice";

/** The request form with its safety questions, or the answer that replaces it when the request is stopped. */
export function RequestFlow({ onCreated }: { onCreated: (visit: PatientHomeVisit) => void }) {
  const { checklist, error, retry } = useChecklist();
  const request = useHomeVisitRequest(onCreated);

  return (
    <section aria-labelledby="request-title" className="rounded-card border border-line bg-white p-5 shadow-card sm:p-6">
      <h2 id="request-title" className="mb-4 text-base font-semibold text-ink">
        Ask for a home visit
      </h2>
      {request.stop ? (
        <StopNotice stop={request.stop} onStartOver={request.startOver} />
      ) : error ? (
        <Alert tone="error">
          <p>{error}</p>
          <Button variant="secondary" size="sm" className="mt-2" onClick={retry}>
            Try again
          </Button>
        </Alert>
      ) : !checklist ? (
        <SkeletonCard lines={6} className="border-0 p-0 shadow-none" />
      ) : (
        <RequestForm questions={checklist.questions} notice={checklist.notice} request={request} />
      )}
    </section>
  );
}
