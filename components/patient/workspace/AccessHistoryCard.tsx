"use client";

import { Eye } from "lucide-react";

import { Alert } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { useAccessHistory } from "@/hooks/records/use-access-history";
import { formatDateTime } from "@/lib/datetime";
import { DashCard } from "./ui";

/** Who else has viewed or changed this patient's record, from the audit log. */
export function AccessHistoryCard() {
  const history = useAccessHistory();
  return (
    <DashCard id="access-history">
      <div className="mb-4 flex items-center gap-3">
        <span className="grid h-9 w-9 place-items-center rounded-control bg-violet-50 text-violet-700">
          <Eye className="h-4 w-4" aria-hidden />
        </span>
        <div>
          <h2 className="text-base font-semibold text-ink">Who has seen my record</h2>
          <p className="text-xs text-ink-muted">Doctors and administrators who opened or changed it</p>
        </div>
      </div>

      {history.status === "loading" ? (
        <div role="status" aria-label="Loading the access history" className="space-y-2">
          <Skeleton className="h-12 w-full" />
          <Skeleton className="h-12 w-full" />
        </div>
      ) : history.status === "error" ? (
        <Alert tone="error" title="The access history could not be loaded">
          {history.error}{" "}
          <button type="button" onClick={history.retry} className="font-semibold underline">
            Try again
          </button>
        </Alert>
      ) : history.items.length === 0 ? (
        <p className="rounded-control border border-line bg-surface-soft p-3 text-sm text-ink-muted">
          No doctor or administrator has opened or changed your record yet.
        </p>
      ) : (
        <>
          <ul className="divide-y divide-line">
            {history.items.map((row) => (
              <li key={row.id} className="min-w-0 py-3 first:pt-0 last:pb-0">
                <p className="break-words text-sm text-ink">
                  <span className="font-semibold">{row.actor_name ?? "A user whose account was removed"}</span>{" "}
                  <span className="text-ink-muted">({row.actor_role})</span> {row.action_label}
                  {row.detail ? <span className="text-ink-muted">: {row.detail}</span> : null}
                </p>
                <p className="mt-0.5 text-xs text-ink-muted">{formatDateTime(row.created_at)}</p>
              </li>
            ))}
          </ul>
          {history.items.length < history.total ? (
            <Button variant="secondary" size="sm" className="mt-3" loading={history.loadingMore} onClick={() => void history.loadMore()}>
              {history.loadingMore ? "Loading..." : `Show more (${history.total - history.items.length} left)`}
            </Button>
          ) : null}
        </>
      )}
      <p className="mt-4 text-xs leading-5 text-ink-muted">Repeated views by the same doctor are shown once every ten minutes.</p>
    </DashCard>
  );
}
