"use client";

import { useState } from "react";
import { ArrowLeft, Bell, BellOff, CheckCheck, SlidersHorizontal } from "lucide-react";

import { PageContainer, PageHeader } from "@/components/layout/PageHeader";
import { Button, ButtonLink } from "@/components/ui/button";
import { EmptyState } from "@/components/ui/empty-state";
import { SkeletonCard } from "@/components/ui/skeleton";
import { ErrorState, PageLoader } from "@/components/ui/spinner";
import { useAuthGuard } from "@/hooks/use-auth-guard";
import { useNotifications } from "@/hooks/notifications/use-notifications";
import { dashboardPathForRole } from "@/lib/auth";
import { cn } from "@/lib/cn";
import { CATEGORY_LABEL, groupByDay } from "@/lib/notifications";
import type { NotificationCategory } from "@/lib/types";
import { NotificationItem } from "./NotificationItem";

type Role = "patient" | "doctor" | "admin";

const CATEGORIES_FOR: Record<Role, NotificationCategory[]> = {
  patient: ["appointments", "payments", "records", "account"],
  doctor: ["appointments", "payments", "account"],
  admin: ["admin", "account"],
};

export function NotificationsView() {
  const auth = useAuthGuard("any");
  if (auth.status === "error") return <ErrorState message={auth.message} onRetry={() => window.location.reload()} />;
  if (auth.status !== "ready") return <PageLoader message="Checking your session..." />;
  return <NotificationsContent role={auth.user.role} />;
}

function NotificationsContent({ role }: { role: Role }) {
  const [unreadOnly, setUnreadOnly] = useState(false);
  const [category, setCategory] = useState<NotificationCategory | "">("");
  const list = useNotifications({ unreadOnly, category, pageSize: 20 });
  const filtered = unreadOnly || category !== "";
  const groups = groupByDay(list.items);

  return (
    <PageContainer narrow>
      <PageHeader
        eyebrow="Inbox"
        title="Notifications"
        description="What happened on your account: appointments, payments, prescriptions and who opened your records."
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

      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div role="tablist" aria-label="Show" className="inline-flex rounded-control border border-line bg-white p-1">
          {[
            { id: false, label: "All" },
            { id: true, label: list.unread > 0 ? `Unread (${list.unread})` : "Unread" },
          ].map((tab) => (
            <button
              key={String(tab.id)}
              type="button"
              role="tab"
              aria-selected={unreadOnly === tab.id}
              onClick={() => setUnreadOnly(tab.id)}
              className={cn(
                "rounded-[10px] px-4 py-1.5 text-sm font-semibold transition-colors",
                unreadOnly === tab.id ? "bg-blue-50 text-brand-blue" : "text-slate-500 hover:text-ink",
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
        <div role="group" aria-label="Filter by type" className="-mx-1 flex gap-1.5 overflow-x-auto px-1 pb-1 sm:pb-0">
          {(["", ...CATEGORIES_FOR[role]] as const).map((id) => (
            <button
              key={id || "all"}
              type="button"
              aria-pressed={category === id}
              onClick={() => setCategory(id)}
              className={cn(
                "flex-shrink-0 rounded-full border px-3 py-1 text-xs font-semibold transition-colors",
                category === id ? "border-brand-blue bg-blue-50 text-brand-blue" : "border-line bg-white text-slate-600 hover:border-line-strong",
              )}
            >
              {id ? CATEGORY_LABEL[id] : "Everything"}
            </button>
          ))}
        </div>
      </div>

      {list.status === "error" ? (
        <ErrorState message={list.error} onRetry={list.retry} />
      ) : list.status === "loading" ? (
        <div role="status" aria-label="Loading notifications" className="space-y-3">
          <SkeletonCard lines={2} />
          <SkeletonCard lines={2} />
          <SkeletonCard lines={2} />
        </div>
      ) : list.items.length === 0 ? (
        <EmptyState
          icon={filtered ? BellOff : Bell}
          title={unreadOnly ? "You are all caught up" : filtered ? "Nothing in this group" : "Nothing here yet"}
          description={
            unreadOnly
              ? "There is nothing you have not read."
              : filtered
                ? "Try another type, or choose Everything."
                : "When you book or change an appointment, pay, get a prescription or someone opens your records, it shows up here."
          }
        />
      ) : (
        <>
          <div className="space-y-5" aria-live="polite">
            {groups.map((group) => (
              <section key={group.label} aria-label={group.label}>
                <h2 className="mb-2 px-1 text-xs font-semibold uppercase tracking-wide text-ink-muted">{group.label}</h2>
                <ul className="space-y-2.5">
                  {group.items.map((item) => (
                    <NotificationItem key={item.id} item={item} onRead={(id) => void list.markRead(id)} onDismiss={(id) => void list.dismiss(id)} />
                  ))}
                </ul>
              </section>
            ))}
          </div>
          <p className="mt-4 text-center text-xs text-ink-muted">
            Showing {list.items.length} of {list.total}
          </p>
          {list.hasMore ? (
            <div className="mt-3 text-center">
              <Button variant="secondary" onClick={() => void list.loadMore()} loading={list.loadingMore}>
                {list.loadingMore ? "Loading..." : "Load more"}
              </Button>
            </div>
          ) : null}
        </>
      )}

      <p className="mt-8 flex items-start gap-2 text-xs leading-5 text-ink-muted">
        <SlidersHorizontal className="mt-0.5 h-3.5 w-3.5 flex-shrink-0" aria-hidden />
        Read notifications are cleared after 90 days. Reminder emails can be switched off in your profile.
      </p>
    </PageContainer>
  );
}
