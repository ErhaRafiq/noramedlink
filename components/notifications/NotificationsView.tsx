"use client";

import Link from "next/link";
import { ArrowLeft, Bell, CalendarCheck2, CalendarClock, CalendarX2, CheckCheck, type LucideIcon } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { Button, ButtonLink } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { SkeletonCard } from "@/components/ui/skeleton";
import { ErrorState, PageLoader } from "@/components/ui/spinner";
import { useAuthGuard } from "@/hooks/use-auth-guard";
import { useNotifications } from "@/hooks/notifications/use-notifications";
import { dashboardPathForRole } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { formatDateTime } from "@/lib/datetime";
import type { AppNotification } from "@/lib/types";

const ICONS: Record<string, LucideIcon> = {
  appointment_confirmed: CalendarCheck2,
  appointment_rescheduled: CalendarClock,
  appointment_cancelled: CalendarX2,
  appointment_reminder: Bell,
};

export function NotificationsView() {
  const auth = useAuthGuard("any");
  if (auth.status === "error") return <ErrorState message={auth.message} onRetry={() => window.location.reload()} />;
  if (auth.status !== "ready") return <PageLoader message="Checking your session..." />;
  return <NotificationsContent role={auth.user.role} />;
}

function NotificationsContent({ role }: { role: "patient" | "doctor" | "admin" }) {
  const list = useNotifications();
  const appointmentsHref = role === "doctor" ? "/dashboard/doctor#appointments" : "/doctors";
  return (
    <PageContainer narrow>
      <PageHeader
        eyebrow="Inbox"
        title="Notifications"
        description="Appointment confirmations, changes and reminders."
        actions={
          <>
            <Button variant="secondary" size="sm" icon={<CheckCheck className="h-4 w-4" />} onClick={() => void list.markAllRead()} disabled={list.unread === 0}>
              Mark all read
            </Button>
            <ButtonLink href={dashboardPathForRole(role)} variant="secondary" size="sm" icon={<ArrowLeft className="h-4 w-4" />}>
              Dashboard
            </ButtonLink>
          </>
        }
      />
      {list.status === "error" ? (
        <ErrorState message={list.error} onRetry={list.retry} />
      ) : list.status === "loading" ? (
        <div role="status" aria-label="Loading notifications" className="space-y-3">
          <SkeletonCard lines={2} />
          <SkeletonCard lines={2} />
        </div>
      ) : list.items.length === 0 ? (
        <EmptyState icon={Bell} title="Nothing here yet" description="When you book, move or cancel an appointment, you will see it here, with reminders before each visit." />
      ) : (
        <>
          <ul className="space-y-2.5">
            {list.items.map((n) => (
              <Row key={n.id} item={n} href={appointmentsHref} onRead={() => void list.markRead(n.id)} />
            ))}
          </ul>
          {list.hasMore ? (
            <div className="mt-4 text-center">
              <Button variant="secondary" onClick={() => void list.loadMore()} loading={list.loadingMore}>
                {list.loadingMore ? "Loading..." : "Load more"}
              </Button>
            </div>
          ) : null}
        </>
      )}
    </PageContainer>
  );
}

function Row({ item, href, onRead }: { item: AppNotification; href: string; onRead: () => void }) {
  const Icon = ICONS[item.kind] ?? Bell;
  return (
    <li className={cn("flex items-start gap-3 rounded-card border p-4 shadow-card", item.read ? "border-line bg-white" : "border-blue-200 bg-blue-50/50")}>
      <span className={cn("grid h-9 w-9 flex-shrink-0 place-items-center rounded-control", item.read ? "bg-surface-soft text-slate-500" : "bg-brand-blue text-white")}>
        <Icon className="h-4 w-4" aria-hidden />
      </span>
      <div className="min-w-0 flex-1">
        <p className="break-words text-sm font-semibold text-ink">
          {item.title}
          {item.read ? null : <span className="sr-only"> (unread)</span>}
        </p>
        <p className="mt-0.5 break-words text-sm leading-6 text-ink-muted">{item.body}</p>
        <p className="mt-1 text-xs text-slate-400">{formatDateTime(item.at)}</p>
      </div>
      <div className="flex flex-shrink-0 flex-col items-end gap-1">
        {item.appointment_id ? (
          <Link href={href} className="text-xs font-semibold text-brand-blue hover:underline">
            View
          </Link>
        ) : null}
        {item.read ? null : (
          <button type="button" onClick={onRead} className="text-xs font-medium text-slate-500 hover:text-ink">
            Mark read
          </button>
        )}
      </div>
    </li>
  );
}
