"use client";

import { useRouter } from "next/navigation";
import { useEffect, useState, type ReactNode } from "react";

import { Skeleton } from "@/components/ui/skeleton";
import { isApiError, api } from "@/lib/api";
import { clearSession, dashboardPathForRole, updateStoredUser } from "@/lib/auth";

/**
 * For sign in, sign up and forgot password: someone who is already signed in goes straight to their own
 * dashboard instead of seeing the form. The cookie session is the truth (the server is asked, and renews an
 * expired access token); the stored profile is only a hint. While the answer is pending a form-shaped
 * skeleton shows, so a signed-in person never sees the form flash.
 */
export function GuestOnly({ children }: { children: ReactNode }) {
  const router = useRouter();
  const [isGuest, setIsGuest] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    api
      .me({ signal: controller.signal })
      .then((user) => {
        updateStoredUser(user);
        router.replace(dashboardPathForRole(user.role));
      })
      .catch((error: unknown) => {
        if (controller.signal.aborted) return;
        if (isApiError(error, 401) || isApiError(error, 403)) clearSession(); // a stale profile must not look signed in
        setIsGuest(true); // no session, or the backend is unreachable: the form still works
      });
    return () => controller.abort();
  }, [router]);

  if (isGuest) return <>{children}</>;
  return (
    <div role="status" aria-label="Checking your session" className="space-y-4">
      <Skeleton className="h-11" />
      <Skeleton className="h-11" />
      <Skeleton className="h-12" />
    </div>
  );
}
