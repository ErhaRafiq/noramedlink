"use client";

import { useState } from "react";
import { Home } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/empty-state";
import { SkeletonCard } from "@/components/ui/skeleton";
import { ErrorState } from "@/components/ui/spinner";
import { useDoctorHomeVisits } from "@/hooks/home-visits/use-doctor-home-visits";
import { OfferItem } from "./OfferItem";
import { VisitItem } from "./VisitItem";

/**
 * Home visits on the doctor dashboard: requests waiting for an answer, the visits in progress, and past visits.
 * The list refreshes every few seconds while the page is open.
 */
export function HomeVisitsCard() {
  const visits = useDoctorHomeVisits(true);
  const [notice, setNotice] = useState("");

  async function answer(action: Promise<string | null>) {
    setNotice((await action) ?? "");
  }

  return (
    <Card id="home-visits" aria-labelledby="home-visits-title">
      <p className="section-eyebrow">On demand</p>
      <h2 id="home-visits-title" className="mb-4 mt-1.5 text-lg font-semibold text-ink">
        Home visits
      </h2>
      {visits.status === "loading" ? (
        <SkeletonCard lines={3} className="border-0 p-0 shadow-none" />
      ) : visits.status === "error" ? (
        <ErrorState message={visits.error} onRetry={visits.retry} />
      ) : (
        <div className="space-y-4">
          {notice ? <Alert tone="warning">{notice}</Alert> : null}
          {visits.offers.map((offer) => (
            <OfferItem
              key={offer.id}
              offer={offer}
              busy={visits.busyId === offer.id}
              onAccept={() => void answer(visits.accept(offer.id))}
              onDecline={() => void answer(visits.decline(offer.id))}
              onRefer={() => void answer(visits.escalate(offer.id))}
            />
          ))}
          {visits.live.map((visit) => (
            <VisitItem
              key={visit.id}
              visit={visit}
              actions={{
                busy: visits.busyId === visit.id,
                enRoute: (eta) => visits.enRoute(visit.id, eta),
                arrived: () => visits.arrived(visit.id),
                complete: () => visits.complete(visit.id),
                close: (summary) => visits.close(visit.id, summary),
                cancel: () => visits.cancel(visit.id),
                escalate: () => visits.escalate(visit.id),
              }}
            />
          ))}
          {visits.offers.length === 0 && visits.live.length === 0 ? (
            <EmptyState
              icon={Home}
              title="No home visit requests right now"
              description="Requests from patients near your base location appear here when you take home visits. Switch them on, and set your base location and radius, in your profile."
              action={
                <ButtonLink href="/profile#home-visits" variant="secondary" size="sm">
                  Home-visit settings
                </ButtonLink>
              }
            />
          ) : null}
          {visits.past.length > 0 ? (
            <section aria-label="Past home visits">
              <h3 className="mb-2 text-sm font-semibold text-ink">Past home visits</h3>
              <div className="space-y-3">
                {visits.past.map((visit) => (
                  <VisitItem
                    key={visit.id}
                    visit={visit}
                    actions={{
                      busy: false,
                      enRoute: async () => null,
                      arrived: async () => null,
                      complete: async () => null,
                      close: async () => null,
                      cancel: async () => null,
                      escalate: async () => null,
                    }}
                  />
                ))}
              </div>
            </section>
          ) : null}
        </div>
      )}
    </Card>
  );
}
